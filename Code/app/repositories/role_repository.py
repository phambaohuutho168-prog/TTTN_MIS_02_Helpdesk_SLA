from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import RoleCode
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole


async def list_roles(session: AsyncSession) -> list[Role]:
    result = await session.execute(select(Role).order_by(Role.role_id))
    return list(result.scalars().all())


async def get_role_by_id(session: AsyncSession, role_id: int) -> Role | None:
    return await session.get(Role, role_id)


async def get_roles_by_ids(
    session: AsyncSession,
    role_ids: list[int],
) -> list[Role]:
    result = await session.execute(
        select(Role).where(Role.role_id.in_(role_ids)).order_by(Role.role_id)
    )
    return list(result.scalars().all())


async def get_role_assignment(
    session: AsyncSession,
    *,
    user_id: int,
    role_id: int,
) -> UserRole | None:
    return await session.get(UserRole, (user_id, role_id))


async def create_role_assignment(
    session: AsyncSession,
    *,
    user_id: int,
    role_id: int,
    assigned_by: int,
) -> UserRole:
    assignment = UserRole(
        user_id=user_id,
        role_id=role_id,
        assigned_by=assigned_by,
    )
    session.add(assignment)
    await session.flush()
    return assignment


async def delete_role_assignment(
    session: AsyncSession,
    assignment: UserRole,
) -> None:
    await session.delete(assignment)
    await session.flush()


async def count_active_admin_users(session: AsyncSession) -> int:
    statement = (
        select(func.count(func.distinct(User.user_id)))
        .select_from(User)
        .join(UserRole, UserRole.user_id == User.user_id)
        .join(Role, Role.role_id == UserRole.role_id)
        .where(
            User.is_active.is_(True),
            Role.is_active.is_(True),
            Role.role_code == RoleCode.ADMIN.value,
        )
    )
    return int((await session.execute(statement)).scalar_one())
