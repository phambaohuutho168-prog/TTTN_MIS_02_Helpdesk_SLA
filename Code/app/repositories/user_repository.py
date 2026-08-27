from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.user_role import UserRole


USER_LOAD_OPTIONS = (
    selectinload(User.department),
    selectinload(User.user_roles).selectinload(UserRole.role),
)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    statement = (
        select(User)
        .where(func.lower(User.email) == email.strip().lower())
        .options(*USER_LOAD_OPTIONS)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    statement = (
        select(User)
        .where(User.user_id == user_id)
        .options(*USER_LOAD_OPTIONS)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def update_profile(
    session: AsyncSession,
    user: User,
    *,
    full_name: str | None,
    phone: str | None,
    provided_fields: set[str],
) -> User:
    if "full_name" in provided_fields:
        user.full_name = full_name  # type: ignore[assignment]
    if "phone" in provided_fields:
        user.phone = phone
    await session.commit()
    return await get_user_by_id(session, user.user_id)  # type: ignore[return-value]
