"""Doctor-side routes: the queue, the case file, and the verification workflow."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import client_ip, current_doctor, current_user, doctor_visit
from app.core.errors import NotFound
from app.db.session import get_db
from app.models.clinical import RedFlag, Visit
from app.models.document import MedicalDocument
from app.models.enums import PriorityLevel, VisitStatus
from app.models.record import ClinicalSummary
from app.models.user import DoctorProfile, PatientProfile, User
from app.schemas.clinical import (
    CaseFileOut,
    DocumentOut,
    FinalizeRequest,
    QueueEntryOut,
    SummaryOut,
    SummarySectionOut,
    TimelineEventOut,
    VerifyRequest,
    VisitOut,
)
from app.models.access import AccessPurpose
from app.schemas.common import AuditEntry
from app.schemas.privacy import OpenCaseRequest
from app.schemas.conversation import RedFlagOut
from app.services import audit_service, summary_service, timeline_service
from app.services.privacy import access_guard
from app.services.redflag.redflag_service import rescore

router = APIRouter(prefix="/doctor", tags=["doctor"])

# Priority first, then longest wait. Deliberately not "newest first": the
# person who has been sitting there for an hour should not keep losing.
QUEUE_ORDER = {PriorityLevel.PRIORITY: 0, PriorityLevel.REVIEW: 1, PriorityLevel.NORMAL: 2}


@router.get("/queue", response_model=list[QueueEntryOut])
async def queue(
    queue_filter: PriorityLevel | None = Query(default=None, alias="queue"),
    doctor: DoctorProfile = Depends(current_doctor),
    db: AsyncSession = Depends(get_db),
) -> list[QueueEntryOut]:
    stmt = (
        select(Visit, PatientProfile, User)
        .join(PatientProfile, Visit.patient_id == PatientProfile.id)
        .join(User, PatientProfile.user_id == User.id)
        .where(Visit.status.in_([VisitStatus.INTAKE_COMPLETE, VisitStatus.IN_REVIEW, VisitStatus.INTAKE_STARTED]))
    )
    if queue_filter:
        stmt = stmt.where(Visit.priority_level == queue_filter)

    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    visit_ids = [visit.id for visit, _, _ in rows]
    flag_counts = dict(
        (
            await db.execute(
                select(RedFlag.visit_id, func.count(RedFlag.id))
                .where(RedFlag.visit_id.in_(visit_ids))
                .group_by(RedFlag.visit_id)
            )
        ).all()
    )
    summarised = set(
        (
            await db.execute(select(ClinicalSummary.visit_id).where(ClinicalSummary.visit_id.in_(visit_ids)))
        ).scalars()
    )

    # Rescore on read. Waiting time is part of the acuity score, so a queue
    # rendered from values frozen at intake would let long waits go unnoticed.
    for visit, _, _ in rows:
        await rescore(db, visit)
    await db.commit()

    now = datetime.now(UTC)
    entries = [
        QueueEntryOut(
            visit_id=visit.id,
            patient_id=profile.id,
            name=user.full_name,
            age=profile.age,
            sex=profile.sex,
            chief_complaint=visit.chief_complaint,
            queue=visit.priority_level,
            flag_count=int(flag_counts.get(visit.id, 0)),
            language=visit.language,
            waited_minutes=int((now - (visit.queued_at or visit.created_at)).total_seconds() // 60),
            status=visit.status,
            summary_ready=visit.id in summarised,
            priority_score=visit.priority_score,
            priority_reason=_top_reason(visit.priority_factors),
        )
        for visit, profile, user in rows
    ]
    # Band first, then score, then wait. The band keeps a fired rule at the top
    # regardless of arithmetic; the score orders within it.
    entries.sort(key=lambda e: (QUEUE_ORDER[e.queue], -e.priority_score, -e.waited_minutes))
    return entries


def _top_reason(factors: list | None) -> str | None:
    """One line for the queue row, describing reports rather than conclusions."""
    if not factors:
        return None
    top = sorted(factors, key=lambda f: f.get("points", 0), reverse=True)[:2]
    return "; ".join(f.get("label", "") for f in top if f.get("label")) or None


@router.post("/visits/{visit_id}/open", response_model=CaseFileOut)
async def case_file(
    payload: OpenCaseRequest,
    request: Request,
    visit: Visit = Depends(doctor_visit),
    doctor: DoctorProfile = Depends(current_doctor),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseFileOut:
    """
    Everything the doctor needs on one screen, in one round trip.

    POST rather than GET because opening a record is not a side-effect-free
    read: it requires a declared purpose, it may require a written
    justification, and it always writes a line the patient can see. Modelling
    that as a GET would invite caching and prefetching of an audited action.
    """
    await access_guard.authorize_read(
        db,
        actor=user,
        doctor_id=doctor.id,
        patient_id=visit.patient_id,
        resource="case_file",
        purpose=AccessPurpose(payload.purpose),
        justification=payload.justification,
        visit_id=visit.id,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    await rescore(db, visit)
    profile = await db.get(PatientProfile, visit.patient_id)
    if profile is None:
        raise NotFound("That patient record could not be found.")
    patient_user = await db.get(User, profile.user_id)

    flags = list((await db.execute(select(RedFlag).where(RedFlag.visit_id == visit.id))).scalars())
    documents = list(
        (await db.execute(select(MedicalDocument).where(MedicalDocument.visit_id == visit.id))).scalars()
    )
    summary = (
        await db.execute(
            select(ClinicalSummary)
            .options(selectinload(ClinicalSummary.sections))
            .where(ClinicalSummary.visit_id == visit.id)
        )
    ).scalar_one_or_none()

    events = await timeline_service.build(db, visit.patient_id, current_visit_id=visit.id)

    await audit_service.record(
        db, event="visit.viewed", actor_id=user.id, actor_role="doctor",
        entity_type="visit", entity_id=visit.id,
    )
    await db.commit()

    return CaseFileOut(
        visit=VisitOut.model_validate(visit),
        patient_name=patient_user.full_name if patient_user else "Unknown",
        patient_age=profile.age,
        patient_sex=profile.sex,
        red_flags=[RedFlagOut.model_validate(f) for f in flags],
        priority_score=visit.priority_score,
        priority_factors=visit.priority_factors or [],
        summary=_summary_out(summary) if summary else None,
        timeline=[TimelineEventOut(**event.__dict__) for event in events],
        documents=[DocumentOut.model_validate(d) for d in documents],
    )


def _summary_out(summary: ClinicalSummary) -> SummaryOut:
    payload = SummaryOut.model_validate(summary)
    payload.sections = [
        SummarySectionOut(
            id=s.id, key=s.key, label=s.label, display_order=s.display_order,
            ai_body=s.ai_body, doctor_body=s.doctor_body, body=s.body,
            provenance=s.provenance, status=s.status, source_refs=s.source_refs,
        )
        for s in sorted(summary.sections, key=lambda s: s.display_order)
    ]
    return payload


@router.post("/visits/{visit_id}/summary", response_model=SummaryOut, status_code=201)
async def generate_summary(
    visit: Visit = Depends(doctor_visit),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> SummaryOut:
    summary = await summary_service.generate(db, visit=visit, actor_id=user.id)
    await db.commit()
    await db.refresh(summary, ["sections"])
    return _summary_out(summary)


@router.get("/visits/{visit_id}/summary", response_model=SummaryOut)
async def get_summary(
    visit: Visit = Depends(doctor_visit), db: AsyncSession = Depends(get_db)
) -> SummaryOut:
    summary = (
        await db.execute(
            select(ClinicalSummary)
            .options(selectinload(ClinicalSummary.sections))
            .where(ClinicalSummary.visit_id == visit.id)
        )
    ).scalar_one_or_none()
    if summary is None:
        raise NotFound("No summary has been drafted for this visit yet.")
    return _summary_out(summary)


@router.post("/summaries/{summary_id}/verify", response_model=SummarySectionOut)
async def verify_section(
    summary_id: uuid.UUID,
    payload: VerifyRequest,
    doctor: DoctorProfile = Depends(current_doctor),
    db: AsyncSession = Depends(get_db),
) -> SummarySectionOut:
    section = await summary_service.verify_section(
        db, summary_id=summary_id, section_key=payload.section, action=payload.action,
        doctor_id=doctor.id, body=payload.body, reason=payload.reason,
    )
    await db.commit()
    return SummarySectionOut(
        id=section.id, key=section.key, label=section.label, display_order=section.display_order,
        ai_body=section.ai_body, doctor_body=section.doctor_body, body=section.body,
        provenance=section.provenance, status=section.status, source_refs=section.source_refs,
    )


@router.post("/summaries/{summary_id}/finalize", response_model=SummaryOut)
async def finalize_summary(
    summary_id: uuid.UUID,
    payload: FinalizeRequest,
    doctor: DoctorProfile = Depends(current_doctor),
    db: AsyncSession = Depends(get_db),
) -> SummaryOut:
    summary = await summary_service.finalize(db, summary_id=summary_id, doctor_id=doctor.id, notes=payload.notes)
    await db.commit()
    await db.refresh(summary, ["sections"])
    return _summary_out(summary)


@router.get("/patients/{patient_id}/timeline", response_model=list[TimelineEventOut])
async def timeline(
    patient_id: uuid.UUID,
    doctor: DoctorProfile = Depends(current_doctor),
    db: AsyncSession = Depends(get_db),
) -> list[TimelineEventOut]:
    events = await timeline_service.build(db, patient_id)
    return [TimelineEventOut(**event.__dict__) for event in events]


@router.get("/audit/{entity_type}/{entity_id}", response_model=list[AuditEntry])
async def audit_trail(
    entity_type: str,
    entity_id: uuid.UUID,
    doctor: DoctorProfile = Depends(current_doctor),
    db: AsyncSession = Depends(get_db),
) -> list[AuditEntry]:
    entries = await audit_service.trail(db, entity_type, entity_id)
    return [AuditEntry.model_validate(e) for e in entries]
