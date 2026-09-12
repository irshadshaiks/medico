"""
Enums shared across the schema.

`Provenance` is the important one: the brief requires every clinical fact to
carry a traceable origin, and it is a non-nullable column on every table that
holds one.
"""

from __future__ import annotations

import enum


class Role(str, enum.Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"


class Provenance(str, enum.Enum):
    PATIENT_PROVIDED = "PATIENT-PROVIDED"
    # A family member answered on the patient's behalf. Kept distinct because a
    # son reporting his mother's symptoms is genuinely less reliable than the
    # mother, and the doctor must be able to see which it was.
    ATTENDANT_REPORTED = "ATTENDANT-REPORTED"
    DOCUMENT_EXTRACTED = "DOCUMENT-EXTRACTED"
    AI_INFERRED = "AI-INFERRED"
    DOCTOR_VERIFIED = "DOCTOR-VERIFIED"


class VerificationState(str, enum.Enum):
    DRAFT = "draft"
    EDITED = "edited"
    VERIFIED = "verified"
    REJECTED = "rejected"


class VisitStatus(str, enum.Enum):
    INTAKE_STARTED = "intake_started"
    INTAKE_COMPLETE = "intake_complete"
    IN_REVIEW = "in_review"
    CONSULTED = "consulted"
    ABANDONED = "abandoned"


class PriorityLevel(str, enum.Enum):
    PRIORITY = "priority"
    REVIEW = "review"
    NORMAL = "normal"


class ConversationStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    # Intake stopped because an escalation rule fired. Distinct from ABANDONED:
    # the patient did not walk away, the system told them to.
    HALTED_ESCALATED = "halted_escalated"


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    PATIENT = "patient"


class DocumentType(str, enum.Enum):
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    DISCHARGE_SUMMARY = "discharge_summary"
    OTHER = "other"


class OCRStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Severity(str, enum.Enum):
    REVIEW = "review"
    PRIORITY = "priority"


class HistoryType(str, enum.Enum):
    MEDICAL = "medical"
    SURGICAL = "surgical"
    FAMILY = "family"
    PERSONAL = "personal"
    OBSTETRIC = "obstetric"


class ConsentScope(str, enum.Enum):
    INTAKE = "intake"
    DOCUMENT_PROCESSING = "document_processing"
    ABDM_SHARING = "abdm_sharing"


class Language(str, enum.Enum):
    EN = "en"
    HI = "hi"
    KN = "kn"
