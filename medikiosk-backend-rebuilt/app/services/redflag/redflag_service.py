"""
Evaluates the rules after every answer and keeps Visit.priority_level in sync.

Flags are additive and idempotent — re-evaluating the same conversation never
duplicates a row, and a flag once raised is not silently withdrawn, because a
doctor may already have acted on it.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.clinical import Conversation, PatientResponse, RedFlag, Visit
from app.models.document import Investigation
from app.models.user import PatientProfile
from app.models.enums import PriorityLevel, Severity
from app.services.redflag.rules import RULES, Facts
from app.services.triage import priority_engine

log = get_logger(__name__)


def merge_facts(responses: list[PatientResponse]) -> Facts:
    """
    Flatten every structured answer into one dict.

    True wins: if the patient mentioned breathlessness at any point, the fact
    stays true even if a later answer did not repeat it.
    """
    facts: Facts = {}
    for response in responses:
        for key, value in (response.structured_value or {}).items():
            if key.startswith("_"):
                continue
            facts[key] = bool(facts.get(key)) or bool(value)
    return facts


def _evidence(facts: Facts, responses: list[PatientResponse], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """The patient's own words behind a flag, so the doctor can see the source."""
    out: list[dict[str, Any]] = []
    for key in keys:
        if not facts.get(key):
            continue
        for response in responses:
            if (response.structured_value or {}).get(key):
                out.append({"key": key, "category": response.category, "said": response.raw_text[:280]})
                break
    return out


async def evaluate_visit(db: AsyncSession, visit: Visit, conversation_id: uuid.UUID) -> list[RedFlag]:
    """Run every rule, persist any new flags, update the visit's priority."""
    responses = list(
        (await db.execute(select(PatientResponse).where(PatientResponse.conversation_id == conversation_id))).scalars()
    )
    facts = merge_facts(responses)

    existing = {
        flag.rule_id: flag
        for flag in (await db.execute(select(RedFlag).where(RedFlag.visit_id == visit.id))).scalars()
    }

    created: list[RedFlag] = []
    for rule in RULES:
        try:
            fired = rule.predicate(facts)
        except Exception as exc:  # noqa: BLE001 - a broken rule must not break intake
            log.error("Red-flag rule raised", extra={"extra": {"rule": rule.id, "error": str(exc)[:200]}})
            continue
        if not fired or rule.id in existing:
            continue

        flag = RedFlag(
            visit_id=visit.id,
            rule_id=rule.id,
            label=rule.label,
            detail=rule.detail,
            severity=rule.severity,
            evidence=_evidence(facts, responses, rule.evidence_keys),
            source="conversation",
        )
        db.add(flag)
        created.append(flag)
        log.info("Red flag raised", extra={"extra": {"rule": rule.id, "visit_id": str(visit.id)}})

    all_flags = list(existing.values()) + created
    await rescore(db, visit, facts=facts, flags=all_flags)
    await db.flush()
    return created


async def rescore(
    db: AsyncSession, visit: Visit, *, facts: Facts | None = None, flags: list[RedFlag] | None = None
) -> None:
    """
    Recompute the acuity score and band.

    Split out from evaluate_visit because the queue also calls it on read: a
    patient's waiting time keeps climbing after their last answer, and a score
    frozen at intake would let long waits go unnoticed.
    """
    if flags is None:
        flags = list((await db.execute(select(RedFlag).where(RedFlag.visit_id == visit.id))).scalars())

    if facts is None:
        conversation_id = (
            await db.execute(select(Conversation.id).where(Conversation.visit_id == visit.id))
        ).scalar_one_or_none()
        responses = (
            list(
                (
                    await db.execute(
                        select(PatientResponse).where(PatientResponse.conversation_id == conversation_id)
                    )
                ).scalars()
            )
            if conversation_id
            else []
        )
        facts = merge_facts(responses)

    profile = await db.get(PatientProfile, visit.patient_id)
    abnormal = int(
        (
            await db.execute(
                select(func.count(Investigation.id)).where(
                    Investigation.patient_id == visit.patient_id,
                    Investigation.abnormal_flag.in_(["high", "low"]),
                )
            )
        ).scalar_one()
        or 0
    )

    assessment = priority_engine.assess(
        facts=facts,
        flags=flags,
        age=profile.age if profile else None,
        waited_minutes=priority_engine.waited_minutes_for(visit),
        abnormal_investigations=abnormal,
    )
    visit.priority_score = assessment.score
    visit.priority_level = assessment.level
    visit.priority_factors = assessment.as_dict()["factors"]


def derive_priority(flags: list[RedFlag]) -> PriorityLevel:
    """Kept for the flag-only case; the queue uses the scored band above."""
    if any(flag.severity == Severity.PRIORITY for flag in flags):
        return PriorityLevel.PRIORITY
    if flags:
        return PriorityLevel.REVIEW
    return PriorityLevel.NORMAL
