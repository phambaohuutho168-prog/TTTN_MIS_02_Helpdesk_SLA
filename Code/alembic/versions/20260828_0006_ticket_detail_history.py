"""Create ticket detail, SLA and immutable history tables for CV031.

Revision ID: 20260828_0006
Revises: 20260828_0005
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_0006"
down_revision: str | None = "20260828_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sla_policies",
        sa.Column("sla_policy_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("priority_id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("response_target_minutes", sa.Integer(), nullable=False),
        sa.Column("resolution_target_minutes", sa.Integer(), nullable=False),
        sa.Column("warning_percent", sa.Integer(), server_default="80", nullable=False),
        sa.Column("escalation_percent", sa.Integer(), server_default="150", nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint("version_no >= 1", name="ck_sla_policies_version_positive"),
        sa.CheckConstraint("response_target_minutes > 0", name="ck_sla_policies_response_target_positive"),
        sa.CheckConstraint("resolution_target_minutes > 0", name="ck_sla_policies_resolution_target_positive"),
        sa.CheckConstraint("warning_percent BETWEEN 1 AND 99", name="ck_sla_policies_warning_percent_range"),
        sa.CheckConstraint("escalation_percent >= 100", name="ck_sla_policies_escalation_percent_range"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_sla_policies_effective_time_order"),
        sa.ForeignKeyConstraint(["priority_id"], ["priorities.priority_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("sla_policy_id"),
        sa.UniqueConstraint("priority_id", "version_no", name="uq_sla_policies_priority_version"),
    )
    op.create_table(
        "ticket_resolutions",
        sa.Column("resolution_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("resolved_by", sa.BigInteger(), nullable=False),
        sa.Column("cycle_no", sa.Integer(), nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("cycle_no >= 1", name="ck_ticket_resolutions_cycle_positive"),
        sa.CheckConstraint("length(trim(resolution_note)) > 0", name="ck_ticket_resolutions_note_not_blank"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("resolution_id"),
        sa.UniqueConstraint("ticket_id", "cycle_no", name="uq_ticket_resolutions_ticket_cycle"),
    )
    op.create_table(
        "ticket_status_history",
        sa.Column("history_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("from_status_code", sa.String(length=30), nullable=True),
        sa.Column("to_status_code", sa.String(length=30), nullable=False),
        sa.Column("changed_by", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_status_code"], ["ticket_statuses.status_code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_status_code"], ["ticket_statuses.status_code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("history_id"),
    )
    op.create_index("ix_ticket_status_history_ticket_time", "ticket_status_history", ["ticket_id", "changed_at"])
    op.execute(
        sa.text(
            "INSERT INTO ticket_status_history "
            "(ticket_id, from_status_code, to_status_code, changed_by, reason, changed_at) "
            "SELECT ticket_id, NULL, current_status_code, requester_id, "
            "'Khởi tạo lịch sử từ dữ liệu hiện có', created_at FROM tickets"
        )
    )
    op.create_table(
        "ticket_slas",
        sa.Column("ticket_sla_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("sla_policy_id", sa.BigInteger(), nullable=False),
        sa.Column("sla_type", sa.String(length=20), nullable=False),
        sa.Column("cycle_no", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_paused_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("runtime_status", sa.String(length=30), server_default="RUNNING", nullable=False),
        sa.Column("result", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sla_type IN ('RESPONSE', 'RESOLUTION')", name="ck_ticket_slas_type_domain"),
        sa.CheckConstraint("cycle_no >= 1", name="ck_ticket_slas_cycle_positive"),
        sa.CheckConstraint("due_at >= started_at", name="ck_ticket_slas_due_time_order"),
        sa.CheckConstraint("completed_at IS NULL OR completed_at >= started_at", name="ck_ticket_slas_completed_time_order"),
        sa.CheckConstraint("paused_at IS NULL OR sla_type = 'RESOLUTION'", name="ck_ticket_slas_pause_resolution_only"),
        sa.CheckConstraint("total_paused_seconds >= 0", name="ck_ticket_slas_total_paused_non_negative"),
        sa.CheckConstraint("runtime_status IN ('RUNNING', 'PAUSED', 'COMPLETED', 'NOT_APPLICABLE')", name="ck_ticket_slas_runtime_status_domain"),
        sa.CheckConstraint("result IS NULL OR result IN ('MET', 'BREACHED', 'NOT_APPLICABLE')", name="ck_ticket_slas_result_domain"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sla_policy_id"], ["sla_policies.sla_policy_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("ticket_sla_id"),
        sa.UniqueConstraint("ticket_id", "sla_type", "cycle_no", name="uq_ticket_slas_ticket_type_cycle"),
    )
    op.create_index("ix_ticket_slas_worker", "ticket_slas", ["runtime_status", "due_at"])


def downgrade() -> None:
    op.drop_index("ix_ticket_slas_worker", table_name="ticket_slas")
    op.drop_table("ticket_slas")
    op.drop_index("ix_ticket_status_history_ticket_time", table_name="ticket_status_history")
    op.drop_table("ticket_status_history")
    op.drop_table("ticket_resolutions")
    op.drop_table("sla_policies")
