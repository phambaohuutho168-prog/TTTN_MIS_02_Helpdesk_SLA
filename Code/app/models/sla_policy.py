from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class SLAPolicy(Base):
    __tablename__ = "sla_policies"
    __table_args__ = (
        CheckConstraint("version_no >= 1", name="ck_sla_policies_version_positive"),
        CheckConstraint(
            "response_target_minutes > 0",
            name="ck_sla_policies_response_target_positive",
        ),
        CheckConstraint(
            "resolution_target_minutes > 0",
            name="ck_sla_policies_resolution_target_positive",
        ),
        CheckConstraint(
            "warning_percent BETWEEN 1 AND 99",
            name="ck_sla_policies_warning_percent_range",
        ),
        CheckConstraint(
            "escalation_percent >= 100",
            name="ck_sla_policies_escalation_percent_range",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_sla_policies_effective_time_order",
        ),
        UniqueConstraint(
            "priority_id",
            "version_no",
            name="uq_sla_policies_priority_version",
        ),
    )

    sla_policy_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    priority_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("priorities.priority_id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    response_target_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_target_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=80,
        server_default="80",
    )
    escalation_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=150,
        server_default="150",
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    priority = relationship("Priority", back_populates="sla_policies")
    ticket_slas = relationship("TicketSLA", back_populates="policy")
