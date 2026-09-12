"""Uploaded documents, what OCR and extraction made of them, and the normalized result."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
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
from app.models.enums import DocumentType, HistoryType, OCRStatus, Provenance, VerificationState


class MedicalDocument(Base, UUIDMixin, TimestampMixin):
    """
    The original the patient walked in with. The file itself never leaves the
    storage backend un-proxied — `storage_key` is opaque and not web-reachable.
    """

    __tablename__ = "medical_documents"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(96), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    page_count: Mapped[int | None] = mapped_column(Integer)
    document_type: Mapped[DocumentType | None] = mapped_column(Enum(DocumentType, name="document_type_enum"))
    captured_via_camera: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    visit: Mapped["Visit"] = relationship(back_populates="documents")  # noqa: F821
    extraction: Mapped["DocumentExtraction | None"] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )


class DocumentExtraction(Base, UUIDMixin, TimestampMixin):
    """OCR output plus the structured fields pulled from it, with confidences."""

    __tablename__ = "document_extractions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_documents.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    ocr_status: Mapped[OCRStatus] = mapped_column(
        Enum(OCRStatus, name="ocr_status_enum"), default=OCRStatus.QUEUED, nullable=False, index=True
    )
    ocr_provider: Mapped[str | None] = mapped_column(String(32))
    raw_text: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    ocr_error: Mapped[str | None] = mapped_column(Text)

    # The AI's structured read, exactly as returned. Never edited in place —
    # doctor corrections live on DoctorVerification instead.
    structured_fields: Mapped[dict | None] = mapped_column(JSONB)
    overall_confidence: Mapped[float | None] = mapped_column(Float)
    extraction_provider: Mapped[str | None] = mapped_column(String(32))
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_state: Mapped[VerificationState] = mapped_column(
        Enum(VerificationState, name="verification_state_enum"),
        default=VerificationState.DRAFT, nullable=False,
    )

    document: Mapped[MedicalDocument] = relationship(back_populates="extraction")


class Medication(Base, UUIDMixin, TimestampMixin):
    """
    Normalized across every document and conversation for this patient.
    Two documents naming the same drug produce one row with two sources, not
    two rows — see `normalization_service`.
    """

    __tablename__ = "medications"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    dose: Mapped[str | None] = mapped_column(String(64))
    frequency: Mapped[str | None] = mapped_column(String(64))
    duration: Mapped[str | None] = mapped_column(String(64))
    started_on: Mapped[date | None] = mapped_column(Date)
    still_taking: Mapped[bool | None] = mapped_column(Boolean)
    provenance: Mapped[Provenance] = mapped_column(Enum(Provenance, name="provenance_enum", create_type=False), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    # Every document that mentioned this drug, for traceability.
    source_document_ids: Mapped[list | None] = mapped_column(JSONB)
    source_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    verification_state: Mapped[VerificationState] = mapped_column(
        Enum(VerificationState, name="verification_state_enum", create_type=False),
        default=VerificationState.DRAFT, nullable=False,
    )

    __table_args__ = (Index("ix_med_patient_norm", "patient_id", "normalized_name", unique=True),)


class Investigation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "investigations"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(String(64))
    unit: Mapped[str | None] = mapped_column(String(32))
    reference_range: Mapped[str | None] = mapped_column(String(64))
    # 'high' | 'low' | 'normal' | 'unclear' — read off the report, not computed.
    abnormal_flag: Mapped[str | None] = mapped_column(String(16), index=True)
    performed_on: Mapped[date | None] = mapped_column(Date)
    date_uncertain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provenance: Mapped[Provenance] = mapped_column(Enum(Provenance, name="provenance_enum", create_type=False), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    source_document_ids: Mapped[list | None] = mapped_column(JSONB)
    verification_state: Mapped[VerificationState] = mapped_column(
        Enum(VerificationState, name="verification_state_enum", create_type=False),
        default=VerificationState.DRAFT, nullable=False,
    )


class Allergy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "allergies"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    substance: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_substance: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    reaction: Mapped[str | None] = mapped_column(String(255))
    provenance: Mapped[Provenance] = mapped_column(Enum(Provenance, name="provenance_enum", create_type=False), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    source_document_ids: Mapped[list | None] = mapped_column(JSONB)
    verification_state: Mapped[VerificationState] = mapped_column(
        Enum(VerificationState, name="verification_state_enum", create_type=False),
        default=VerificationState.DRAFT, nullable=False,
    )

    __table_args__ = (Index("ix_allergy_patient_norm", "patient_id", "normalized_substance", unique=True),)


class MedicalHistoryEntry(Base, UUIDMixin, TimestampMixin):
    """
    One table for medical, surgical, family, personal and obstetric history,
    separated by `history_type` rather than by five near-identical tables.
    """

    __tablename__ = "medical_history_entries"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    history_type: Mapped[HistoryType] = mapped_column(
        Enum(HistoryType, name="history_type_enum"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    onset_date: Mapped[date | None] = mapped_column(Date)
    date_uncertain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provenance: Mapped[Provenance] = mapped_column(Enum(Provenance, name="provenance_enum", create_type=False), nullable=False)
    source_document_ids: Mapped[list | None] = mapped_column(JSONB)
    verification_state: Mapped[VerificationState] = mapped_column(
        Enum(VerificationState, name="verification_state_enum", create_type=False),
        default=VerificationState.DRAFT, nullable=False,
    )
