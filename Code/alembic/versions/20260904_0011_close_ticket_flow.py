"""Record the actor and timestamp of ticket closure.

Revision ID: 20260904_0011
Revises: 20260904_0010
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_0011"
down_revision: str | None = "20260904_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("closed_by", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tickets_closed_by_users",
        "tickets",
        "users",
        ["closed_by"],
        ["user_id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_tickets_closed_actor_time",
        "tickets",
        "closed_by IS NULL OR closed_at IS NOT NULL",
    )
    op.create_index(
        "ix_tickets_closed_by_time",
        "tickets",
        ["closed_by", "closed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tickets_closed_by_time", table_name="tickets")
    op.drop_constraint(
        "ck_tickets_closed_actor_time",
        "tickets",
        type_="check",
    )
    op.drop_constraint(
        "fk_tickets_closed_by_users",
        "tickets",
        type_="foreignkey",
    )
    op.drop_column("tickets", "closed_by")
