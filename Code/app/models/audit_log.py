from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class AuditLog(Base):
    """Append-only business audit record.

    The application intentionally exposes no update or delete operation for
    this entity.  Assignment changes are persisted here in the same database
    transaction as the assignment itself.
    """

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
    entity_id: Mapped[int] = mapped_column(BIGINT_PK, nullable=False)
    old_value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    new_value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    actor = relationship("User", back_populates="audit_logs")
    ticket = relationship("Ticket", back_populates="audit_logs")
