from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.department import Department
from app.models.role import Role
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
        .execution_options(populate_existing=True)
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


async def list_users(
    session: AsyncSession,
    *,
    q: str | None,
    department_id: int | None,
    role_code: str | None,
    is_active: bool | None,
    offset: int,
    limit: int,
) -> tuple[list[User], int]:
    filters = []
    if q:
        search = f"%{q.strip().lower()}%"
        filters.append(
            or_(
                func.lower(User.email).like(search),
                func.lower(User.full_name).like(search),
            )
        )
    if department_id is not None:
        filters.append(User.department_id == department_id)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))

    statement = select(User)
    count_statement = select(func.count(func.distinct(User.user_id))).select_from(User)
    if role_code is not None:
        statement = statement.join(UserRole, UserRole.user_id == User.user_id).join(
            Role,
            Role.role_id == UserRole.role_id,
        )
        count_statement = count_statement.join(
            UserRole,
            UserRole.user_id == User.user_id,
        ).join(Role, Role.role_id == UserRole.role_id)
        filters.append(Role.role_code == role_code)

    statement = (
        statement.where(*filters)
        .options(*USER_LOAD_OPTIONS)
        .order_by(User.user_id)
        .offset(offset)
        .limit(limit)
        .distinct()
    )
    count_statement = count_statement.where(*filters)

    result = await session.execute(statement)
    total = int((await session.execute(count_statement)).scalar_one())
    return list(result.scalars().unique().all()), total


async def create_user_record(
    session: AsyncSession,
    *,
    email: str,
    full_name: str,
    password_hash: str,
    phone: str | None,
    department_id: int | None,
    is_active: bool,
) -> User:
    user = User(
        email=email,
        full_name=full_name,
        password_hash=password_hash,
        phone=phone,
        department_id=department_id,
        is_active=is_active,
    )
    session.add(user)
    await session.flush()
    return user


async def get_department_by_id(
    session: AsyncSession,
    department_id: int,
) -> Department | None:
    return await session.get(Department, department_id)


async def list_departments(
    session: AsyncSession,
    *,
    q: str | None,
    is_active: bool | None,
) -> list[Department]:
    statement = select(Department)
    if q:
        statement = statement.where(
            func.lower(Department.department_name).like(f"%{q.strip().lower()}%")
        )
    if is_active is not None:
        statement = statement.where(Department.is_active.is_(is_active))
    result = await session.execute(statement.order_by(Department.department_name))
    return list(result.scalars().all())
