from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class TicketAssignment(Base):
    __tablename__ = "ticket_assignments"
    __table_args__ = (
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= assigned_at",
            name="ck_ticket_assignments_time_order",
        ),
        CheckConstraint(
            "(is_current AND ended_at IS NULL) OR "
            "(NOT is_current AND ended_at IS NOT NULL)",
            name="ck_ticket_assignments_current_consistency",
        ),
        Index(
            "uq_ticket_assignments_current",
            "ticket_id",
            unique=True,
            postgresql_where=text("is_current = true"),
            sqlite_where=text("is_current = 1"),
        ),
        Index(
            "ix_ticket_assignments_assignee_current",
            "assignee_id",
            "is_current",
        ),
    )

    assignment_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    ticket_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    assignee_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_by: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    ticket = relationship("Ticket", back_populates="assignments")
    assignee = relationship(
        "User",
        back_populates="ticket_assignments",
        foreign_keys=[assignee_id],
    )
    assigner = relationship(
        "User",
        back_populates="assignments_created",
        foreign_keys=[assigned_by],
    )
