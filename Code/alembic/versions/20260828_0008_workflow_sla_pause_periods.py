"""Add SLA pause intervals required by ticket workflow.

Revision ID: 20260828_0008
Revises: 20260828_0007
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_0008"
down_revision: str | None = "20260828_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sla_pause_periods",
        sa.Column("pause_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("ticket_sla_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "paused_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "resumed_at IS NULL OR resumed_at >= paused_at",
            name="ck_sla_pause_periods_time_order",
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_sla_pause_periods_duration_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_sla_id"],
            ["ticket_slas.ticket_sla_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("pause_id"),
    )
    op.create_index(
        "ix_sla_pause_periods_ticket_sla_id",
        "sla_pause_periods",
        ["ticket_sla_id"],
    )
    op.create_index(
        "uq_sla_pause_periods_one_open",
        "sla_pause_periods",
        ["ticket_sla_id"],
        unique=True,
        postgresql_where=sa.text("resumed_at IS NULL"),
        sqlite_where=sa.text("resumed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_sla_pause_periods_one_open",
        table_name="sla_pause_periods",
    )
    op.drop_index(
        "ix_sla_pause_periods_ticket_sla_id",
        table_name="sla_pause_periods",
    )
    op.drop_table("sla_pause_periods")
