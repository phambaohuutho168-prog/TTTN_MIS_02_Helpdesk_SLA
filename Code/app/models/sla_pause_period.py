from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class SLAPausePeriod(Base):
    """One append-only pause interval of a Resolution SLA cycle."""

    __tablename__ = "sla_pause_periods"
    __table_args__ = (
        CheckConstraint(
            "resumed_at IS NULL OR resumed_at >= paused_at",
            name="ck_sla_pause_periods_time_order",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_sla_pause_periods_duration_non_negative",
        ),
    )

    pause_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    ticket_sla_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("ticket_slas.ticket_sla_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    paused_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    resumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    ticket_sla = relationship("TicketSLA")
