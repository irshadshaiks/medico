"""
Escalation service.

This is the answer to the criticism that a pre-consultation system is useless
to someone who is actually unwell. The system's job in that moment is not to
interview anybody. It is to work out within about ten seconds that this person
should not be in the OPD queue at all, and get them out of it.

Three things happen when a rule fires, in this order:

  1. The conversation halts. Continuing to ask a patient about the character of
     their pain after deciding they need a human now is indefensible.
  2. The patient's screen is replaced by a single instruction and a destination.
  3. The triage desk is alerted with the token number and what was reported.

Two guarantees this module must never break:

  * **Fail open.** If escalation evaluation raises, times out, or the database
    is unreachable, the patient continues intake normally and the red-flag
    engine still runs. A safety feature that can block a patient from being
    seen is a worse defect than the one it fixes.
  * **Never a diagnosis.** The patient is told where to go, never what the
    system thinks is wrong. Staff are shown what the patient reported and which
    rule matched, never an interpretation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.clinical import Conversation, PatientResponse, Visit
from app.models.enums import ConversationStatus, PriorityLevel, VisitStatus
from app.models.escalation import Escalation, EscalationStatus
from app.services import audit_service
from app.services.escalation.rules import RULES_BY_ID, EscalationRule, evaluate

log = get_logger(__name__)


def _facts_from(responses: list[PatientResponse]) -> dict:
    facts: dict = {}
    for response in responses:
        for key, value in (response.structured_value or {}).items():
            if key.startswith("_"):
                continue
            facts[key] = bool(facts.get(key)) or bool(value)
    return facts


def _permitted(rule: EscalationRule) -> bool:
    """
    An unreviewed rule must never reach a real patient.

    In production a rule without clinical sign-off is skipped entirely and the
    omission is logged loudly. Outside production it fires, so the demo and the
    tests exercise the real path.
    """
    if rule.signed_off:
        return True
    if settings.ENV == "production":
        log.error(
            "Escalation rule skipped: no clinical sign-off",
            extra={"extra": {"rule": rule.id}},
        )
        return False
    return True


async def check(
    db: AsyncSession,
    *,
    visit: Visit,
    conversation: Conversation,
    actor_id: uuid.UUID | None = None,
) -> Escalation | None:
    """
    Evaluate escalation rules for this conversation.

    Returns the Escalation if one was raised, otherwise None. Never raises:
    every failure path returns None and lets intake continue.
    """
    try:
        responses = list(
            (
                await db.execute(
                    select(PatientResponse).where(PatientResponse.conversation_id == conversation.id)
                )
            ).scalars()
        )
        facts = _facts_from(responses)
        fired = [rule for rule in evaluate(facts) if _permitted(rule)]
        if not fired:
            return None

        # One escalation per visit. A patient already told to go to Casualty
        # does not need a second alarm, and staff do not need a duplicate row.
        existing = (
            await db.execute(
                select(Escalation).where(
                    Escalation.visit_id == visit.id,
                    Escalation.status == EscalationStatus.RAISED,
                )
            )
        ).scalars().first()
        if existing is not None:
            return existing

        rule = fired[0]
        evidence = [
            {"key": key, "said": response.raw_text[:280]}
            for key in rule.evidence_keys
            if facts.get(key)
            for response in responses
            if (response.structured_value or {}).get(key)
        ][:4]

        escalation = Escalation(
            visit_id=visit.id,
            conversation_id=conversation.id,
            rule_id=rule.id,
            staff_label=rule.staff_label,
            destination=rule.destination,
            patient_instruction=rule.patient_instruction,
            evidence=evidence,
            matched_rules=[r.id for r in fired],
            clinically_signed_off=rule.signed_off,
            status=EscalationStatus.RAISED,
        )
        db.add(escalation)

        # Halt the interview. The visit stays in the queue as a priority entry
        # as well -- if the patient ignores the instruction, or staff miss the
        # alert, they must not vanish from both systems at once.
        conversation.status = ConversationStatus.HALTED_ESCALATED
        conversation.completed_at = datetime.now(UTC)
        visit.priority_level = PriorityLevel.PRIORITY
        if visit.status == VisitStatus.INTAKE_STARTED:
            visit.status = VisitStatus.INTAKE_COMPLETE
            visit.queued_at = visit.queued_at or datetime.now(UTC)

        await db.flush()

        log.warning(
            "Escalation raised",
            extra={
                "extra": {
                    "rule": rule.id,
                    "visit_id": str(visit.id),
                    "signed_off": rule.signed_off,
                }
            },
        )
        await audit_service.record(
            db,
            event="escalation.raised",
            actor_id=actor_id,
            actor_role="patient",
            entity_type="visit",
            entity_id=visit.id,
            summary=rule.staff_label,
            after={"rule_id": rule.id, "destination": rule.destination},
        )
        return escalation

    except Exception as exc:  # noqa: BLE001
        # Fail open, loudly. The patient continues; red flags still run.
        log.error(
            "Escalation check failed; intake continues",
            extra={"extra": {"visit_id": str(visit.id), "error": str(exc)[:300]}},
        )
        return None


async def acknowledge(
    db: AsyncSession,
    *,
    escalation_id: uuid.UUID,
    staff_user_id: uuid.UUID,
    outcome: str,
    note: str | None = None,
) -> Escalation | None:
    """
    A staff member confirms they have collected the patient.

    Acknowledgement is the only thing that clears the alarm. It deliberately
    cannot be done by the patient or by a timeout: an alert that silently
    expires is worse than no alert, because the screen looks calm while nobody
    has gone to fetch anyone.
    """
    escalation = await db.get(Escalation, escalation_id)
    if escalation is None:
        return None

    escalation.status = EscalationStatus.ACKNOWLEDGED
    escalation.acknowledged_by = staff_user_id
    escalation.acknowledged_at = datetime.now(UTC)
    escalation.outcome = outcome
    escalation.outcome_note = note
    await db.flush()

    await audit_service.record(
        db,
        event="escalation.acknowledged",
        actor_id=staff_user_id,
        actor_role="staff",
        entity_type="escalation",
        entity_id=escalation.id,
        summary=f"{outcome}: {note[:160] if note else ''}",
    )
    return escalation


async def open_escalations(db: AsyncSession) -> list[Escalation]:
    """Everything not yet acknowledged, oldest first — that is the order to work."""
    result = await db.execute(
        select(Escalation)
        .where(Escalation.status == EscalationStatus.RAISED)
        .order_by(Escalation.created_at)
    )
    return list(result.scalars())
