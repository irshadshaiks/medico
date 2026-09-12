"""
Models for the insider-misuse controls.

The threat here is not an outside attacker. It is a legitimate account —
a doctor with a valid login and a real reason to see *some* records — reading
or exporting patients they have no clinical relationship with, and selling
what they find. Perimeter security does nothing about that, because the
credential is genuine.

Three ideas carry the weight, and each needs a table:

  * Every read is recorded with a *declared purpose*, so access is bound to a
    stated reason rather than a role.
  * Patterns that look like harvesting raise an alert a human reviews.
  * Every export leaves a receipt with a unique watermark, so a leaked file
    can be traced back to the account and moment it left the system.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class AccessPurpose(str, enum.Enum):
    """
    Why this record is being opened. Declared by the clinician, recorded, and
    shown to the patient. Nothing here is inferred — a stated purpose the
    person can be held to is the point.
    """

    TREATMENT = "treatment"                  # patient is in this doctor's queue now
    CONTINUITY = "continuity_of_care"        # reviewing an earlier visit
    EMERGENCY = "emergency"                  # break-glass, reviewed afterwards
    QUALITY_AUDIT = "quality_audit"          # administrative review


class AccessDecision(str, enum.Enum):
    ALLOWED = "allowed"
    BREAK_GLASS = "break_glass"   # allowed, but outside the normal relationship
    THROTTLED = "throttled"       # allowed after a rate check flagged the pattern
    DENIED = "denied"


class AlertKind(str, enum.Enum):
    BULK_ACCESS = "bulk_access"              # many distinct patients, short window
    OFF_QUEUE_PATTERN = "off_queue_pattern"  # repeated break-glass
    EXPORT_VOLUME = "export_volume"          # repeated exports
    AFTER_HOURS_BULK = "after_hours_bulk"


class RecordAccess(Base, UUIDMixin, TimestampMixin):
    """
    One row per read of one patient's record. Append-only.

    This is what the patient sees on their own access log, which is the
    strongest deterrent in the whole design: misuse stops being invisible.
    """

    __tablename__ = "record_accesses"

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_name: Mapped[str | None] = mapped_column(String(160))
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visits.id", ondelete="SET NULL")
    )
    resource: Mapped[str] = mapped_column(String(48), nullable=False)  # case_file | document | timeline | export
    purpose: Mapped[AccessPurpose] = mapped_column(Enum(AccessPurpose, name="access_purpose_enum"), nullable=False)
    decision: Mapped[AccessDecision] = mapped_column(
        Enum(AccessDecision, name="access_decision_enum"), nullable=False, default=AccessDecision.ALLOWED
    )
    # Required when the patient is not in the actor's active queue.
    justification: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(255))
    request_id: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_access_patient_time", "patient_id", "created_at"),
        Index("ix_access_actor_time", "actor_id", "created_at"),
    )


class MisuseAlert(Base, UUIDMixin, TimestampMixin):
    """
    Raised by a rule over access patterns, not by a model.

    Deliberately does not block. A hard block on an unusual pattern would, on
    the day it matters, stop a doctor reading a record during an emergency.
    Raising a reviewable alert catches harvesting without that risk.
    """

    __tablename__ = "misuse_alerts"

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    kind: Mapped[AlertKind] = mapped_column(Enum(AlertKind, name="alert_kind_enum"), nullable=False, index=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    window_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSONB)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_note: Mapped[str | None] = mapped_column(Text)


class ExportReceipt(Base, UUIDMixin, TimestampMixin):
    """
    Proof that a specific person exported a specific record at a specific
    moment. The watermark is embedded in the exported bundle, so a file found
    somewhere it should not be can be traced to the account that produced it.
    """

    __tablename__ = "export_receipts"

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    actor_name: Mapped[str | None] = mapped_column(String(160))
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("visits.id", ondelete="SET NULL"))
    watermark: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # Hash of the exact bytes handed over, so a later dispute about what was in
    # the file has an answer.
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    section_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    purpose: Mapped[AccessPurpose] = mapped_column(
        Enum(AccessPurpose, name="access_purpose_enum", create_type=False), nullable=False
    )
    ip_address: Mapped[str | None] = mapped_column(INET)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
