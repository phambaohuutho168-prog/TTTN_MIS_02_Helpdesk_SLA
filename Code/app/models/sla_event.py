from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class SLAEvent(Base):
    """Idempotent record of one SLA threshold being crossed."""

    __tablename__ = "sla_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('WARNING', 'OVERDUE', 'ESCALATED')",
            name="ck_sla_events_type_domain",
        ),
        CheckConstraint(
            "threshold_percent > 0",
            name="ck_sla_events_threshold_positive",
        ),
        UniqueConstraint(
            "ticket_sla_id",
            "event_type",
            name="uq_sla_events_runtime_type",
        ),
        Index("ix_sla_events_type_time", "event_type", "triggered_at"),
    )

    sla_event_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    ticket_sla_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("ticket_slas.ticket_sla_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    ticket_sla = relationship("TicketSLA", back_populates="events")
    notifications = relationship(
        "Notification",
        back_populates="sla_event",
        passive_deletes=True,
    )
