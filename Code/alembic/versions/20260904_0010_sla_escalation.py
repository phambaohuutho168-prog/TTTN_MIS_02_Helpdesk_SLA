"""Create idempotent SLA events and recipient notifications.

Revision ID: 20260904_0010
Revises: 20260828_0009
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_0010"
down_revision: str | None = "20260828_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sla_events",
        sa.Column(
            "sla_event_id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("ticket_sla_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("threshold_percent", sa.Integer(), nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('WARNING', 'OVERDUE', 'ESCALATED')",
            name="ck_sla_events_type_domain",
        ),
        sa.CheckConstraint(
            "threshold_percent > 0",
            name="ck_sla_events_threshold_positive",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_sla_id"],
            ["ticket_slas.ticket_sla_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("sla_event_id"),
        sa.UniqueConstraint(
            "ticket_sla_id",
            "event_type",
            name="uq_sla_events_runtime_type",
        ),
    )
    op.create_index(
        "ix_sla_events_type_time",
        "sla_events",
        ["event_type", "triggered_at"],
    )

    op.create_table(
        "notifications",
        sa.Column(
            "notification_id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("recipient_id", sa.BigInteger(), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=True),
        sa.Column("sla_event_id", sa.BigInteger(), nullable=True),
        sa.Column("notification_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "is_read",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(trim(notification_type)) > 0",
            name="ck_notifications_type_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_notifications_title_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(message)) > 0",
            name="ck_notifications_message_not_blank",
        ),
        sa.CheckConstraint(
            "(is_read = false AND read_at IS NULL) OR "
            "(is_read = true AND read_at IS NOT NULL)",
            name="ck_notifications_read_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.user_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.ticket_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sla_event_id"],
            ["sla_events.sla_event_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("notification_id"),
        sa.UniqueConstraint(
            "recipient_id",
            "sla_event_id",
            "notification_type",
            name="uq_notifications_recipient_sla_event_type",
        ),
    )
    op.create_index(
        "ix_notifications_recipient_unread_time",
        "notifications",
        ["recipient_id", "is_read", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notifications_recipient_unread_time",
        table_name="notifications",
    )
    op.drop_table("notifications")
    op.drop_index("ix_sla_events_type_time", table_name="sla_events")
    op.drop_table("sla_events")
