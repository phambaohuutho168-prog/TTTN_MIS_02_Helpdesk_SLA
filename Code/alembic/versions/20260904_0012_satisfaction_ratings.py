"""Create one satisfaction rating per resolved or closed ticket.

Revision ID: 20260904_0012
Revises: 20260904_0011
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_0012"
down_revision: str | None = "20260904_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ratings",
        sa.Column("rating_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("rated_by", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "score BETWEEN 1 AND 5",
            name="ck_ratings_score_range",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.ticket_id"],
            name="fk_ratings_ticket",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rated_by"],
            ["users.user_id"],
            name="fk_ratings_rated_by_user",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("rating_id", name="pk_ratings"),
        sa.UniqueConstraint("ticket_id", name="uq_ratings_ticket"),
    )


def downgrade() -> None:
    op.drop_table("ratings")
