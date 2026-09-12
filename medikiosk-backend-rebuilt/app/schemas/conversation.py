from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ConversationStatus, Language, MessageRole, Provenance, Severity
from app.schemas.common import ORMModel


class ConsentRequest(BaseModel):
    scope: str = "intake"
    granted: bool
    language_shown: Language = Language.EN
    consent_text_version: str = "v1"
    consent_text: str | None = None


class StartIntakeRequest(BaseModel):
    chief_complaint: str = Field(min_length=2, max_length=2000)
    language: Language = Language.EN
    department: str | None = None


class QuestionOut(ORMModel):
    id: uuid.UUID
    category: str
    presented_text: str
    answer_type: str
    options: list[str] | None = None


class AnswerRequest(BaseModel):
    question_id: uuid.UUID
    text: str = Field(min_length=1, max_length=4000)
    via_voice: bool = False
    # Client-generated; makes a retried submission idempotent.
    client_token: str | None = Field(default=None, max_length=64)


class RedFlagOut(ORMModel):
    id: uuid.UUID
    rule_id: str
    label: str
    detail: str
    severity: Severity
    evidence: list | None = None
    created_at: datetime


class MessageOut(ORMModel):
    sequence: int
    role: MessageRole
    text: str
    via_voice: bool
    created_at: datetime


class ConversationOut(ORMModel):
    id: uuid.UUID
    visit_id: uuid.UUID
    status: ConversationStatus
    language: Language
    detected_pathway: str | None
    current_step_index: int
    messages: list[MessageOut] = []


class NextQuestionOut(BaseModel):
    conversation_id: uuid.UUID
    status: ConversationStatus
    question: QuestionOut | None
    step_index: int
    total_steps: int
    # Non-diagnostic by construction — see app/services/redflag/rules.py.
    new_red_flags: list[RedFlagOut] = []
    complete: bool = False
