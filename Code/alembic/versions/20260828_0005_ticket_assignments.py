"""Create ticket assignment history for CV030 data scope.

Revision ID: 20260828_0005
Revises: 20260828_0004
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_0005"
down_revision: str | None = "20260828_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticket_assignments",
        sa.Column("assignment_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("assignee_id", sa.BigInteger(), nullable=False),
        sa.Column("assigned_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= assigned_at",
            name="ck_ticket_assignments_time_order",
        ),
        sa.CheckConstraint(
            "(is_current AND ended_at IS NULL) OR "
            "(NOT is_current AND ended_at IS NOT NULL)",
            name="ck_ticket_assignments_current_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.ticket_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["users.user_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"],
            ["users.user_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("assignment_id"),
    )
    op.create_index(
        "uq_ticket_assignments_current",
        "ticket_assignments",
        ["ticket_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )
    op.create_index(
        "ix_ticket_assignments_assignee_current",
        "ticket_assignments",
        ["assignee_id", "is_current"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ticket_assignments_assignee_current",
        table_name="ticket_assignments",
    )
    op.drop_index(
        "uq_ticket_assignments_current",
        table_name="ticket_assignments",
    )
    op.drop_table("ticket_assignments")
