"""Normalize Category and Priority catalog constraints.

Revision ID: 20260828_0003
Revises: 20260828_0002
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_0003"
down_revision: str | None = "20260828_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Normalize the legacy CV027 seed values before enforcing P1-P4.
    op.execute(
        """
        UPDATE priorities
        SET
            priority_code = 'LEGACY_' || UPPER(priority_code),
            priority_level = priority_level + 100
        WHERE UPPER(priority_code) IN ('URGENT', 'HIGH', 'MEDIUM', 'LOW')
        """
    )
    op.execute(
        """
        UPDATE priorities
        SET
            priority_code = CASE UPPER(priority_code)
                WHEN 'LEGACY_URGENT' THEN 'P1'
                WHEN 'LEGACY_HIGH' THEN 'P2'
                WHEN 'LEGACY_MEDIUM' THEN 'P3'
                WHEN 'LEGACY_LOW' THEN 'P4'
            END,
            priority_level = CASE UPPER(priority_code)
                WHEN 'LEGACY_URGENT' THEN 1
                WHEN 'LEGACY_HIGH' THEN 2
                WHEN 'LEGACY_MEDIUM' THEN 3
                WHEN 'LEGACY_LOW' THEN 4
            END
        WHERE UPPER(priority_code) IN (
            'LEGACY_URGENT',
            'LEGACY_HIGH',
            'LEGACY_MEDIUM',
            'LEGACY_LOW'
        )
        """
    )

    op.drop_constraint("uq_categories_name", "categories", type_="unique")
    op.create_index(
        "uq_categories_name_lower",
        "categories",
        [sa.text("lower(category_name)")],
        unique=True,
    )

    op.drop_constraint(
        "ck_priorities_level_positive",
        "priorities",
        type_="check",
    )
    op.alter_column(
        "priorities",
        "priority_code",
        existing_type=sa.String(length=30),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_priorities_code_domain",
        "priorities",
        "priority_code IN ('P1', 'P2', 'P3', 'P4')",
    )
    op.create_check_constraint(
        "ck_priorities_level_range",
        "priorities",
        "priority_level BETWEEN 1 AND 4",
    )
    op.create_check_constraint(
        "ck_priorities_name_not_blank",
        "priorities",
        "length(BTRIM(priority_name)) > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_priorities_name_not_blank",
        "priorities",
        type_="check",
    )
    op.drop_constraint(
        "ck_priorities_level_range",
        "priorities",
        type_="check",
    )
    op.drop_constraint(
        "ck_priorities_code_domain",
        "priorities",
        type_="check",
    )
    op.alter_column(
        "priorities",
        "priority_code",
        existing_type=sa.String(length=10),
        type_=sa.String(length=30),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_priorities_level_positive",
        "priorities",
        "priority_level > 0",
    )

    op.drop_index("uq_categories_name_lower", table_name="categories")
    op.create_unique_constraint(
        "uq_categories_name",
        "categories",
        ["category_name"],
    )
