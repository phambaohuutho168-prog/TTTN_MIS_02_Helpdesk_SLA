from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(
            "length(trim(file_name)) > 0",
            name="ck_attachments_file_name_not_blank",
        ),
        CheckConstraint(
            "length(trim(storage_path)) > 0",
            name="ck_attachments_storage_path_not_blank",
        ),
        CheckConstraint(
            "file_size > 0",
            name="ck_attachments_file_size_positive",
        ),
        Index("ix_attachments_ticket_uploaded", "ticket_id", "uploaded_at"),
    )

    attachment_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    ticket_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    comment_id: Mapped[int | None] = mapped_column(
        BIGINT_PK,
        ForeignKey("comments.comment_id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_by: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
    )
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BIGINT_PK, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    ticket = relationship("Ticket", back_populates="attachments")
    comment = relationship("Comment", back_populates="attachments")
    uploader = relationship("User", back_populates="uploaded_attachments")
