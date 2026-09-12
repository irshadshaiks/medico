"""
Import every model here.

Alembic autogenerate and `Base.metadata` only see what has been imported, so a
model missing from this list silently vanishes from migrations.
"""

from app.db.base import Base
from app.models.access import ExportReceipt, MisuseAlert, RecordAccess
from app.models.escalation import Escalation
from app.models.clinical import (
    Conversation,
    ConversationMessage,
    PatientResponse,
    Question,
    RedFlag,
    Visit,
)
from app.models.document import (
    Allergy,
    DocumentExtraction,
    Investigation,
    Medication,
    MedicalDocument,
    MedicalHistoryEntry,
)
from app.models.record import (
    AbdmSyncLog,
    AuditLog,
    ClinicalSummary,
    DoctorVerification,
    SummarySection,
)
from app.models.user import Consent, DoctorProfile, PatientProfile, RefreshToken, User

__all__ = [
    "Base",
    "User", "PatientProfile", "DoctorProfile", "RefreshToken", "Consent",
    "Visit", "Conversation", "ConversationMessage", "Question", "PatientResponse", "RedFlag",
    "MedicalDocument", "DocumentExtraction", "Medication", "Investigation", "Allergy",
    "MedicalHistoryEntry",
    "ClinicalSummary", "SummarySection", "DoctorVerification", "AuditLog", "AbdmSyncLog",
    "RecordAccess", "MisuseAlert", "ExportReceipt",
    "Escalation",
]
