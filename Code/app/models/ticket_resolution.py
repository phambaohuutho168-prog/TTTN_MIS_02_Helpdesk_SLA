from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class TicketResolution(Base):
    __tablename__ = "ticket_resolutions"
    __table_args__ = (
        CheckConstraint("cycle_no >= 1", name="ck_ticket_resolutions_cycle_positive"),
        CheckConstraint(
            "length(trim(resolution_note)) > 0",
            name="ck_ticket_resolutions_note_not_blank",
        ),
        UniqueConstraint(
            "ticket_id",
            "cycle_no",
            name="uq_ticket_resolutions_ticket_cycle",
        ),
    )

    resolution_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    ticket_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    resolved_by: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    cycle_no: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_note: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    ticket = relationship("Ticket", back_populates="resolutions")
    resolver = relationship("User", back_populates="ticket_resolutions")
