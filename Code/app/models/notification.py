from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class Notification(Base):
    """In-app notification generated for a concrete recipient."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "length(trim(notification_type)) > 0",
            name="ck_notifications_type_not_blank",
        ),
        CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_notifications_title_not_blank",
        ),
        CheckConstraint(
            "length(trim(message)) > 0",
            name="ck_notifications_message_not_blank",
        ),
        CheckConstraint(
            "(is_read = false AND read_at IS NULL) OR "
            "(is_read = true AND read_at IS NOT NULL)",
            name="ck_notifications_read_consistency",
        ),
        UniqueConstraint(
            "recipient_id",
            "sla_event_id",
            "notification_type",
            name="uq_notifications_recipient_sla_event_type",
        ),
        Index(
            "ix_notifications_recipient_unread_time",
            "recipient_id",
            "is_read",
            "created_at",
        ),
    )

    notification_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    recipient_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    ticket_id: Mapped[int | None] = mapped_column(
        BIGINT_PK,
        ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=True,
    )
    sla_event_id: Mapped[int | None] = mapped_column(
        BIGINT_PK,
        ForeignKey("sla_events.sla_event_id", ondelete="SET NULL"),
        nullable=True,
    )
    notification_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    recipient = relationship("User", back_populates="notifications")
    ticket = relationship("Ticket", back_populates="notifications")
    sla_event = relationship("SLAEvent", back_populates="notifications")
