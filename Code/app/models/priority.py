from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class Priority(Base):
    __tablename__ = "priorities"
    __table_args__ = (
        CheckConstraint(
            "priority_code IN ('P1', 'P2', 'P3', 'P4')",
            name="ck_priorities_code_domain",
        ),
        CheckConstraint(
            "priority_level BETWEEN 1 AND 4",
            name="ck_priorities_level_range",
        ),
        CheckConstraint(
            "length(trim(priority_name)) > 0",
            name="ck_priorities_name_not_blank",
        ),
    )

    priority_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    priority_code: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
    )
    priority_level: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
    )
    priority_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tickets = relationship("Ticket", back_populates="priority")
