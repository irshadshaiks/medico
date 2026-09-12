"""The visit and everything the conversational intake produces."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    ConversationStatus,
    Language,
    MessageRole,
    PriorityLevel,
    Provenance,
    Severity,
    VisitStatus,
)


class Visit(Base, UUIDMixin, TimestampMixin):
    """One trip to the OPD. Everything an intake produces hangs off this."""

    __tablename__ = "visits"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="SET NULL"), index=True
    )
    department: Mapped[str | None] = mapped_column(String(120))
    chief_complaint: Mapped[str | None] = mapped_column(Text)
    status: Mapped[VisitStatus] = mapped_column(
        Enum(VisitStatus, name="visit_status_enum"), default=VisitStatus.INTAKE_STARTED, nullable=False, index=True
    )
    # Set by the deterministic red-flag engine, never by a model.
    priority_level: Mapped[PriorityLevel] = mapped_column(
        Enum(PriorityLevel, name="priority_level_enum"), default=PriorityLevel.NORMAL, nullable=False, index=True
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, name="language_enum", create_type=False), default=Language.EN, nullable=False
    )
    # Explainable acuity score from app/services/triage/priority_engine.py.
    # priority_level is the band; these two are the "why" behind it.
    priority_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority_factors: Mapped[list | None] = mapped_column(JSONB)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consulted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped["PatientProfile"] = relationship(back_populates="visits")  # noqa: F821
    conversation: Mapped["Conversation | None"] = relationship(
        back_populates="visit", uselist=False, cascade="all, delete-orphan"
    )
    documents: Mapped[list["MedicalDocument"]] = relationship(  # noqa: F821
        back_populates="visit", cascade="all, delete-orphan"
    )
    red_flags: Mapped[list["RedFlag"]] = relationship(back_populates="visit", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_visits_queue", "status", "priority_level", "queued_at"),)


class Conversation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conversations"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visits.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, name="conversation_status_enum"),
        default=ConversationStatus.IN_PROGRESS,
        nullable=False,
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, name="language_enum", create_type=False), default=Language.EN, nullable=False
    )
    # Which pathway JSON is driving this conversation.
    detected_pathway: Mapped[str | None] = mapped_column(String(64), index=True)
    # Cursor into that pathway. Backend-authoritative: the client never decides
    # what comes next, it only renders what it is handed.
    current_step_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    visit: Mapped[Visit] = relationship(back_populates="conversation")
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.sequence"
    )
    responses: Mapped[list["PatientResponse"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ConversationMessage(Base, UUIDMixin, TimestampMixin):
    """The transcript, exactly as it appeared on screen."""

    __tablename__ = "conversation_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role_enum"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[Language] = mapped_column(
        Enum(Language, name="language_enum", create_type=False), default=Language.EN, nullable=False
    )
    # True when the patient answered by voice rather than by typing.
    via_voice: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_messages_conv_seq", "conversation_id", "sequence", unique=True),)


class Question(Base, UUIDMixin, TimestampMixin):
    """
    A question the engine actually asked, with the pathway node it came from.
    Stored so the pathway that produced a given history can be reconstructed.
    """

    __tablename__ = "questions"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pathway: Mapped[str] = mapped_column(String(64), nullable=False)
    node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # What the pathway file says, before any rephrasing.
    canonical_text: Mapped[str] = mapped_column(Text, nullable=False)
    # What the patient was actually shown, after LLM phrasing (or the fallback).
    presented_text: Mapped[str] = mapped_column(Text, nullable=False)
    phrasing_source: Mapped[str] = mapped_column(String(16), default="template", nullable=False)
    answer_type: Mapped[str] = mapped_column(String(24), default="text", nullable=False)
    options: Mapped[list | None] = mapped_column(JSONB)


class PatientResponse(Base, UUIDMixin, TimestampMixin):
    """
    The answer, raw and structured. `structured_value` is what the red-flag
    rules read, so the rules never have to parse free text at decision time.
    """

    __tablename__ = "patient_responses"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_value: Mapped[dict | None] = mapped_column(JSONB)
    provenance: Mapped[Provenance] = mapped_column(
        Enum(Provenance, name="provenance_enum"), default=Provenance.PATIENT_PROVIDED, nullable=False
    )
    via_voice: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Idempotency: a retried submission with the same key updates, not duplicates.
    client_token: Mapped[str | None] = mapped_column(String(64), index=True)
    # "patient" | "attendant". A patient too unwell, too elderly or too
    # distressed to use the kiosk almost always has family beside them who can
    # answer. Recorded so the doctor knows whose account they are reading.
    respondent: Mapped[str] = mapped_column(String(16), default="patient", nullable=False)
    attendant_relationship: Mapped[str | None] = mapped_column(String(48))

    conversation: Mapped[Conversation] = relationship(back_populates="responses")


class RedFlag(Base, UUIDMixin, TimestampMixin):
    """
    Raised by a deterministic rule, never by a model. `rule_id` and `evidence`
    together make every flag explainable to the doctor who sees it.
    """

    __tablename__ = "red_flags"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity, name="severity_enum"), nullable=False)
    # Which responses caused it to fire.
    evidence: Mapped[list | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(24), default="conversation", nullable=False)
    acknowledged_by_doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="SET NULL")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    visit: Mapped[Visit] = relationship(back_populates="red_flags")

    __table_args__ = (Index("ix_redflag_visit_rule", "visit_id", "rule_id", unique=True),)
