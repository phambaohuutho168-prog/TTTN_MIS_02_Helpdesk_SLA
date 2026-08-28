from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(trim(full_name)) > 0", name="ck_users_full_name_not_blank"),
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    department_id: Mapped[int | None] = mapped_column(
        BIGINT_PK,
        ForeignKey("departments.department_id", ondelete="SET NULL"),
        nullable=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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

    department = relationship("Department", back_populates="users")
    user_roles = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.user_id",
    )
    tickets = relationship("Ticket", back_populates="requester")
    comments = relationship("Comment", back_populates="author")
    uploaded_attachments = relationship("Attachment", back_populates="uploader")
    ticket_assignments = relationship(
        "TicketAssignment",
        back_populates="assignee",
        foreign_keys="TicketAssignment.assignee_id",
    )
    assignments_created = relationship(
        "TicketAssignment",
        back_populates="assigner",
        foreign_keys="TicketAssignment.assigned_by",
    )

    @property
    def role_codes(self) -> list[str]:
        return sorted(
            user_role.role.role_code
            for user_role in self.user_roles
            if user_role.role is not None and user_role.role.is_active
        )
