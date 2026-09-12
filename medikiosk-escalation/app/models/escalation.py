"""
The escalation record.

Separate from RedFlag on purpose. A red flag is a queue signal; an escalation
is an instruction to leave the queue, and the two have different lifecycles:
a flag is read by whichever doctor eventually sees the patient, an escalation
must be acknowledged by a named staff member within minutes or it has failed.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class EscalationStatus(str, enum.Enum):
    RAISED = "raised"
    ACKNOWLEDGED = "acknowledged"


class EscalationOutcome(str, enum.Enum):
    """What staff actually did. Recorded to measure the false-positive rate."""

    ESCORTED = "escorted_to_emergency"
    ASSESSED_STAYED = "assessed_remained_in_opd"
    PATIENT_DECLINED = "patient_declined"
    NOT_FOUND = "patient_not_found"


class Escalation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "escalations"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    staff_label: Mapped[str] = mapped_column(String(200), nullable=False)
    destination: Mapped[str] = mapped_column(String(96), nullable=False)
    patient_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    # The patient's own words behind it, so staff can see why in one glance.
    evidence: Mapped[list | None] = mapped_column(JSONB)
    matched_rules: Mapped[list | None] = mapped_column(JSONB)
    # False until a named clinician reviews the rule. Surfaced on the staff
    # screen so nobody mistakes a draft protocol for an approved one.
    clinically_signed_off: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    status: Mapped[EscalationStatus] = mapped_column(
        Enum(EscalationStatus, name="escalation_status_enum"),
        default=EscalationStatus.RAISED, nullable=False, index=True,
    )
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(48))
    outcome_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_escalation_open", "status", "created_at"),)
