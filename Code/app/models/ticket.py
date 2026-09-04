from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_tickets_title_not_blank",
        ),
        Index("ix_tickets_requester_created", "requester_id", "created_at"),
        Index("ix_tickets_current_status", "current_status_code"),
    )

    ticket_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    ticket_code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
    )
    requester_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    category_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("categories.category_id", ondelete="RESTRICT"),
        nullable=False,
    )
    priority_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("priorities.priority_id", ondelete="RESTRICT"),
        nullable=False,
    )
    current_status_code: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("ticket_statuses.status_code", ondelete="RESTRICT"),
        nullable=False,
        default="NEW",
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    first_response_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    requester = relationship("User", back_populates="tickets")
    category = relationship("Category", back_populates="tickets")
    priority = relationship("Priority", back_populates="tickets")
    current_status = relationship("TicketStatus", back_populates="tickets")
    comments = relationship(
        "Comment",
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attachments = relationship(
        "Attachment",
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    assignments = relationship(
        "TicketAssignment",
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TicketAssignment.assigned_at",
    )
    resolutions = relationship(
        "TicketResolution",
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TicketResolution.cycle_no",
    )
    status_history = relationship(
        "TicketStatusHistory",
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TicketStatusHistory.changed_at",
    )
    sla_records = relationship(
        "TicketSLA",
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TicketSLA.cycle_no",
    )
    audit_logs = relationship(
        "AuditLog",
        back_populates="ticket",
        foreign_keys="AuditLog.ticket_id",
    )
    notifications = relationship(
        "Notification",
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def current_assignment(self):
        return next(
            (assignment for assignment in self.assignments if assignment.is_current),
            None,
        )
