from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import Language
from app.schemas.conversation import QuestionOut


class SafetyScreenOut(BaseModel):
    conversation_id: uuid.UUID
    question: QuestionOut


class SafetyScreenAnswer(BaseModel):
    conversation_id: uuid.UUID
    question_id: uuid.UUID
    text: str = Field(min_length=1, max_length=1000)
    # Attendant mode: a family member answering for a patient who cannot.
    respondent: str = Field(default="patient", pattern="^(patient|attendant)$")
    attendant_relationship: str | None = Field(default=None, max_length=48)


class EscalationOut(BaseModel):
    """
    What the patient's screen shows.

    Contains an instruction and a destination, and deliberately no explanation
    of what the symptoms might mean. A patient told their chest pain "could be
    a heart attack" panics, and panic does not help anyone walk forty metres to
    Casualty.
    """

    escalated: bool
    id: uuid.UUID | None = None
    instruction: str | None = None
    destination: str | None = None
    # Shown small, so nobody mistakes a draft protocol for an approved one.
    clinically_signed_off: bool = True


class StaffEscalationOut(BaseModel):
    id: uuid.UUID
    visit_id: uuid.UUID
    patient_name: str
    patient_age: int | None
    rule_id: str
    staff_label: str
    destination: str
    evidence: list | None
    clinically_signed_off: bool
    raised_at: datetime
    waiting_seconds: int


class AcknowledgeRequest(BaseModel):
    outcome: str = Field(
        pattern="^(escorted_to_emergency|assessed_remained_in_opd|patient_declined|patient_not_found)$"
    )
    note: str | None = Field(default=None, max_length=1000)
