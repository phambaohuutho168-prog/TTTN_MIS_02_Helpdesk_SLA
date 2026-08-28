from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class AuditLog(Base):
    """Append-only business audit record."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "length(trim(action_code)) > 0",
            name="ck_audit_logs_action_not_blank",
        ),
        CheckConstraint(
            "length(trim(entity_type)) > 0",
            name="ck_audit_logs_entity_type_not_blank",
        ),
        Index("ix_audit_logs_ticket_time", "ticket_id", "created_at"),
        Index("ix_audit_logs_actor_time", "actor_user_id", "created_at"),
        Index(
            "ix_audit_logs_entity_time",
            "entity_type",
            "entity_id",
            "created_at",
        ),
        Index("ix_audit_logs_action_time", "action_code", "created_at"),
        Index("ix_audit_logs_request_id", "request_id"),
    )

    audit_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        BIGINT_PK,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    ticket_id: Mapped[int | None] = mapped_column(
        BIGINT_PK,
        ForeignKey("tickets.ticket_id", ondelete="SET NULL"),
        nullable=True,
    )
    action_code: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(BIGINT_PK, nullable=True)
    old_value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    new_value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    actor = relationship("User", back_populates="audit_logs")
    ticket = relationship("Ticket", back_populates="audit_logs")


def _reject_mutation(_mapper, _connection, _target) -> None:
    raise ValueError("AUDIT_LOG_APPEND_ONLY")


def _prepare_insert(_mapper, _connection, target: AuditLog) -> None:
    """Enforce normalization, tracing and redaction for every audit writer."""

    from app.core.request_context import current_request_id
    from app.repositories.audit_repository import (
        normalize_ip_address,
        sanitize_audit_value,
    )

    target.action_code = target.action_code.strip().upper()
    target.entity_type = target.entity_type.strip().upper()
    target.old_value_json = sanitize_audit_value(target.old_value_json)
    target.new_value_json = sanitize_audit_value(target.new_value_json)
    target.ip_address = normalize_ip_address(target.ip_address)
    target.request_id = target.request_id or current_request_id()


event.listen(AuditLog, "before_insert", _prepare_insert)
event.listen(AuditLog, "before_update", _reject_mutation)
event.listen(AuditLog, "before_delete", _reject_mutation)
