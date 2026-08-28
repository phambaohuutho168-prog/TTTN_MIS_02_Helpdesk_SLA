from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class TicketSLA(Base):
    __tablename__ = "ticket_slas"
    __table_args__ = (
        CheckConstraint(
            "sla_type IN ('RESPONSE', 'RESOLUTION')",
            name="ck_ticket_slas_type_domain",
        ),
        CheckConstraint("cycle_no >= 1", name="ck_ticket_slas_cycle_positive"),
        CheckConstraint("due_at >= started_at", name="ck_ticket_slas_due_time_order"),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_ticket_slas_completed_time_order",
        ),
        CheckConstraint(
            "paused_at IS NULL OR sla_type = 'RESOLUTION'",
            name="ck_ticket_slas_pause_resolution_only",
        ),
        CheckConstraint(
            "total_paused_seconds >= 0",
            name="ck_ticket_slas_total_paused_non_negative",
        ),
        CheckConstraint(
            "runtime_status IN ('RUNNING', 'PAUSED', 'COMPLETED', 'NOT_APPLICABLE')",
            name="ck_ticket_slas_runtime_status_domain",
        ),
        CheckConstraint(
            "result IS NULL OR result IN ('MET', 'BREACHED', 'NOT_APPLICABLE')",
            name="ck_ticket_slas_result_domain",
        ),
        UniqueConstraint(
            "ticket_id",
            "sla_type",
            "cycle_no",
            name="uq_ticket_slas_ticket_type_cycle",
        ),
        Index("ix_ticket_slas_worker", "runtime_status", "due_at"),
    )

    ticket_sla_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    ticket_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    sla_policy_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("sla_policies.sla_policy_id", ondelete="RESTRICT"),
        nullable=False,
    )
    sla_type: Mapped[str] = mapped_column(String(20), nullable=False)
    cycle_no: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_paused_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    runtime_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="RUNNING",
        server_default="RUNNING",
    )
    result: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    ticket = relationship("Ticket", back_populates="sla_records")
    policy = relationship("SLAPolicy", back_populates="ticket_slas")
