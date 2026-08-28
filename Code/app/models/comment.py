from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class Comment(Base):
    """Comment metadata needed to validate attachment-to-ticket ownership.

    Comment endpoints are implemented in their own module; defining the model
    here keeps the Attachment foreign key consistent with the Data Dictionary.
    """

    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint(
            "length(trim(content)) > 0",
            name="ck_comments_content_not_blank",
        ),
        CheckConstraint(
            "visibility IN ('PUBLIC', 'INTERNAL')",
            name="ck_comments_visibility_domain",
        ),
        CheckConstraint(
            "comment_type IN ('REPLY', 'REQUEST_INFO', 'SYSTEM_NOTE')",
            name="ck_comments_type_domain",
        ),
    )

    comment_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    ticket_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PUBLIC",
        server_default="PUBLIC",
    )
    comment_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="REPLY",
        server_default="REPLY",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ticket = relationship("Ticket", back_populates="comments")
    author = relationship("User", back_populates="comments")
    attachments = relationship("Attachment", back_populates="comment")
