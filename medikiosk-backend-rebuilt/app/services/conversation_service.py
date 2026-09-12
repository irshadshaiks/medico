"""
Conversation orchestration.

The backend owns the state. The client posts an answer and is told what to show
next; it never decides what comes next itself, and a refresh mid-intake resumes
exactly where the patient left off because the cursor lives in the database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import Conflict, Forbidden, NotFound
from app.core.logging import get_logger
from app.models.clinical import (
    Conversation,
    ConversationMessage,
    PatientResponse,
    Question,
    RedFlag,
    Visit,
)
from app.models.enums import (
    ConsentScope,
    ConversationStatus,
    Language,
    MessageRole,
    Provenance,
    VisitStatus,
)
from app.models.user import Consent
from app.services import audit_service
from app.services.questioning.complaint_classifier import classify_complaint
from app.services.questioning.pathway_engine import (
    AnsweredNode,
    build_next_question,
    structure_answer,
)
from app.services.questioning.schema import get_pathway
from app.services.escalation import service as escalation_service
from app.services.escalation.screen_loader import load_screen
from app.services.redflag.redflag_service import evaluate_visit

log = get_logger(__name__)


async def _require_intake_consent(db: AsyncSession, visit: Visit) -> None:
    """No consent, no intake. Checked here rather than at the route, so every
    entry point into the conversation is covered by the same gate."""
    result = await db.execute(
        select(Consent).where(
            Consent.visit_id == visit.id,
            Consent.scope == ConsentScope.INTAKE,
            Consent.granted.is_(True),
            Consent.withdrawn_at.is_(None),
        )
    )
    if result.scalar_one_or_none() is None:
        raise Forbidden("Intake consent has not been given for this visit.")


async def get_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages), selectinload(Conversation.visit))
        .where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise NotFound("That intake session could not be found.")
    return conversation


async def _answered_nodes(db: AsyncSession, conversation_id: uuid.UUID) -> list[AnsweredNode]:
    result = await db.execute(
        select(PatientResponse, Question)
        .join(Question, PatientResponse.question_id == Question.id)
        .where(PatientResponse.conversation_id == conversation_id)
        .order_by(PatientResponse.created_at)
    )
    return [
        AnsweredNode(
            node_id=question.node_id,
            category=response.category,
            raw_text=response.raw_text,
            structured=response.structured_value or {},
        )
        for response, question in result.all()
    ]


async def _next_sequence(db: AsyncSession, conversation_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(ConversationMessage.sequence), 0)).where(
            ConversationMessage.conversation_id == conversation_id
        )
    )
    return int(result.scalar_one()) + 1


async def start(
    db: AsyncSession,
    *,
    visit: Visit,
    chief_complaint: str,
    language: Language,
    actor_id: uuid.UUID,
) -> tuple[Conversation, Question | None, str | None]:
    """
    Begin intake. The complaint routes to a pathway, and the first question is
    asked immediately so the patient is never shown an empty screen.
    """
    await _require_intake_consent(db, visit)

    existing = (
        await db.execute(select(Conversation).where(Conversation.visit_id == visit.id))
    ).scalar_one_or_none()

    if existing is not None:
        if existing.status is ConversationStatus.HALTED_ESCALATED:
            # The safety screen already sent this patient to Casualty. Starting
            # a clinical interview now would be exactly the wrong thing.
            raise Conflict("This intake was stopped and the patient was directed to Emergency.")
        if existing.detected_pathway is not None:
            raise Conflict("Intake has already been started for this visit.")

    pathway_id, decided_by = await classify_complaint(chief_complaint)
    log.info(
        "Pathway selected",
        extra={"extra": {"pathway": pathway_id, "decided_by": decided_by, "visit_id": str(visit.id)}},
    )

    if existing is not None:
        # Reuse the conversation the safety screen opened, so the screen answer
        # and the clinical answers live in one transcript.
        conversation = existing
        conversation.detected_pathway = pathway_id
        conversation.language = language
    else:
        conversation = Conversation(
            visit_id=visit.id, language=language, detected_pathway=pathway_id,
            status=ConversationStatus.IN_PROGRESS,
        )
        db.add(conversation)
    visit.chief_complaint = chief_complaint
    visit.status = VisitStatus.INTAKE_STARTED
    visit.language = language
    await db.flush()

    # The complaint itself is the patient's first turn, recorded verbatim.
    db.add(
        ConversationMessage(
            conversation_id=conversation.id,
            sequence=1,
            role=MessageRole.PATIENT,
            text=chief_complaint,
            language=language,
        )
    )
    await db.flush()

    question, presented = await ask_next(db, conversation)
    await audit_service.record(
        db,
        event=audit_service.AuditEvent.CONVERSATION_STARTED,
        actor_id=actor_id,
        actor_role="patient",
        entity_type="conversation",
        entity_id=conversation.id,
        summary=f"Intake started on the '{pathway_id}' pathway ({decided_by}).",
    )
    return conversation, question, presented


async def ask_next(db: AsyncSession, conversation: Conversation) -> tuple[Question | None, str | None]:
    """
    Produce and persist the next question, or close the conversation.
    Safe to call twice: an unanswered question is returned again rather than
    a second one being generated.
    """
    pending = await db.execute(
        select(Question)
        .outerjoin(PatientResponse, PatientResponse.question_id == Question.id)
        .where(Question.conversation_id == conversation.id, PatientResponse.id.is_(None))
        .order_by(Question.created_at.desc())
        .limit(1)
    )
    outstanding = pending.scalar_one_or_none()
    if outstanding is not None:
        return outstanding, outstanding.presented_text

    answered = await _answered_nodes(db, conversation.id)
    nxt = await build_next_question(
        conversation.detected_pathway or "generic", answered, conversation.language.value
    )

    if nxt is None:
        conversation.status = ConversationStatus.COMPLETED
        conversation.completed_at = datetime.now(UTC)
        visit = conversation.visit or await db.get(Visit, conversation.visit_id)
        if visit and visit.status == VisitStatus.INTAKE_STARTED:
            visit.status = VisitStatus.INTAKE_COMPLETE
            visit.queued_at = datetime.now(UTC)
        await db.flush()
        return None, None

    question = Question(
        conversation_id=conversation.id,
        pathway=conversation.detected_pathway or "generic",
        node_id=nxt.node.id,
        category=nxt.node.category,
        canonical_text=nxt.node.question,
        presented_text=nxt.presented_text,
        phrasing_source=nxt.phrasing_source,
        answer_type=nxt.node.answer_type,
        options=nxt.node.options,
    )
    db.add(question)
    conversation.current_step_index = nxt.step_index
    await db.flush()

    db.add(
        ConversationMessage(
            conversation_id=conversation.id,
            sequence=await _next_sequence(db, conversation.id),
            role=MessageRole.SYSTEM,
            text=nxt.presented_text,
            language=conversation.language,
        )
    )
    await db.flush()
    return question, nxt.presented_text


async def submit_answer(
    db: AsyncSession,
    *,
    conversation: Conversation,
    question_id: uuid.UUID,
    text: str,
    via_voice: bool,
    client_token: str | None,
    actor_id: uuid.UUID,
) -> tuple[list[RedFlag], Question | None, str | None]:
    """Record an answer, re-run the rules, and hand back the next question."""
    if conversation.status is not ConversationStatus.IN_PROGRESS:
        raise Conflict("This intake session is already closed.")

    question = await db.get(Question, question_id)
    if question is None or question.conversation_id != conversation.id:
        raise NotFound("That question does not belong to this intake session.")

    # Idempotency: a retried request with the same token updates its own row
    # rather than appending a duplicate answer.
    if client_token:
        dupe = await db.execute(
            select(PatientResponse).where(
                PatientResponse.conversation_id == conversation.id,
                PatientResponse.client_token == client_token,
            )
        )
        existing = dupe.scalar_one_or_none()
        if existing is not None:
            question_next, presented = await ask_next(db, conversation)
            return [], question_next, presented

    pathway = get_pathway(question.pathway)
    node = next((n for n in pathway.nodes if n.id == question.node_id), None)
    structured = structure_answer(node, text) if node else {}

    db.add(
        PatientResponse(
            conversation_id=conversation.id,
            question_id=question.id,
            category=question.category,
            raw_text=text,
            structured_value=structured,
            provenance=Provenance.PATIENT_PROVIDED,
            via_voice=via_voice,
            client_token=client_token,
        )
    )
    db.add(
        ConversationMessage(
            conversation_id=conversation.id,
            sequence=await _next_sequence(db, conversation.id),
            role=MessageRole.PATIENT,
            text=text,
            language=conversation.language,
            via_voice=via_voice,
        )
    )
    await db.flush()

    visit = conversation.visit or await db.get(Visit, conversation.visit_id)

    # Escalation first. If this answer means the patient should not be in the
    # queue at all, nothing else about the interview matters.
    escalation = await escalation_service.check(
        db, visit=visit, conversation=conversation, actor_id=actor_id
    )
    if escalation is not None:
        await evaluate_visit(db, visit, conversation.id)
        return [], None, None

    new_flags = await evaluate_visit(db, visit, conversation.id)
    for flag in new_flags:
        await audit_service.record(
            db,
            event=audit_service.AuditEvent.RED_FLAG_RAISED,
            actor_id=actor_id,
            actor_role="patient",
            entity_type="visit",
            entity_id=visit.id,
            summary=flag.label,
            after={"rule_id": flag.rule_id, "severity": flag.severity.value},
        )

    next_question, presented = await ask_next(db, conversation)
    if next_question is None:
        await audit_service.record(
            db,
            event=audit_service.AuditEvent.CONVERSATION_COMPLETED,
            actor_id=actor_id,
            actor_role="patient",
            entity_type="conversation",
            entity_id=conversation.id,
        )
    return new_flags, next_question, presented
