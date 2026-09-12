"""
Privacy and transparency routes.

The centrepiece is `GET /privacy/my-access-log`. Every technical control in
`access_guard` is a deterrent only if someone can see it working, and the
person with the strongest incentive to look is the patient. Making access
visible to them turns an internal audit table into an actual check on
behaviour: selling records stops being an invisible act.

The sharing consent routes exist for the same reason. Export is gated on a
consent the patient grants and can withdraw at any moment — the decision to
send a record outside the hospital belongs to them, not to the clinician
holding the keyboard.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_patient, current_user, require_admin
from app.core.errors import NotFound
from app.db.session import get_db
from app.models.access import AccessDecision, ExportReceipt, MisuseAlert, RecordAccess
from app.models.enums import ConsentScope, Language
from app.models.user import Consent, PatientProfile, User
from app.schemas.privacy import (
    AccessLogEntryOut,
    ExportReceiptOut,
    MisuseAlertOut,
    ReviewAlertRequest,
    SharingConsentOut,
    SharingConsentRequest,
)
from app.services import audit_service

router = APIRouter(prefix="/privacy", tags=["privacy"])

# Shown above the access log. Written for a first-time reader, not a lawyer.
TRANSPARENCY_NOTICE = (
    "This is every time a member of hospital staff opened your record. If you see "
    "an entry you do not recognise, or a reason that does not make sense to you, "
    "you can raise it with the hospital. Staff are told that you can see this list."
)


@router.get("/my-access-log", response_model=list[AccessLogEntryOut])
async def my_access_log(
    limit: int = Query(default=100, le=500),
    patient: PatientProfile = Depends(current_patient),
    db: AsyncSession = Depends(get_db),
) -> list[AccessLogEntryOut]:
    """Who opened this patient's record, when, and the reason they gave."""
    rows = await db.execute(
        select(RecordAccess)
        .where(RecordAccess.patient_id == patient.id)
        .order_by(RecordAccess.created_at.desc())
        .limit(limit)
    )
    return [
        AccessLogEntryOut(
            id=access.id,
            accessed_by=access.actor_name or "Hospital staff",
            role=access.actor_role,
            resource=access.resource,
            purpose=access.purpose.value,
            # Break-glass is surfaced plainly rather than buried. If someone
            # opened a record they had no relationship with, the patient should
            # not have to interpret a status code to find that out.
            unusual=access.decision is AccessDecision.BREAK_GLASS,
            reason_given=access.justification,
            occurred_at=access.created_at,
        )
        for access in rows.scalars()
    ]


@router.get("/my-exports", response_model=list[ExportReceiptOut])
async def my_exports(
    patient: PatientProfile = Depends(current_patient), db: AsyncSession = Depends(get_db)
) -> list[ExportReceiptOut]:
    """
    Every copy of this record that has left the system.

    The watermark is shown to the patient too. If a copy of their record turns
    up somewhere it should not, that string identifies which export it came
    from and therefore who made it.
    """
    rows = await db.execute(
        select(ExportReceipt)
        .where(ExportReceipt.patient_id == patient.id)
        .order_by(ExportReceipt.created_at.desc())
        .limit(100)
    )
    return [
        ExportReceiptOut(
            id=receipt.id,
            exported_by=receipt.actor_name or "Hospital staff",
            watermark=receipt.watermark,
            section_count=receipt.section_count,
            purpose=receipt.purpose.value,
            occurred_at=receipt.created_at,
            revoked_at=receipt.revoked_at,
        )
        for receipt in rows.scalars()
    ]


@router.get("/notice")
async def transparency_notice() -> dict:
    return {"notice": TRANSPARENCY_NOTICE}


@router.get("/sharing-consent", response_model=SharingConsentOut)
async def get_sharing_consent(
    patient: PatientProfile = Depends(current_patient), db: AsyncSession = Depends(get_db)
) -> SharingConsentOut:
    consent = (
        await db.execute(
            select(Consent).where(
                Consent.patient_id == patient.id, Consent.scope == ConsentScope.ABDM_SHARING
            )
        )
    ).scalars().first()

    granted = bool(consent and consent.granted and consent.withdrawn_at is None)
    return SharingConsentOut(
        granted=granted,
        granted_at=consent.granted_at if granted and consent else None,
        withdrawn_at=consent.withdrawn_at if consent else None,
        explanation=(
            "While this is on, a doctor treating you can send a copy of your verified "
            "record to another hospital or to your national health account. Turning it "
            "off stops any new copies being made. It does not delete copies already sent."
        ),
    )


