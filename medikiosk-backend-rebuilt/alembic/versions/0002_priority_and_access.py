"""Priority scoring and insider-misuse controls.

Revision ID: 0002_priority_and_access
Revises: 0001_initial
Create Date: 2026-09-10

Adds two things:

  * `visits.priority_score` and `visits.priority_factors` — the explainable
    acuity score behind the queue band.
  * `record_accesses`, `misuse_alerts`, `export_receipts` — the controls that
    make insider misuse visible and traceable.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_priority_and_access"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


ENUMS = {
    "access_purpose_enum": ("treatment", "continuity_of_care", "emergency", "quality_audit"),
    "access_decision_enum": ("allowed", "break_glass", "throttled", "denied"),
    "alert_kind_enum": ("bulk_access", "off_queue_pattern", "export_volume", "after_hours_bulk"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    # ---------------------------------------------------- priority scoring --
    op.add_column("visits", sa.Column("priority_score", sa.Integer, nullable=False, server_default="0"))
    op.add_column("visits", sa.Column("priority_factors", postgresql.JSONB))
    # The queue sorts on band then score, so the index must cover both.
    op.create_index("ix_visits_priority", "visits", ["status", "priority_level", "priority_score"])

    # ------------------------------------------------------ access records --
    op.create_table(
        "record_accesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_role", sa.String(24), nullable=False),
        sa.Column("actor_name", sa.String(160)),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="SET NULL")),
        sa.Column("resource", sa.String(48), nullable=False),
        sa.Column("purpose", _enum("access_purpose_enum"), nullable=False),
        sa.Column("decision", _enum("access_decision_enum"), nullable=False, server_default="allowed"),
        sa.Column("justification", sa.Text),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("request_id", sa.String(64)),
        *_timestamps(),
    )
    op.create_index("ix_access_patient_time", "record_accesses", ["patient_id", "created_at"])
    op.create_index("ix_access_actor_time", "record_accesses", ["actor_id", "created_at"])

    op.create_table(
        "misuse_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", _enum("alert_kind_enum"), nullable=False),
        sa.Column("detail", sa.Text, nullable=False),
        sa.Column("window_minutes", sa.Integer, nullable=False),
        sa.Column("observed_count", sa.Integer, nullable=False),
        sa.Column("threshold", sa.Integer, nullable=False),
        sa.Column("context", postgresql.JSONB),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True)),
        sa.Column("review_note", sa.Text),
        *_timestamps(),
    )
    op.create_index("ix_alerts_actor", "misuse_alerts", ["actor_id"])
    op.create_index("ix_alerts_kind", "misuse_alerts", ["kind"])

    op.create_table(
        "export_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_name", sa.String(160)),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="SET NULL")),
        sa.Column("watermark", sa.String(64), nullable=False, unique=True),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("section_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("consent_id", postgresql.UUID(as_uuid=True)),
        sa.Column("purpose", _enum("access_purpose_enum"), nullable=False),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_receipts_actor", "export_receipts", ["actor_id"])
    op.create_index("ix_receipts_patient", "export_receipts", ["patient_id"])
    op.create_index("ix_receipts_watermark", "export_receipts", ["watermark"])


def downgrade() -> None:
    for table in ("export_receipts", "misuse_alerts", "record_accesses"):
        op.drop_table(table)

    op.drop_index("ix_visits_priority", table_name="visits")
    op.drop_column("visits", "priority_factors")
    op.drop_column("visits", "priority_score")

    bind = op.get_bind()
    for name in ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
