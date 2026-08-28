from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class TicketStatusHistory(Base):
    __tablename__ = "ticket_status_history"
    __table_args__ = (
        Index("ix_ticket_status_history_ticket_time", "ticket_id", "changed_at"),
    )

    history_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    ticket_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status_code: Mapped[str | None] = mapped_column(
        String(30),
        ForeignKey("ticket_statuses.status_code", ondelete="RESTRICT"),
        nullable=True,
    )
    to_status_code: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("ticket_statuses.status_code", ondelete="RESTRICT"),
        nullable=False,
    )
    changed_by: Mapped[int | None] = mapped_column(
        BIGINT_PK,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    ticket = relationship("Ticket", back_populates="status_history")
    from_status = relationship(
        "TicketStatus",
        foreign_keys=[from_status_code],
        back_populates="history_as_source",
    )
    to_status = relationship(
        "TicketStatus",
        foreign_keys=[to_status_code],
        back_populates="history_as_target",
    )
    actor = relationship("User", back_populates="ticket_status_changes")
