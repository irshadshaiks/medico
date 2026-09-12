"""Safety escalation, attendant mode.

Revision ID: 0003_escalation
Revises: 0002_priority_and_access
Create Date: 2026-09-12

Additive only. No table is dropped, no column is dropped, no existing enum
member moves. A rollback to 0002 leaves every pre-existing row untouched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_escalation"
down_revision = "0002_priority_and_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # New members appended to existing types. ADD VALUE cannot run inside a
    # transaction block on older PostgreSQL, hence COMMIT first.
    op.execute("COMMIT")
    op.execute("ALTER TYPE conversation_status_enum ADD VALUE IF NOT EXISTS 'halted_escalated'")
    op.execute("ALTER TYPE provenance_enum ADD VALUE IF NOT EXISTS 'ATTENDANT-REPORTED'")

    postgresql.ENUM("raised", "acknowledged", name="escalation_status_enum").create(bind, checkfirst=True)

    op.create_table(
        "escalations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("staff_label", sa.String(200), nullable=False),
        sa.Column("destination", sa.String(96), nullable=False),
        sa.Column("patient_instruction", sa.Text, nullable=False),
        sa.Column("evidence", postgresql.JSONB),
        sa.Column("matched_rules", postgresql.JSONB),
        sa.Column("clinically_signed_off", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("status", postgresql.ENUM("raised", "acknowledged", name="escalation_status_enum", create_type=False),
                  nullable=False, server_default="raised"),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("outcome", sa.String(48)),
        sa.Column("outcome_note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_escalations_visit_id", "escalations", ["visit_id"])
    op.create_index("ix_escalations_rule_id", "escalations", ["rule_id"])
    op.create_index("ix_escalation_open", "escalations", ["status", "created_at"])

    # Attendant mode.
    op.add_column("patient_responses", sa.Column("respondent", sa.String(16), nullable=False, server_default="patient"))
    op.add_column("patient_responses", sa.Column("attendant_relationship", sa.String(48)))


def downgrade() -> None:
    op.drop_column("patient_responses", "attendant_relationship")
    op.drop_column("patient_responses", "respondent")
    op.drop_table("escalations")

    bind = op.get_bind()
    postgresql.ENUM(name="escalation_status_enum").drop(bind, checkfirst=True)

    # PostgreSQL cannot remove a value from an enum type. 'halted_escalated'
    # and 'ATTENDANT-REPORTED' stay in their types after this downgrade, which
    # is harmless: nothing references them once the code is rolled back, and
    # re-running the upgrade is idempotent thanks to IF NOT EXISTS.
