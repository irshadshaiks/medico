from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    DocumentType,
    Language,
    OCRStatus,
    PriorityLevel,
    Provenance,
    VerificationState,
    VisitStatus,
)
from app.schemas.common import ORMModel


class VisitOut(ORMModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    chief_complaint: str | None
    status: VisitStatus
    priority_level: PriorityLevel
    language: Language
    department: str | None
    queued_at: datetime | None
    created_at: datetime


class DocumentOut(ORMModel):
    id: uuid.UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    page_count: int | None
    document_type: DocumentType | None
    created_at: datetime


class ExtractedField(BaseModel):
    label: str
    value: str
    confidence: float | None = None
    provenance: Provenance = Provenance.DOCUMENT_EXTRACTED


class ExtractionOut(ORMModel):
    id: uuid.UUID
    document_id: uuid.UUID
    ocr_status: OCRStatus
    ocr_confidence: float | None
    ocr_error: str | None
    raw_text: str | None
    structured_fields: dict | None
    overall_confidence: float | None
    verification_state: VerificationState
    extracted_at: datetime | None


class DocumentDetailOut(BaseModel):
    document: DocumentOut
    extraction: ExtractionOut | None
    # Short-lived S3 link, or null when the file must be proxied.
    download_url: str | None = None


class TimelineEventOut(BaseModel):
    id: str
    kind: str
    title: str
    detail: str
    provenance: Provenance
    occurred_on: date | None
    date_uncertain: bool = False
    current_visit: bool = False
    source_document_ids: list[str] = []


class SummarySectionOut(ORMModel):
    id: uuid.UUID
    key: str
    label: str
    display_order: int
    ai_body: str | None
    doctor_body: str | None
    body: str | None
    provenance: Provenance
    status: VerificationState
    source_refs: list | None


class SummaryOut(ORMModel):
    id: uuid.UUID
    visit_id: uuid.UUID
    status: VerificationState
    generated_by: str | None
    generated_at: datetime | None
    finalized_at: datetime | None
    doctor_notes: str | None
    sections: list[SummarySectionOut] = []
    # Rendered by the client as a persistent banner while any section is a draft.
    draft_notice: str = (
        "Draft prepared from patient intake. Not reviewed by a doctor. No diagnosis has been made."
    )


class VerifyRequest(BaseModel):
    section: str
    action: str = Field(pattern="^(accept|edit|reject)$")
    body: str | None = None
    reason: str | None = None


class FinalizeRequest(BaseModel):
    notes: str | None = None


class QueueEntryOut(BaseModel):
    visit_id: uuid.UUID
    patient_id: uuid.UUID
    name: str
    age: int | None
    sex: str | None
    chief_complaint: str | None
    queue: PriorityLevel
    flag_count: int
    language: Language
    waited_minutes: int
    status: VisitStatus
    summary_ready: bool
    # Explainable acuity score. The band is derived from it; both are shown.
    priority_score: int = 0
    priority_reason: str | None = None


class CaseFileOut(BaseModel):
    visit: VisitOut
    patient_name: str
    patient_age: int | None
    patient_sex: str | None
    red_flags: list = []
    priority_score: int = 0
    priority_factors: list = []
    summary: SummaryOut | None
    timeline: list[TimelineEventOut] = []
    documents: list[DocumentOut] = []


class AbhaLinkRequest(BaseModel):
    accept_simulation_notice: bool = True


class AbhaLinkOut(BaseModel):
    abha_id: str
    simulated: bool
    message: str
