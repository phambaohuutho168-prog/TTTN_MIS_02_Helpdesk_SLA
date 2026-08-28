from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class TicketStatus(Base):
    __tablename__ = "ticket_statuses"

    status_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    status_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    tickets = relationship("Ticket", back_populates="current_status")
