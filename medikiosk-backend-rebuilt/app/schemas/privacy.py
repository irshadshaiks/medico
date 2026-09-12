from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import Language


class AccessLogEntryOut(BaseModel):
    id: uuid.UUID
    accessed_by: str
    role: str
    resource: str
    purpose: str
    # True when the record was opened outside a normal clinical relationship.
    unusual: bool
    reason_given: str | None
    occurred_at: datetime


class ExportReceiptOut(BaseModel):
    id: uuid.UUID
    exported_by: str
    watermark: str
    section_count: int
    purpose: str
    occurred_at: datetime
    revoked_at: datetime | None


class SharingConsentRequest(BaseModel):
    granted: bool
    language_shown: Language | None = None
    consent_text: str | None = None


class SharingConsentOut(BaseModel):
    granted: bool
    granted_at: datetime | None
    withdrawn_at: datetime | None
    explanation: str


class MisuseAlertOut(BaseModel):
    id: uuid.UUID
    kind: str
    actor_name: str
    actor_email: str | None
    detail: str
    observed_count: int
    threshold: int
    window_minutes: int
    created_at: datetime
    reviewed_at: datetime | None
    review_note: str | None


class ReviewAlertRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class OpenCaseRequest(BaseModel):
    """
    Sent when a doctor opens a case file.

    Purpose is mandatory, and a free-text justification is required whenever the
    patient is not already in this doctor's queue. Both are recorded and shown
    to the patient on their access log.
    """

    purpose: str = Field(
        default="treatment", pattern="^(treatment|continuity_of_care|emergency|quality_audit)$"
    )
    justification: str | None = Field(default=None, max_length=2000)
