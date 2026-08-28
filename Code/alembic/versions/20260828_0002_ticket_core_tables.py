"""Create ticket master data and tickets table.

Revision ID: 20260828_0002
Revises: 20260827_0001
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_0002"
down_revision: str | None = "20260827_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("category_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("category_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(BTRIM(category_name)) > 0",
            name="ck_categories_name_not_blank",
        ),
        sa.PrimaryKeyConstraint("category_id"),
        sa.UniqueConstraint("category_name", name="uq_categories_name"),
    )

    op.create_table(
        "priorities",
        sa.Column("priority_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("priority_code", sa.String(length=30), nullable=False),
        sa.Column("priority_level", sa.Integer(), nullable=False),
        sa.Column("priority_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.CheckConstraint(
            "priority_level > 0",
            name="ck_priorities_level_positive",
        ),
        sa.PrimaryKeyConstraint("priority_id"),
        sa.UniqueConstraint("priority_code", name="uq_priorities_code"),
        sa.UniqueConstraint("priority_level", name="uq_priorities_level"),
    )

    op.create_table(
        "ticket_statuses",
        sa.Column("status_code", sa.String(length=30), nullable=False),
        sa.Column("status_name", sa.String(length=100), nullable=False),
        sa.Column("is_terminal", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("status_code"),
    )

    op.create_table(
        "tickets",
        sa.Column("ticket_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("ticket_code", sa.String(length=30), nullable=False),
        sa.Column("requester_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("priority_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "current_status_code",
            sa.String(length=30),
            server_default="NEW",
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(BTRIM(title)) > 0",
            name="ck_tickets_title_not_blank",
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.user_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.category_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["priority_id"],
            ["priorities.priority_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["current_status_code"],
            ["ticket_statuses.status_code"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("ticket_id"),
        sa.UniqueConstraint("ticket_code", name="uq_tickets_code"),
    )
    op.create_index(
        "ix_tickets_requester_created",
        "tickets",
        ["requester_id", "created_at"],
    )
    op.create_index(
        "ix_tickets_current_status",
        "tickets",
        ["current_status_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_tickets_current_status", table_name="tickets")
    op.drop_index("ix_tickets_requester_created", table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("ticket_statuses")
    op.drop_table("priorities")
    op.drop_table("categories")
