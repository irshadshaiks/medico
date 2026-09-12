"""Initial MediKiosk schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-09

Enum types are created explicitly at the top rather than being inferred per
column. Several tables share `provenance_enum` and `verification_state_enum`,
and letting Alembic create them implicitly makes the second table fail with
"type already exists".
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


ENUMS = {
    "role_enum": ("patient", "doctor", "admin"),
    "language_enum": ("en", "hi", "kn"),
    "provenance_enum": ("PATIENT-PROVIDED", "DOCUMENT-EXTRACTED", "AI-INFERRED", "DOCTOR-VERIFIED"),
    "verification_state_enum": ("draft", "edited", "verified", "rejected"),
    "visit_status_enum": ("intake_started", "intake_complete", "in_review", "consulted", "abandoned"),
    "priority_level_enum": ("priority", "review", "normal"),
    "conversation_status_enum": ("in_progress", "completed", "abandoned"),
    "message_role_enum": ("system", "patient"),
    "document_type_enum": ("prescription", "lab_report", "discharge_summary", "other"),
    "ocr_status_enum": ("queued", "processing", "done", "failed"),
    "severity_enum": ("review", "priority"),
    "history_type_enum": ("medical", "surgical", "family", "personal", "obstetric"),
    "consent_scope_enum": ("intake", "document_processing", "abdm_sharing"),
}


def _enum(name: str) -> postgresql.ENUM:
    """Reference an already-created type; never emit CREATE TYPE again."""
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    # gen_random_uuid() lives here on PostgreSQL 13+.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    # ------------------------------------------------------------ identity --
    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("role", _enum("role_enum"), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("preferred_language", _enum("language_enum"), nullable=False, server_default="en"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    op.create_table(
        "patient_profiles",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("date_of_birth", sa.Date),
        sa.Column("sex", sa.String(16)),
        sa.Column("blood_group", sa.String(8)),
        sa.Column("address_district", sa.String(120)),
        sa.Column("emergency_contact", sa.String(120)),
        sa.Column("abha_id", sa.String(32)),
        sa.Column("abha_linked_at", sa.DateTime(timezone=True)),
        sa.Column("consent_withdrawn_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_patient_profiles_abha_id", "patient_profiles", ["abha_id"])

    op.create_table(
        "doctor_profiles",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("registration_number", sa.String(64)),
        sa.Column("department", sa.String(120)),
        sa.Column("designation", sa.String(120)),
        *_timestamps(),
    )
    op.create_index("ix_doctor_profiles_department", "doctor_profiles", ["department"])

    op.create_table(
        "refresh_tokens",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jti", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.String(255)),
        *_timestamps(),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    # -------------------------------------------------------------- visits --
    op.create_table(
        "visits",
        _uuid_pk(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctor_profiles.id", ondelete="SET NULL")),
        sa.Column("department", sa.String(120)),
        sa.Column("chief_complaint", sa.Text),
        sa.Column("status", _enum("visit_status_enum"), nullable=False, server_default="intake_started"),
        sa.Column("priority_level", _enum("priority_level_enum"), nullable=False, server_default="normal"),
        sa.Column("language", _enum("language_enum"), nullable=False, server_default="en"),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("consulted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_visits_patient_id", "visits", ["patient_id"])
    op.create_index("ix_visits_queue", "visits", ["status", "priority_level", "queued_at"])

    op.create_table(
        "consents",
        _uuid_pk(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="CASCADE")),
        sa.Column("scope", _enum("consent_scope_enum"), nullable=False),
        sa.Column("granted", sa.Boolean, nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True)),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column("language_shown", _enum("language_enum"), nullable=False, server_default="en"),
        sa.Column("consent_text_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("consent_text", sa.Text),
        *_timestamps(),
        sa.UniqueConstraint("patient_id", "visit_id", "scope", name="uq_consent_scope"),
    )

    # -------------------------------------------------------- conversation --
    op.create_table(
        "conversations",
        _uuid_pk(),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", _enum("conversation_status_enum"), nullable=False, server_default="in_progress"),
        sa.Column("language", _enum("language_enum"), nullable=False, server_default="en"),
        sa.Column("detected_pathway", sa.String(64)),
        sa.Column("current_step_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_conversations_pathway", "conversations", ["detected_pathway"])

    op.create_table(
        "conversation_messages",
        _uuid_pk(),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("role", _enum("message_role_enum"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("language", _enum("language_enum"), nullable=False, server_default="en"),
        sa.Column("via_voice", sa.Boolean, nullable=False, server_default=sa.false()),
        *_timestamps(),
    )
    op.create_index("ix_messages_conv_seq", "conversation_messages", ["conversation_id", "sequence"], unique=True)

    op.create_table(
        "questions",
        _uuid_pk(),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pathway", sa.String(64), nullable=False),
        sa.Column("node_id", sa.String(64), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("canonical_text", sa.Text, nullable=False),
        sa.Column("presented_text", sa.Text, nullable=False),
        sa.Column("phrasing_source", sa.String(16), nullable=False, server_default="template"),
        sa.Column("answer_type", sa.String(24), nullable=False, server_default="text"),
        sa.Column("options", postgresql.JSONB),
        *_timestamps(),
    )
    op.create_index("ix_questions_conversation_id", "questions", ["conversation_id"])
    op.create_index("ix_questions_category", "questions", ["category"])

    op.create_table(
        "patient_responses",
        _uuid_pk(),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("structured_value", postgresql.JSONB),
        sa.Column("provenance", _enum("provenance_enum"), nullable=False, server_default="PATIENT-PROVIDED"),
        sa.Column("via_voice", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("client_token", sa.String(64)),
        *_timestamps(),
    )
    op.create_index("ix_responses_conversation_id", "patient_responses", ["conversation_id"])
    op.create_index("ix_responses_client_token", "patient_responses", ["client_token"])

    op.create_table(
        "red_flags",
        _uuid_pk(),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("detail", sa.Text, nullable=False),
        sa.Column("severity", _enum("severity_enum"), nullable=False),
        sa.Column("evidence", postgresql.JSONB),
        sa.Column("source", sa.String(24), nullable=False, server_default="conversation"),
        sa.Column("acknowledged_by_doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctor_profiles.id", ondelete="SET NULL")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_redflag_visit_rule", "red_flags", ["visit_id", "rule_id"], unique=True)

    # ----------------------------------------------------------- documents --
    op.create_table(
        "medical_documents",
        _uuid_pk(),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(96), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("page_count", sa.Integer),
        sa.Column("document_type", _enum("document_type_enum")),
        sa.Column("captured_via_camera", sa.Boolean, nullable=False, server_default=sa.false()),
        *_timestamps(),
    )
    op.create_index("ix_documents_visit_id", "medical_documents", ["visit_id"])
    op.create_index("ix_documents_patient_id", "medical_documents", ["patient_id"])
    op.create_index("ix_documents_sha256", "medical_documents", ["sha256"])

    op.create_table(
        "document_extractions",
        _uuid_pk(),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medical_documents.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("ocr_status", _enum("ocr_status_enum"), nullable=False, server_default="queued"),
        sa.Column("ocr_provider", sa.String(32)),
        sa.Column("raw_text", sa.Text),
        sa.Column("ocr_confidence", sa.Float),
        sa.Column("ocr_error", sa.Text),
        sa.Column("structured_fields", postgresql.JSONB),
        sa.Column("overall_confidence", sa.Float),
        sa.Column("extraction_provider", sa.String(32)),
        sa.Column("extracted_at", sa.DateTime(timezone=True)),
        sa.Column("verification_state", _enum("verification_state_enum"), nullable=False, server_default="draft"),
        *_timestamps(),
    )
    op.create_index("ix_extractions_status", "document_extractions", ["ocr_status"])

    op.create_table(
        "medications",
        _uuid_pk(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(160), nullable=False),
        sa.Column("dose", sa.String(64)),
        sa.Column("frequency", sa.String(64)),
        sa.Column("duration", sa.String(64)),
        sa.Column("started_on", sa.Date),
        sa.Column("still_taking", sa.Boolean),
        sa.Column("provenance", _enum("provenance_enum"), nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("source_document_ids", postgresql.JSONB),
        sa.Column("source_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("verification_state", _enum("verification_state_enum"), nullable=False, server_default="draft"),
        *_timestamps(),
    )
    op.create_index("ix_med_patient_norm", "medications", ["patient_id", "normalized_name"], unique=True)

    op.create_table(
        "investigations",
        _uuid_pk(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(160), nullable=False),
        sa.Column("value", sa.String(64)),
        sa.Column("unit", sa.String(32)),
        sa.Column("reference_range", sa.String(64)),
        sa.Column("abnormal_flag", sa.String(16)),
        sa.Column("performed_on", sa.Date),
        sa.Column("date_uncertain", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("provenance", _enum("provenance_enum"), nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("source_document_ids", postgresql.JSONB),
        sa.Column("verification_state", _enum("verification_state_enum"), nullable=False, server_default="draft"),
        *_timestamps(),
    )
    op.create_index("ix_investigations_patient_id", "investigations", ["patient_id"])
    op.create_index("ix_investigations_abnormal", "investigations", ["abnormal_flag"])

    op.create_table(
        "allergies",
        _uuid_pk(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("substance", sa.String(160), nullable=False),
        sa.Column("normalized_substance", sa.String(160), nullable=False),
        sa.Column("reaction", sa.String(255)),
        sa.Column("provenance", _enum("provenance_enum"), nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("source_document_ids", postgresql.JSONB),
        sa.Column("verification_state", _enum("verification_state_enum"), nullable=False, server_default="draft"),
        *_timestamps(),
    )
    op.create_index("ix_allergy_patient_norm", "allergies", ["patient_id", "normalized_substance"], unique=True)

    op.create_table(
        "medical_history_entries",
        _uuid_pk(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("history_type", _enum("history_type_enum"), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("detail", sa.Text),
        sa.Column("onset_date", sa.Date),
        sa.Column("date_uncertain", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("provenance", _enum("provenance_enum"), nullable=False),
        sa.Column("source_document_ids", postgresql.JSONB),
        sa.Column("verification_state", _enum("verification_state_enum"), nullable=False, server_default="draft"),
        *_timestamps(),
    )
    op.create_index("ix_history_patient_type", "medical_history_entries", ["patient_id", "history_type"])

    # ------------------------------------------------------------- summary --
    op.create_table(
        "clinical_summaries",
        _uuid_pk(),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", _enum("verification_state_enum"), nullable=False, server_default="draft"),
        sa.Column("generated_by", sa.String(32)),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
        sa.Column("finalized_by_doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctor_profiles.id", ondelete="SET NULL")),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column("doctor_notes", sa.Text),
        *_timestamps(),
    )
    op.create_index("ix_summaries_status", "clinical_summaries", ["status"])

    op.create_table(
        "summary_sections",
        _uuid_pk(),
        sa.Column("summary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinical_summaries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(48), nullable=False),
        sa.Column("label", sa.String(96), nullable=False),
        sa.Column("display_order", sa.Integer, nullable=False),
        sa.Column("ai_body", sa.Text),
        sa.Column("doctor_body", sa.Text),
        sa.Column("provenance", _enum("provenance_enum"), nullable=False),
        sa.Column("status", _enum("verification_state_enum"), nullable=False, server_default="draft"),
        sa.Column("source_refs", postgresql.JSONB),
        *_timestamps(),
    )
    op.create_index("ix_section_summary_key", "summary_sections", ["summary_id", "key"], unique=True)

    op.create_table(
        "doctor_verifications",
        _uuid_pk(),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctor_profiles.id", ondelete="SET NULL")),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(48), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("original_value", sa.Text),
        sa.Column("verified_value", sa.Text),
        sa.Column("reason", sa.Text),
        *_timestamps(),
    )
    op.create_index("ix_verifications_entity", "doctor_verifications", ["entity_type", "entity_id"])
    op.create_index("ix_verifications_visit", "doctor_verifications", ["visit_id"])

    # --------------------------------------------------------------- audit --
    op.create_table(
        "audit_logs",
        _uuid_pk(),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_role", sa.String(24)),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(48)),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("summary", sa.Text),
        sa.Column("before", postgresql.JSONB),
        sa.Column("after", postgresql.JSONB),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("request_id", sa.String(64)),
        *_timestamps(),
    )
    op.create_index("ix_audit_event", "audit_logs", ["event"])
    op.create_index("ix_audit_actor", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_entity_time", "audit_logs", ["entity_type", "entity_id", "created_at"])

    op.create_table(
        "abdm_sync_logs",
        _uuid_pk(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="SET NULL")),
        sa.Column("operation", sa.String(48), nullable=False),
        sa.Column("adapter", sa.String(24), nullable=False, server_default="mock"),
        sa.Column("simulated", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("payload_preview", postgresql.JSONB),
        *_timestamps(),
    )


def downgrade() -> None:
    for table in (
        "abdm_sync_logs", "audit_logs", "doctor_verifications", "summary_sections", "clinical_summaries",
        "medical_history_entries", "allergies", "investigations", "medications",
        "document_extractions", "medical_documents", "red_flags", "patient_responses", "questions",
        "conversation_messages", "conversations", "consents", "visits",
        "refresh_tokens", "doctor_profiles", "patient_profiles", "users",
    ):
        op.drop_table(table)

    bind = op.get_bind()
    for name in ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
