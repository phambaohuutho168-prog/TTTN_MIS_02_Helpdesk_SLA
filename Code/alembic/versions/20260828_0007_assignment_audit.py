"""Create append-only audit log for ticket assignment changes.

Revision ID: 20260828_0007
Revises: 20260828_0006
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_0007"
down_revision: str | None = "20260828_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("audit_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("ticket_id", sa.BigInteger(), nullable=True),
        sa.Column("action_code", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("old_value_json", sa.JSON(), nullable=True),
        sa.Column("new_value_json", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(action_code)) > 0",
            name="ck_audit_logs_action_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(entity_type)) > 0",
            name="ck_audit_logs_entity_type_not_blank",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.user_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.ticket_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    op.create_index(
        "ix_audit_logs_ticket_time",
        "audit_logs",
        ["ticket_id", "created_at"],
    )
    op.create_index(
        "ix_audit_logs_actor_time",
        "audit_logs",
        ["actor_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_actor_time", table_name="audit_logs")
    op.drop_index("ix_audit_logs_ticket_time", table_name="audit_logs")
    op.drop_table("audit_logs")
