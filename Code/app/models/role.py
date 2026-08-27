from sqlalchemy import Boolean, CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BIGINT_PK, Base


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint(
            "role_code IN ('REQUESTER','PROCESSOR','ADMIN')",
            name="ck_roles_code",
        ),
    )

    role_id: Mapped[int] = mapped_column(
        BIGINT_PK,
        primary_key=True,
        autoincrement=True,
    )
    role_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user_roles = relationship("UserRole", back_populates="role")
