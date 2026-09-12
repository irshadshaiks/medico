"""The doctor-facing record: summary, verification history, audit trail, ABDM log."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import Provenance, VerificationState


class ClinicalSummary(Base, UUIDMixin, TimestampMixin):
    """One draft summary per visit, composed of independently verifiable sections."""

    __tablename__ = "clinical_summaries"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visits.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    status: Mapped[VerificationState] = mapped_column(
        Enum(VerificationState, name="verification_state_enum", create_type=False),
        default=VerificationState.DRAFT, nullable=False, index=True,
    )
    generated_by: Mapped[str | None] = mapped_column(String(32))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_by_doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="SET NULL")
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    doctor_notes: Mapped[str | None] = mapped_column(Text)

    sections: Mapped[list["SummarySection"]] = relationship(
        back_populates="summary", cascade="all, delete-orphan", order_by="SummarySection.display_order"
    )


class SummarySection(Base, UUIDMixin, TimestampMixin):
    """
    A section is the unit a doctor accepts, edits or rejects. The AI's original
    text is never overwritten — `ai_body` and `doctor_body` sit side by side so
    the diff is always recoverable.
    """

    __tablename__ = "summary_sections"

    summary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_summaries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(48), nullable=False)
    label: Mapped[str] = mapped_column(String(96), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_body: Mapped[str | None] = mapped_column(Text)
    doctor_body: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[Provenance] = mapped_column(
        Enum(Provenance, name="provenance_enum", create_type=False), nullable=False
    )
    status: Mapped[VerificationState] = mapped_column(
        Enum(VerificationState, name="verification_state_enum", create_type=False),
        default=VerificationState.DRAFT, nullable=False,
    )
    # The exact records this section was composed from, so a doctor can ask
    # "where did that come from" and get an answer.
    source_refs: Mapped[list | None] = mapped_column(JSONB)

    summary: Mapped[ClinicalSummary] = relationship(back_populates="sections")

    __table_args__ = (Index("ix_section_summary_key", "summary_id", "key", unique=True),)

    @property
    def body(self) -> str | None:
        """What the doctor should read: their edit if there is one, else the draft."""
        return self.doctor_body or self.ai_body


class DoctorVerification(Base, UUIDMixin, TimestampMixin):
    """
    An immutable record of one human decision. Rows are only ever inserted.
    """

    __tablename__ = "doctor_verifications"

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctor_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # accept | edit | reject
    original_value: Mapped[str | None] = mapped_column(Text)
    verified_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """
    Append-only. Written by `AuditService` from a middleware hook and from the
    services that perform sensitive actions, so a new endpoint cannot silently
    skip it.
    """

    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    actor_role: Mapped[str | None] = mapped_column(String(24))
    event: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(48), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(255))
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)

    __table_args__ = (Index("ix_audit_entity_time", "entity_type", "entity_id", "created_at"),)


class AbdmSyncLog(Base, UUIDMixin, TimestampMixin):
    """Simulated only. Recorded so the demo can show what a real sync would log."""

    __tablename__ = "abdm_sync_logs"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("visits.id", ondelete="SET NULL"))
    operation: Mapped[str] = mapped_column(String(48), nullable=False)
    adapter: Mapped[str] = mapped_column(String(24), default="mock", nullable=False)
    simulated: Mapped[bool] = mapped_column(default=True, nullable=False)
    payload_preview: Mapped[dict | None] = mapped_column(JSONB)
