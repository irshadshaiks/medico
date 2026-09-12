"""
Runs the ten-second safety screen that opens every intake.

This is the highest-value moment in the whole system. Before we know anything
about the patient, before a pathway is chosen, before a single clinical
question, we ask one multiple-choice question about what is happening right
now. If the answer matches an escalation rule, the intake ends here and the
patient is sent to Emergency.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound
from app.models.clinical import (
    Conversation,
    ConversationMessage,
    PatientResponse,
    Question,
    Visit,
)
from app.models.enums import ConversationStatus, Language, MessageRole, Provenance
from app.models.escalation import Escalation
from app.services.escalation import service as escalation_service
from app.services.escalation.screen_loader import load_screen
from app.services.questioning.pathway_engine import structure_answer

SCREEN_NODE_ID = "danger_now"


async def present(
    db: AsyncSession, *, visit: Visit, language: Language
) -> tuple[Conversation, Question]:
    """Create (or reuse) the conversation and return the screen question."""
    conversation = (
        await db.execute(select(Conversation).where(Conversation.visit_id == visit.id))
    ).scalar_one_or_none()

    if conversation is None:
        conversation = Conversation(
            visit_id=visit.id, language=language, detected_pathway=None,
            status=ConversationStatus.IN_PROGRESS,
        )
        db.add(conversation)
        await db.flush()

    existing_q = (
        await db.execute(
            select(Question).where(
                Question.conversation_id == conversation.id, Question.node_id == SCREEN_NODE_ID
            )
        )
    ).scalar_one_or_none()
    if existing_q is not None:
        return conversation, existing_q

    node = load_screen().nodes[0]
    question = Question(
        conversation_id=conversation.id,
        pathway="emergency_screen",
        node_id=node.id,
        category=node.category,
        canonical_text=node.question,
        # Never rephrased by the model. This question's exact wording is a
        # safety control; an LLM softening "right now" would defeat it.
        presented_text=node.question,
        phrasing_source="template",
        answer_type=node.answer_type,
        options=node.options,
    )
    db.add(question)
    await db.flush()

    db.add(
        ConversationMessage(
            conversation_id=conversation.id, sequence=1, role=MessageRole.SYSTEM,
            text=node.question, language=language,
        )
    )
    await db.flush()
    return conversation, question


async def submit(
    db: AsyncSession,
    *,
    visit: Visit,
    conversation_id: uuid.UUID,
    question_id: uuid.UUID,
    text: str,
    respondent: str = "patient",
    attendant_relationship: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> Escalation | None:
    """Record the screen answer and evaluate escalation. None means proceed."""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.visit_id != visit.id:
        raise NotFound("That intake session could not be found.")

    question = await db.get(Question, question_id)
    if question is None or question.node_id != SCREEN_NODE_ID:
        raise Conflict("That is not the safety screen question.")

    already = (
        await db.execute(
            select(PatientResponse).where(PatientResponse.question_id == question.id)
        )
    ).scalar_one_or_none()

    if already is None:
        node = load_screen().nodes[0]
        db.add(
            PatientResponse(
                conversation_id=conversation.id,
                question_id=question.id,
                category=question.category,
                raw_text=text,
                structured_value=structure_answer(node, text),
                provenance=(
                    Provenance.ATTENDANT_REPORTED if respondent == "attendant"
                    else Provenance.PATIENT_PROVIDED
                ),
                respondent=respondent,
                attendant_relationship=attendant_relationship,
            )
        )
        db.add(
            ConversationMessage(
                conversation_id=conversation.id, sequence=2, role=MessageRole.PATIENT,
                text=text, language=conversation.language,
            )
        )
        await db.flush()

    return await escalation_service.check(
        db, visit=visit, conversation=conversation, actor_id=actor_id
    )
