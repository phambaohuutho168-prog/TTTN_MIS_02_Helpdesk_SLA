from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rbac import RoleCode
from app.models.user import User
from app.repositories import role_repository, user_repository
from app.schemas.user import DepartmentResponse, RoleResponse, UserDetail
from app.services.auth_service import build_user_detail


async def list_admin_roles(session: AsyncSession) -> list[RoleResponse]:
    roles = await role_repository.list_roles(session)
    return [RoleResponse.model_validate(role) for role in roles]


async def list_admin_departments(
    session: AsyncSession,
    *,
    q: str | None,
    is_active: bool | None,
) -> list[DepartmentResponse]:
    departments = await user_repository.list_departments(
        session,
        q=q,
        is_active=is_active,
    )
    return [DepartmentResponse.model_validate(item) for item in departments]


async def assign_role(
    session: AsyncSession,
    *,
    actor: User,
    user_id: int,
    role_id: int,
) -> UserDetail:
    user = await user_repository.get_user_by_id(session, user_id)
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "Không tìm thấy người dùng.")

    role = await role_repository.get_role_by_id(session, role_id)
    if role is None or not role.is_active:
        raise AppError(404, "ROLE_NOT_FOUND", "Không tìm thấy vai trò hoạt động.")

    assignment = await role_repository.get_role_assignment(
        session,
        user_id=user_id,
        role_id=role_id,
    )
    if assignment is not None:
        raise AppError(409, "ROLE_ALREADY_ASSIGNED", "Người dùng đã có vai trò này.")

    await role_repository.create_role_assignment(
        session,
        user_id=user_id,
        role_id=role_id,
        assigned_by=actor.user_id,
    )
    await session.commit()

    updated = await user_repository.get_user_by_id(session, user_id)
    if updated is None:
        raise AppError(404, "USER_NOT_FOUND", "Không tìm thấy người dùng.")
    return build_user_detail(updated)


async def remove_role(
    session: AsyncSession,
    *,
    user_id: int,
    role_id: int,
) -> None:
    user = await user_repository.get_user_by_id(session, user_id)
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "Không tìm thấy người dùng.")

    role = await role_repository.get_role_by_id(session, role_id)
    if role is None:
        raise AppError(404, "ROLE_NOT_FOUND", "Không tìm thấy vai trò.")

    assignment = await role_repository.get_role_assignment(
        session,
        user_id=user_id,
        role_id=role_id,
    )
    if assignment is None:
        raise AppError(
            404,
            "ROLE_ASSIGNMENT_NOT_FOUND",
            "Không tìm thấy lần gán vai trò cần thu hồi.",
        )

    if (
        role.role_code == RoleCode.ADMIN.value
        and role.is_active
        and user.is_active
        and await role_repository.count_active_admin_users(session) <= 1
    ):
        raise AppError(
            409,
            "LAST_ADMIN_ROLE_FORBIDDEN",
            "Không được thu hồi vai trò của quản trị viên hoạt động cuối cùng.",
        )

    await role_repository.delete_role_assignment(session, assignment)
    await session.commit()
