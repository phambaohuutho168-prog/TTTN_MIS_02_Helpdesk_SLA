"""Complete audit log queryability and append-only protection.

Revision ID: 20260828_0009
Revises: 20260828_0008
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_0009"
down_revision: str | None = "20260828_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("audit_logs", "entity_id", existing_type=sa.BigInteger(), nullable=True)
    op.add_column(
        "audit_logs",
        sa.Column("request_id", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_audit_logs_entity_time",
        "audit_logs",
        ["entity_type", "entity_id", "created_at"],
    )
    op.create_index(
        "ix_audit_logs_action_time",
        "audit_logs",
        ["action_code", "created_at"],
    )
    op.create_index(
        "ix_audit_logs_request_id",
        "audit_logs",
        ["request_id"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_logs is append-only';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_audit_logs_append_only
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()")
    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action_time", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_time", table_name="audit_logs")
    op.drop_column("audit_logs", "request_id")
    op.alter_column("audit_logs", "entity_id", existing_type=sa.BigInteger(), nullable=False)
