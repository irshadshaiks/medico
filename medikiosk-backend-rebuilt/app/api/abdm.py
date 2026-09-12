"""
Simulated ABDM endpoints.

Every response from this router carries `simulated: true` and a notice string.
That is not decoration — presenting a mock government integration as real would
be the single most damaging thing this project could do.
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import client_ip, current_doctor, current_patient, current_user
from app.core.errors import Conflict, NotFound
from app.db.session import get_db
from app.models.clinical import Visit
from app.models.document import Investigation, Medication
from app.models.enums import VerificationState
from app.models.record import AbdmSyncLog, ClinicalSummary
from app.models.user import DoctorProfile, PatientProfile, User
from app.schemas.clinical import AbhaLinkOut, AbhaLinkRequest
from app.services import audit_service
from app.models.access import AccessPurpose
from app.services.abdm.factory import get_abdm_service
from app.services.privacy import access_guard

router = APIRouter(prefix="/abdm", tags=["abdm (simulated)"])

NOTICE = (
    "This is a simulated ABDM integration built for a hackathon demonstration. "
    "No data is sent to, or received from, the Ayushman Bharat Digital Mission."
)


@router.post("/link-abha", response_model=AbhaLinkOut)
async def link_abha(
    payload: AbhaLinkRequest,
    patient: PatientProfile = Depends(current_patient),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> AbhaLinkOut:
    from datetime import UTC, datetime

    adapter = get_abdm_service()
    result = await adapter.link_abha(
        full_name=user.full_name,
        year_of_birth=patient.date_of_birth.year if patient.date_of_birth else None,
        mobile=user.phone,
    )

    patient.abha_id = result.abha_id
    patient.abha_linked_at = datetime.now(UTC)
    db.add(AbdmSyncLog(patient_id=patient.id, operation="link_abha", adapter=adapter.name, simulated=True))
    await audit_service.record(
        db, event=audit_service.AuditEvent.ABDM_LINKED, actor_id=user.id, actor_role="patient",
        entity_type="patient", entity_id=patient.id, summary="Simulated ABHA number linked.",
    )
    await db.commit()
    return AbhaLinkOut(abha_id=result.abha_id, simulated=result.simulated, message=result.message)


@router.get("/export/{visit_id}")
async def export_record(
    visit_id: uuid.UUID,
    request: Request,
    purpose: str = Query(default="treatment", pattern="^(treatment|continuity_of_care|emergency)$"),
    doctor: DoctorProfile = Depends(current_doctor),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    FHIR-shaped export of the verified record only. Drafts are excluded.

    Export is the act that actually moves data out of the hospital, so it is
    gated harder than a read. Three things must hold: the patient has an active
    sharing consent, this account is not exporting at a rate that looks like
    bulk extraction, and every copy produced carries a unique watermark tying
    it to the account and moment that made it.
    """
    visit = await db.get(Visit, visit_id)
    if visit is None:
        raise NotFound("That visit could not be found.")

    summary = (
        await db.execute(
            select(ClinicalSummary)
            .options(selectinload(ClinicalSummary.sections))
            .where(ClinicalSummary.visit_id == visit.id)
        )
    ).scalar_one_or_none()
    if summary is None or summary.status is not VerificationState.VERIFIED:
        raise Conflict("Only a doctor-verified record can be exported. Finalise the summary first.")

    profile = await db.get(PatientProfile, visit.patient_id)
    patient_user = await db.get(User, profile.user_id) if profile else None

    verified_sections = [
        {"label": s.label, "body": s.body}
        for s in summary.sections
        if s.status in (VerificationState.VERIFIED, VerificationState.EDITED)
    ]
    medications = list(
        (await db.execute(select(Medication).where(Medication.patient_id == visit.patient_id))).scalars()
    )
    investigations = list(
        (await db.execute(select(Investigation).where(Investigation.patient_id == visit.patient_id))).scalars()
    )

    # Patient consent first. Without it there is no export, whatever reason the
    # clinician gives -- the decision to send a record outside the hospital
    # belongs to the person the record is about.
    consent_id = await access_guard.authorize_export(
        db, actor=user, patient_id=visit.patient_id, purpose=AccessPurpose(purpose)
    )

    adapter = get_abdm_service()
    bundle = await adapter.export_record(
        {
            "patient": {
                "id": str(profile.id) if profile else None,
                "name": patient_user.full_name if patient_user else None,
                "sex": profile.sex if profile else None,
                "abha_id": profile.abha_id if profile else None,
            },
            "sections": verified_sections,
            "medications": [{"name": m.name, "dose": m.dose, "frequency": m.frequency} for m in medications],
            "investigations": [
                {"name": i.name, "value": i.value, "unit": i.unit,
                 "date": str(i.performed_on) if i.performed_on else None}
                for i in investigations
            ],
        }
    )

    # Watermark the bundle itself, not just the log. A file found somewhere it
    # should not be carries its own provenance.
    watermark = access_guard.watermark_for(user.id, visit.patient_id)
    bundle["_watermark"] = watermark
    bundle["_issued_to"] = {"account": user.email, "name": user.full_name, "purpose": purpose}
    bundle["_traceability"] = (
        "This export is uniquely watermarked and recorded against the account that "
        "produced it. The patient can see this export on their own access log."
    )

    payload_bytes = json.dumps(bundle, sort_keys=True, default=str).encode()
    await access_guard.record_export(
        db,
        actor=user,
        patient_id=visit.patient_id,
        visit_id=visit.id,
        watermark=watermark,
        payload_bytes=payload_bytes,
        section_count=len(verified_sections),
        consent_id=consent_id,
        purpose=AccessPurpose(purpose),
        ip_address=client_ip(request),
    )

    db.add(
        AbdmSyncLog(
            patient_id=visit.patient_id, visit_id=visit.id, operation="export_record",
            adapter=adapter.name, simulated=True,
            payload_preview={
                "sections": len(verified_sections),
                "medications": len(medications),
                "watermark": watermark,
            },
        )
    )
    await db.commit()
    return JSONResponse(
        content=bundle,
        headers={"X-MediKiosk-Simulated": "true", "X-MediKiosk-Watermark": watermark},
    )


@router.get("/status")
async def status() -> dict:
    adapter = get_abdm_service()
    return {"adapter": adapter.name, "simulated": adapter.simulated, "notice": NOTICE}
