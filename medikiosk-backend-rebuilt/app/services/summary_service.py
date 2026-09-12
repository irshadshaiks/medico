"""
Draft summary generation and the human verification layer.

Two rules shape this file:

  * The model is given structured records and asked to write prose about them.
    It is never given free rein, and a section whose underlying data is empty
    is written as empty rather than filled in.
  * A doctor's edit never overwrites the draft. `ai_body` and `doctor_body` sit
    side by side forever, so the diff between what the machine proposed and
    what the clinician signed is always recoverable.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import Conflict, Forbidden, NotFound
from app.core.logging import get_logger
from app.core.prompts import SUMMARY_SECTION, SUMMARY_SECTION_LENGTH
from app.models.clinical import Conversation, PatientResponse, Question, RedFlag, Visit
from app.models.document import Investigation, Medication
from app.models.enums import Provenance, VerificationState, VisitStatus
from app.models.record import ClinicalSummary, DoctorVerification, SummarySection
from app.services import audit_service
from app.services.ai.base import AICompletionRequest
from app.services.ai.factory import get_ai_service

log = get_logger(__name__)

SECTIONS: tuple[tuple[str, str, Provenance], ...] = (
    ("chief_complaint", "Chief complaint", Provenance.PATIENT_PROVIDED),
    ("history_of_present_illness", "History of present illness", Provenance.AI_INFERRED),
    ("past_history", "Past history", Provenance.PATIENT_PROVIDED),
    ("medications", "Current medication", Provenance.DOCUMENT_EXTRACTED),
    ("investigations", "Previous investigations", Provenance.DOCUMENT_EXTRACTED),
    ("red_flags", "Potential concerns for review", Provenance.AI_INFERRED),
)

EMPTY = {
    "chief_complaint": "No chief complaint was recorded during intake.",
    "history_of_present_illness": "Intake did not capture enough detail to describe the current problem.",
    "past_history": "No past history was recorded during intake.",
    "medications": "No current medication was recorded, and no prescription was uploaded.",
    "investigations": "No previous investigation results were found in the uploaded documents.",
    "red_flags": "No rule was triggered during intake.",
}


async def _gather(db: AsyncSession, visit: Visit) -> dict[str, dict]:
    """Collect the structured inputs each section is allowed to draw on."""
    conversation = (
        await db.execute(select(Conversation).where(Conversation.visit_id == visit.id))
    ).scalar_one_or_none()

    answers: list[dict] = []
    if conversation:
        rows = await db.execute(
            select(PatientResponse, Question)
            .join(Question, PatientResponse.question_id == Question.id)
            .where(PatientResponse.conversation_id == conversation.id)
            .order_by(PatientResponse.created_at)
        )
        answers = [
            {"category": response.category, "asked": question.canonical_text, "answered": response.raw_text}
            for response, question in rows.all()
        ]

    by_category = lambda cats: [a for a in answers if a["category"] in cats]  # noqa: E731

    medications = list(
        (await db.execute(select(Medication).where(Medication.patient_id == visit.patient_id))).scalars()
    )
    investigations = list(
        (await db.execute(select(Investigation).where(Investigation.patient_id == visit.patient_id))).scalars()
    )
    flags = list((await db.execute(select(RedFlag).where(RedFlag.visit_id == visit.id))).scalars())

    return {
        "chief_complaint": {"complaint": visit.chief_complaint, "answers": by_category({"chief_complaint"})},
        "history_of_present_illness": {
            "answers": by_category(
                {"site", "character", "onset", "duration", "severity", "course",
                 "aggravating_factors", "relieving_factors", "radiation", "associated_symptoms"}
            )
        },
        "past_history": {"answers": by_category({"past_history", "personal_history", "allergies"})},
        "medications": {
            "answers": by_category({"medications"}),
            "records": [
                {"name": m.name, "dose": m.dose, "frequency": m.frequency,
                 "sources": m.source_count, "confidence": m.confidence}
                for m in medications
            ],
        },
        "investigations": {
            "records": [
                {"name": i.name, "value": i.value, "unit": i.unit, "reference": i.reference_range,
                 "flag": i.abnormal_flag, "date": str(i.performed_on) if i.performed_on else None}
                for i in investigations
            ]
        },
        "red_flags": {
            "flags": [
                {"rule": f.rule_id, "label": f.label, "severity": f.severity.value, "evidence": f.evidence}
                for f in flags
            ]
        },
    }


def _has_content(payload: dict) -> bool:
    return any(bool(value) for value in payload.values())


async def generate(db: AsyncSession, *, visit: Visit, actor_id: uuid.UUID | None = None) -> ClinicalSummary:
    """
    Draft every section. Regenerating is safe: sections a doctor has already
    accepted, edited or rejected are left alone, so new intake data never
    silently undoes a clinician's decision.
    """
    summary = (
        await db.execute(
            select(ClinicalSummary)
            .options(selectinload(ClinicalSummary.sections))
            .where(ClinicalSummary.visit_id == visit.id)
        )
    ).scalar_one_or_none()

    if summary is None:
        summary = ClinicalSummary(visit_id=visit.id, status=VerificationState.DRAFT)
        db.add(summary)
        await db.flush()

    if summary.status is VerificationState.VERIFIED:
        raise Conflict("This summary has been finalised and cannot be regenerated.")

    data = await _gather(db, visit)
    existing = {section.key: section for section in summary.sections}
    ai = get_ai_service()

    for order, (key, label, provenance) in enumerate(SECTIONS):
        current = existing.get(key)
        if current and current.status is not VerificationState.DRAFT:
            continue  # a doctor has already ruled on this section

        payload = data.get(key, {})
        if not _has_content(payload):
            body = EMPTY[key]
        else:
            response = await ai.complete(
                AICompletionRequest(
                    prompt=SUMMARY_SECTION.format(
                        section=key,
                        length=SUMMARY_SECTION_LENGTH.get(key, "Two to four sentences."),
                        data=_render(payload),
                    ),
                    temperature=0.15,
                    max_output_tokens=500,
                ),
                fallback=EMPTY[key],
            )
            body = response.text

        if current:
            current.ai_body = body
            current.source_refs = _refs(payload)
        else:
            db.add(
                SummarySection(
                    summary_id=summary.id, key=key, label=label, display_order=order,
                    ai_body=body, provenance=provenance, status=VerificationState.DRAFT,
                    source_refs=_refs(payload),
                )
            )

    summary.generated_by = ai.name
    summary.generated_at = datetime.now(UTC)
    if visit.status is VisitStatus.INTAKE_COMPLETE:
        visit.status = VisitStatus.IN_REVIEW
    await db.flush()

    await audit_service.record(
        db, event=audit_service.AuditEvent.SUMMARY_GENERATED, actor_id=actor_id,
        entity_type="summary", entity_id=summary.id,
        summary=f"Draft summary generated by {ai.name}.",
    )
    return summary


def _render(payload: dict) -> str:
    import json

    return json.dumps(payload, indent=2, default=str)[:6000]


def _refs(payload: dict) -> list[dict]:
    refs: list[dict] = []
    for answer in payload.get("answers", []) or []:
        refs.append({"type": "response", "category": answer.get("category")})
    for record in payload.get("records", []) or []:
        refs.append({"type": "record", "name": record.get("name")})
    for flag in payload.get("flags", []) or []:
        refs.append({"type": "red_flag", "rule": flag.get("rule")})
    return refs


# --------------------------------------------------------------- verification --


async def verify_section(
    db: AsyncSession,
    *,
    summary_id: uuid.UUID,
    section_key: str,
    action: str,
    doctor_id: uuid.UUID,
    body: str | None = None,
    reason: str | None = None,
) -> SummarySection:
    summary = (
        await db.execute(
            select(ClinicalSummary).options(selectinload(ClinicalSummary.sections)).where(ClinicalSummary.id == summary_id)
        )
    ).scalar_one_or_none()
    if summary is None:
        raise NotFound("That summary could not be found.")
    if summary.status is VerificationState.VERIFIED:
        raise Conflict("This summary is finalised. Reopen it before making further changes.")

    section = next((s for s in summary.sections if s.key == section_key), None)
    if section is None:
        raise NotFound(f"This summary has no '{section_key}' section.")

    original = section.body

    if action == "accept":
        section.status = VerificationState.VERIFIED
        section.provenance = Provenance.DOCTOR_VERIFIED
    elif action == "edit":
        if not body or not body.strip():
            raise Conflict("An edited section needs some text. To remove it, reject it instead.")
        section.doctor_body = body.strip()
        section.status = VerificationState.EDITED
        section.provenance = Provenance.DOCTOR_VERIFIED
    elif action == "reject":
        section.status = VerificationState.REJECTED
    else:
        raise Conflict(f"'{action}' is not a verification action.")

    db.add(
        DoctorVerification(
            doctor_id=doctor_id, visit_id=summary.visit_id, entity_type="summary_section",
            entity_id=section.id, action=action, original_value=original,
            verified_value=section.body, reason=reason,
        )
    )
    await db.flush()

    await audit_service.record(
        db, event=audit_service.AuditEvent.SUMMARY_SECTION_VERIFIED, actor_id=doctor_id,
        actor_role="doctor", entity_type="summary_section", entity_id=section.id,
        summary=f"{action} on '{section_key}'.",
        before={"body": (original or "")[:2000]}, after={"body": (section.body or "")[:2000]},
    )
    return section


async def finalize(
    db: AsyncSession, *, summary_id: uuid.UUID, doctor_id: uuid.UUID, notes: str | None = None
) -> ClinicalSummary:
    """
    Lock the record. Refuses while any section is still an untouched draft —
    finalising means a human read all of it, and the check enforces that
    rather than trusting it.
    """
    summary = (
        await db.execute(
            select(ClinicalSummary).options(selectinload(ClinicalSummary.sections)).where(ClinicalSummary.id == summary_id)
        )
    ).scalar_one_or_none()
    if summary is None:
        raise NotFound("That summary could not be found.")

    unreviewed = [s.label for s in summary.sections if s.status is VerificationState.DRAFT]
    if unreviewed:
        raise Conflict("Review every section before finalising. Still open: " + ", ".join(unreviewed) + ".")

    summary.status = VerificationState.VERIFIED
    summary.finalized_by_doctor_id = doctor_id
    summary.finalized_at = datetime.now(UTC)
    if notes:
        summary.doctor_notes = notes

    visit = await db.get(Visit, summary.visit_id)
    if visit:
        visit.status = VisitStatus.CONSULTED
        visit.consulted_at = datetime.now(UTC)
    await db.flush()

    await audit_service.record(
        db, event=audit_service.AuditEvent.SUMMARY_FINALIZED, actor_id=doctor_id, actor_role="doctor",
        entity_type="summary", entity_id=summary.id, summary="Record verified and locked by the doctor.",
    )
    return summary
