"""
The insider-misuse guard.

Called on every read of a patient record and every export. It does four things
in order: establish whether a clinical relationship exists, bind the access to
a declared purpose, look for patterns that resemble harvesting, and record the
whole thing where the patient can see it.

Design note on why nothing here hard-blocks a read: in a government OPD, the
one time a doctor urgently needs a record they have no formal relationship with
is exactly the time a strict rule would refuse. So the guard makes unusual
access *expensive and visible* — a justification, a break-glass marker, an
alert, a line on the patient's own log — rather than impossible. Deterrence and
traceability beat a blunt denial that gets worked around or disabled.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, Forbidden
from app.core.logging import get_logger, request_id_ctx
from app.models.access import (
    AccessDecision,
    AccessPurpose,
    AlertKind,
    ExportReceipt,
    MisuseAlert,
    RecordAccess,
)
from app.models.clinical import Visit
from app.models.enums import ConsentScope, VisitStatus
from app.models.user import Consent, User
from app.services import audit_service

log = get_logger(__name__)

# Harvesting thresholds. Set from what a genuinely busy OPD session looks like:
# a doctor seeing 60 patients in a session opens roughly one record every two
# minutes. Thirty distinct patients in fifteen minutes is not clinical work.
BULK_WINDOW_MINUTES = 15
BULK_DISTINCT_PATIENTS = 30

BREAK_GLASS_WINDOW_MINUTES = 60
BREAK_GLASS_THRESHOLD = 5

EXPORT_WINDOW_MINUTES = 60
EXPORT_THRESHOLD = 10

# Requires a justification of at least this length. Short enough not to be
# obstructive, long enough that "x" does not pass.
MIN_JUSTIFICATION = 12


async def _has_clinical_relationship(db: AsyncSession, *, doctor_id: uuid.UUID, patient_id: uuid.UUID) -> bool:
    """
    True when this patient is in an open queue, or was previously consulted by
    this doctor. Both are ordinary reasons to open a record.
    """
    open_visit = await db.execute(
        select(Visit.id).where(
            Visit.patient_id == patient_id,
            Visit.status.in_(
                [VisitStatus.INTAKE_STARTED, VisitStatus.INTAKE_COMPLETE, VisitStatus.IN_REVIEW]
            ),
        ).limit(1)
    )
    if open_visit.scalar_one_or_none() is not None:
        return True

    prior = await db.execute(
        select(Visit.id)
        .where(Visit.patient_id == patient_id, Visit.assigned_doctor_id == doctor_id)
        .limit(1)
    )
    return prior.scalar_one_or_none() is not None


async def authorize_read(
    db: AsyncSession,
    *,
    actor: User,
    doctor_id: uuid.UUID,
    patient_id: uuid.UUID,
    resource: str,
    purpose: AccessPurpose,
    justification: str | None,
    visit_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AccessDecision:
    """
    Authorise, record, and return the decision. Raises only when a required
    justification is missing — never simply because the pattern looked odd.
    """
    related = await _has_clinical_relationship(db, doctor_id=doctor_id, patient_id=patient_id)
    decision = AccessDecision.ALLOWED

    if not related:
        # No queue entry, no prior consultation. This is the access worth
        # making expensive, because it is the shape data harvesting takes.
        if purpose is AccessPurpose.TREATMENT:
            raise Forbidden(
                "This patient is not in your queue and you have not consulted them before. "
                "Select 'emergency' or 'continuity of care' and give a reason."
            )
        if not justification or len(justification.strip()) < MIN_JUSTIFICATION:
            raise Forbidden(
                "Opening a record outside your queue needs a written reason of at least "
                f"{MIN_JUSTIFICATION} characters. It is recorded and shown to the patient."
            )
        decision = AccessDecision.BREAK_GLASS

    db.add(
        RecordAccess(
            actor_id=actor.id,
            actor_role=actor.role.value,
            actor_name=actor.full_name,
            patient_id=patient_id,
            visit_id=visit_id,
            resource=resource,
            purpose=purpose,
            decision=decision,
            justification=(justification or "").strip()[:2000] or None,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:255] or None,
            request_id=request_id_ctx.get(),
        )
    )
    await db.flush()

    await _detect_patterns(db, actor_id=actor.id)
    return decision


async def _detect_patterns(db: AsyncSession, *, actor_id: uuid.UUID) -> None:
    """
    Rule-based anomaly detection over the access log. Alerts are deduplicated
    within their own window so one harvesting session does not generate a
    thousand identical alerts and bury the signal.
    """
    now = datetime.now(UTC)

    async def already_alerted(kind: AlertKind, window: int) -> bool:
        existing = await db.execute(
            select(MisuseAlert.id).where(
                MisuseAlert.actor_id == actor_id,
                MisuseAlert.kind == kind,
                MisuseAlert.created_at >= now - timedelta(minutes=window),
            ).limit(1)
        )
        return existing.scalar_one_or_none() is not None

    # --- distinct patients opened in a short window ---
    distinct = await db.execute(
        select(func.count(func.distinct(RecordAccess.patient_id))).where(
            RecordAccess.actor_id == actor_id,
            RecordAccess.created_at >= now - timedelta(minutes=BULK_WINDOW_MINUTES),
        )
    )
    count = int(distinct.scalar_one() or 0)
    if count >= BULK_DISTINCT_PATIENTS and not await already_alerted(AlertKind.BULK_ACCESS, BULK_WINDOW_MINUTES):
        db.add(
            MisuseAlert(
                actor_id=actor_id,
                kind=AlertKind.BULK_ACCESS,
                detail=(
                    f"{count} different patient records were opened by this account in "
                    f"{BULK_WINDOW_MINUTES} minutes. This is above the pattern expected of "
                    "clinical work and has been flagged for review."
                ),
                window_minutes=BULK_WINDOW_MINUTES,
                observed_count=count,
                threshold=BULK_DISTINCT_PATIENTS,
            )
        )
        log.warning("Bulk access pattern flagged", extra={"extra": {"actor_id": str(actor_id), "count": count}})

    # --- repeated break-glass ---
    glass = await db.execute(
        select(func.count(RecordAccess.id)).where(
            RecordAccess.actor_id == actor_id,
            RecordAccess.decision == AccessDecision.BREAK_GLASS,
            RecordAccess.created_at >= now - timedelta(minutes=BREAK_GLASS_WINDOW_MINUTES),
        )
    )
    glass_count = int(glass.scalar_one() or 0)
    if glass_count >= BREAK_GLASS_THRESHOLD and not await already_alerted(
        AlertKind.OFF_QUEUE_PATTERN, BREAK_GLASS_WINDOW_MINUTES
    ):
        db.add(
            MisuseAlert(
                actor_id=actor_id,
                kind=AlertKind.OFF_QUEUE_PATTERN,
                detail=(
                    f"This account used emergency access to open {glass_count} records outside its "
                    f"queue within {BREAK_GLASS_WINDOW_MINUTES} minutes."
                ),
                window_minutes=BREAK_GLASS_WINDOW_MINUTES,
                observed_count=glass_count,
                threshold=BREAK_GLASS_THRESHOLD,
            )
        )

    await db.flush()


async def authorize_export(
    db: AsyncSession,
    *,
    actor: User,
    patient_id: uuid.UUID,
    purpose: AccessPurpose,
) -> uuid.UUID:
    """
    Export is the act that actually moves data out of the building, so it is
    gated harder than a read. Returns the consent id that permitted it.
    """
    consent = (
        await db.execute(
            select(Consent).where(
                Consent.patient_id == patient_id,
                Consent.scope == ConsentScope.ABDM_SHARING,
                Consent.granted.is_(True),
                Consent.withdrawn_at.is_(None),
            )
        )
    ).scalars().first()

    if consent is None:
        # The patient owns this decision, not the doctor. Without an active
        # sharing consent there is no export, whatever the clinician's reason.
        raise Forbidden(
            "This patient has not given consent to share their record outside the hospital. "
            "Ask them to grant sharing consent before exporting."
        )

    now = datetime.now(UTC)
    recent = await db.execute(
        select(func.count(ExportReceipt.id)).where(
            ExportReceipt.actor_id == actor.id,
            ExportReceipt.created_at >= now - timedelta(minutes=EXPORT_WINDOW_MINUTES),
        )
    )
    export_count = int(recent.scalar_one() or 0)
    if export_count >= EXPORT_THRESHOLD:
        db.add(
            MisuseAlert(
                actor_id=actor.id,
                kind=AlertKind.EXPORT_VOLUME,
                detail=(
                    f"This account exported {export_count} records within {EXPORT_WINDOW_MINUTES} minutes. "
                    "Further exports are paused pending review."
                ),
                window_minutes=EXPORT_WINDOW_MINUTES,
                observed_count=export_count,
                threshold=EXPORT_THRESHOLD,
            )
        )
        await db.flush()
        # Export is the one place a hard stop is right: unlike a read, nothing
        # clinical is lost by pausing it for a few minutes.
        raise Conflict(
            "You have exported an unusual number of records in a short time. "
            "Exports are paused for this account pending review."
        )

    return consent.id


def watermark_for(actor_id: uuid.UUID, patient_id: uuid.UUID) -> str:
    """
    Unique per export, unguessable, and not derivable from the patient id.
    Embedded in the bundle and stored on the receipt.
    """
    nonce = secrets.token_hex(6)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    digest = hashlib.sha256(f"{actor_id}{patient_id}{nonce}".encode()).hexdigest()[:10]
    return f"MK-{stamp}-{digest}-{nonce}".upper()


async def record_export(
    db: AsyncSession,
    *,
    actor: User,
    patient_id: uuid.UUID,
    visit_id: uuid.UUID | None,
    watermark: str,
    payload_bytes: bytes,
    section_count: int,
    consent_id: uuid.UUID | None,
    purpose: AccessPurpose,
    ip_address: str | None,
) -> ExportReceipt:
    receipt = ExportReceipt(
        actor_id=actor.id,
        actor_name=actor.full_name,
        patient_id=patient_id,
        visit_id=visit_id,
        watermark=watermark,
        payload_sha256=hashlib.sha256(payload_bytes).hexdigest(),
        section_count=section_count,
        consent_id=consent_id,
        purpose=purpose,
        ip_address=ip_address,
    )
    db.add(receipt)

    db.add(
        RecordAccess(
            actor_id=actor.id,
            actor_role=actor.role.value,
            actor_name=actor.full_name,
            patient_id=patient_id,
            visit_id=visit_id,
            resource="export",
            purpose=purpose,
            decision=AccessDecision.ALLOWED,
            ip_address=ip_address,
            request_id=request_id_ctx.get(),
        )
    )
    await audit_service.record(
        db,
        event=audit_service.AuditEvent.ABDM_EXPORTED,
        actor_id=actor.id,
        actor_role=actor.role.value,
        entity_type="patient",
        entity_id=patient_id,
        summary=f"Record exported under watermark {watermark}.",
    )
    await db.flush()
    return receipt