@router.post("/sharing-consent", response_model=SharingConsentOut)
async def set_sharing_consent(
    payload: SharingConsentRequest,
    patient: PatientProfile = Depends(current_patient),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> SharingConsentOut:
    """
    Grant or withdraw sharing. Withdrawal takes effect immediately — the next
    export attempt is refused, whatever the doctor's stated reason.
    """
    consent = (
        await db.execute(
            select(Consent).where(
                Consent.patient_id == patient.id, Consent.scope == ConsentScope.ABDM_SHARING
            )
        )
    ).scalars().first()

    now = datetime.now(UTC)
    if consent is None:
        consent = Consent(
            patient_id=patient.id, scope=ConsentScope.ABDM_SHARING, granted=payload.granted,
            language_shown=payload.language_shown or Language.EN,
        )
        db.add(consent)

    consent.granted = payload.granted
    if payload.granted:
        consent.granted_at, consent.withdrawn_at = now, None
    else:
        consent.withdrawn_at = now
    consent.consent_text = payload.consent_text
    await db.flush()

    await audit_service.record(
        db,
        event=(
            audit_service.AuditEvent.CONSENT_GRANTED
            if payload.granted
            else audit_service.AuditEvent.CONSENT_WITHDRAWN
        ),
        actor_id=user.id,
        actor_role="patient",
        entity_type="consent",
        entity_id=consent.id,
        summary=f"Sharing consent {'granted' if payload.granted else 'withdrawn'} by the patient.",
    )
    await db.commit()

    return SharingConsentOut(
        granted=payload.granted,
        granted_at=consent.granted_at,
        withdrawn_at=consent.withdrawn_at,
        explanation="Updated. This takes effect immediately.",
    )


# --------------------------------------------------------------------- admin --


@router.get("/alerts", response_model=list[MisuseAlertOut], dependencies=[Depends(require_admin)])
async def misuse_alerts(
    unreviewed_only: bool = Query(default=True), db: AsyncSession = Depends(get_db)
) -> list[MisuseAlertOut]:
    """
    Access patterns that resemble harvesting rather than clinical work.

    Admin-only, and deliberately not exposed to doctors: an alert about a
    colleague is not clinical information, and widening who can read it would
    turn a safeguard into gossip.
    """
    stmt = select(MisuseAlert).order_by(MisuseAlert.created_at.desc()).limit(200)
    if unreviewed_only:
        stmt = stmt.where(MisuseAlert.reviewed_at.is_(None))

    alerts = (await db.execute(stmt)).scalars()
    out: list[MisuseAlertOut] = []
    for alert in alerts:
        actor = await db.get(User, alert.actor_id)
        out.append(
            MisuseAlertOut(
                id=alert.id,
                kind=alert.kind.value,
                actor_name=actor.full_name if actor else "Unknown account",
                actor_email=actor.email if actor else None,
                detail=alert.detail,
                observed_count=alert.observed_count,
                threshold=alert.threshold,
                window_minutes=alert.window_minutes,
                created_at=alert.created_at,
                reviewed_at=alert.reviewed_at,
                review_note=alert.review_note,
            )
        )
    return out


@router.post("/alerts/{alert_id}/review", response_model=MisuseAlertOut, dependencies=[Depends(require_admin)])
async def review_alert(
    alert_id: uuid.UUID,
    payload: ReviewAlertRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> MisuseAlertOut:
    alert = await db.get(MisuseAlert, alert_id)
    if alert is None:
        raise NotFound("That alert could not be found.")

    alert.reviewed_at = datetime.now(UTC)
    alert.reviewed_by = user.id
    alert.review_note = payload.note
    await db.flush()

    await audit_service.record(
        db,
        event="privacy.alert_reviewed",
        actor_id=user.id,
        actor_role=user.role.value,
        entity_type="misuse_alert",
        entity_id=alert.id,
        summary=payload.note[:200] if payload.note else None,
    )
    await db.commit()

    actor = await db.get(User, alert.actor_id)
    return MisuseAlertOut(
        id=alert.id,
        kind=alert.kind.value,
        actor_name=actor.full_name if actor else "Unknown account",
        actor_email=actor.email if actor else None,
        detail=alert.detail,
        observed_count=alert.observed_count,
        threshold=alert.threshold,
        window_minutes=alert.window_minutes,
        created_at=alert.created_at,
        reviewed_at=alert.reviewed_at,
        review_note=alert.review_note,
    )
