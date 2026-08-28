"""Create organization and authentication tables.

Revision ID: 20260827_0001
Revises:
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260827_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("department_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("department_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("department_id"),
        sa.UniqueConstraint("department_name", name="uq_departments_name"),
    )

    op.create_table(
        "roles",
        sa.Column("role_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("role_code", sa.String(length=30), nullable=False),
        sa.Column("role_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.CheckConstraint(
            "role_code IN ('REQUESTER','PROCESSOR','ADMIN')",
            name="ck_roles_code",
        ),
        sa.PrimaryKeyConstraint("role_id"),
        sa.UniqueConstraint("role_code", name="uq_roles_code"),
    )

    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("department_id", sa.BigInteger(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("BTRIM(full_name) <> ''", name="ck_users_full_name_not_blank"),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.department_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("assigned_by", sa.BigInteger(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.role_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
    )


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("departments")
