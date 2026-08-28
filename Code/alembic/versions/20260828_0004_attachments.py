"""Create comments metadata and attachments.

Revision ID: 20260828_0004
Revises: 20260828_0003
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_0004"
down_revision: str | None = "20260828_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("comment_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "visibility",
            sa.String(length=20),
            server_default="PUBLIC",
            nullable=False,
        ),
        sa.Column(
            "comment_type",
            sa.String(length=30),
            server_default="REPLY",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(BTRIM(content)) > 0",
            name="ck_comments_content_not_blank",
        ),
        sa.CheckConstraint(
            "visibility IN ('PUBLIC', 'INTERNAL')",
            name="ck_comments_visibility_domain",
        ),
        sa.CheckConstraint(
            "comment_type IN ('REPLY', 'REQUEST_INFO', 'SYSTEM_NOTE')",
            name="ck_comments_type_domain",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.ticket_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.user_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("comment_id"),
    )
    op.create_index("ix_comments_ticket_id", "comments", ["ticket_id"])

    op.create_table(
        "attachments",
        sa.Column("attachment_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("comment_id", sa.BigInteger(), nullable=True),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(BTRIM(file_name)) > 0",
            name="ck_attachments_file_name_not_blank",
        ),
        sa.CheckConstraint(
            "length(BTRIM(storage_path)) > 0",
            name="ck_attachments_storage_path_not_blank",
        ),
        sa.CheckConstraint(
            "file_size > 0",
            name="ck_attachments_file_size_positive",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.ticket_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["comment_id"],
            ["comments.comment_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.user_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("attachment_id"),
        sa.UniqueConstraint("storage_path"),
    )
    op.create_index(
        "ix_attachments_ticket_uploaded",
        "attachments",
        ["ticket_id", "uploaded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_attachments_ticket_uploaded", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_comments_ticket_id", table_name="comments")
    op.drop_table("comments")
