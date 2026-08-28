from anyio import to_thread
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rbac import RoleCode
from app.core.security import hash_password
from app.models.user import User
from app.repositories import audit_repository, role_repository, user_repository
from app.schemas.common import PageData
from app.schemas.user import (
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    ProfileUpdateRequest,
    UserDetail,
)
from app.services.auth_service import build_user_detail


async def update_own_profile(
    session: AsyncSession,
    user: User,
    payload: ProfileUpdateRequest,
) -> UserDetail:
    updated = await user_repository.update_profile(
        session,
        user,
        full_name=payload.full_name,
        phone=payload.phone,
        provided_fields=payload.model_fields_set,
    )
    return build_user_detail(updated)


async def list_admin_users(
    session: AsyncSession,
    *,
    q: str | None,
    department_id: int | None,
    role_code: RoleCode | None,
    is_active: bool | None,
    page: int,
    page_size: int,
) -> PageData[UserDetail]:
    users, total = await user_repository.list_users(
        session,
        q=q,
        department_id=department_id,
        role_code=role_code.value if role_code else None,
        is_active=is_active,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return PageData[UserDetail](
        items=[build_user_detail(user) for user in users],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=(total + page_size - 1) // page_size,
    )


async def get_admin_user(session: AsyncSession, user_id: int) -> UserDetail:
    user = await user_repository.get_user_by_id(session, user_id)
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "Không tìm thấy người dùng.")
    return build_user_detail(user)


async def create_admin_user(
    session: AsyncSession,
    *,
    actor: User,
    payload: AdminUserCreateRequest,
    ip_address: str | None = None,
) -> UserDetail:
    if await user_repository.get_user_by_email(session, str(payload.email)):
        raise AppError(409, "USER_EMAIL_CONFLICT", "Email đã được sử dụng.")

    if payload.department_id is not None:
        department = await user_repository.get_department_by_id(
            session,
            payload.department_id,
        )
        if department is None:
            raise AppError(404, "DEPARTMENT_NOT_FOUND", "Không tìm thấy phòng ban.")

    roles = await role_repository.get_roles_by_ids(
        session,
        [int(role_id) for role_id in payload.role_ids],
    )
    if len(roles) != len(payload.role_ids) or any(not role.is_active for role in roles):
        raise AppError(404, "ROLE_NOT_FOUND", "Không tìm thấy vai trò hoạt động.")

    password_hash = await to_thread.run_sync(hash_password, payload.password)
    try:
        user = await user_repository.create_user_record(
            session,
            email=str(payload.email),
            full_name=payload.full_name,
            password_hash=password_hash,
            phone=payload.phone,
            department_id=payload.department_id,
            is_active=payload.is_active,
        )
        for role in roles:
            await role_repository.create_role_assignment(
                session,
                user_id=user.user_id,
                role_id=role.role_id,
                assigned_by=actor.user_id,
            )
        await audit_repository.append_audit(
            session,
            actor_user_id=actor.user_id,
            action_code="USER_CREATED",
            entity_type="USER",
            entity_id=user.user_id,
            new_value={
                "email": user.email,
                "full_name": user.full_name,
                "phone": user.phone,
                "department_id": user.department_id,
                "is_active": user.is_active,
                "role_ids": sorted(role.role_id for role in roles),
            },
            ip_address=ip_address,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "USER_EMAIL_CONFLICT", "Email đã được sử dụng.") from exc

    created = await user_repository.get_user_by_id(session, user.user_id)
    if created is None:
        raise AppError(500, "INTERNAL_SERVER_ERROR", "Không thể tải tài khoản vừa tạo.")
    return build_user_detail(created)


async def update_admin_user(
    session: AsyncSession,
    *,
    user_id: int,
    actor: User,
    payload: AdminUserUpdateRequest,
    ip_address: str | None = None,
) -> UserDetail:
    user = await user_repository.get_user_by_id(session, user_id)
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "Không tìm thấy người dùng.")

    fields = payload.model_fields_set
    if "department_id" in fields and payload.department_id is not None:
        department = await user_repository.get_department_by_id(
            session,
            payload.department_id,
        )
        if department is None:
            raise AppError(404, "DEPARTMENT_NOT_FOUND", "Không tìm thấy phòng ban.")

    if (
        "is_active" in fields
        and payload.is_active is False
        and user.is_active
        and RoleCode.ADMIN.value in user.role_codes
        and await role_repository.count_active_admin_users(session) <= 1
    ):
        raise AppError(
            409,
            "LAST_ADMIN_ROLE_FORBIDDEN",
            "Không được vô hiệu hóa quản trị viên hoạt động cuối cùng.",
        )

    audited_fields = ("full_name", "phone", "department_id", "is_active")
    old_value = {
        field: getattr(user, field)
        for field in audited_fields
        if field in fields
    }
    if "full_name" in fields:
        user.full_name = payload.full_name  # type: ignore[assignment]
    if "phone" in fields:
        user.phone = payload.phone
    if "department_id" in fields:
        user.department_id = payload.department_id
    if "is_active" in fields:
        user.is_active = payload.is_active  # type: ignore[assignment]

    new_value = {
        field: getattr(user, field)
        for field in audited_fields
        if field in fields
    }
    await audit_repository.append_audit(
        session,
        actor_user_id=actor.user_id,
        action_code=(
            "USER_STATUS_CHANGED" if "is_active" in fields else "USER_UPDATED"
        ),
        entity_type="USER",
        entity_id=user.user_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
    )
    await session.commit()

    updated = await user_repository.get_user_by_id(session, user.user_id)
    if updated is None:
        raise AppError(404, "USER_NOT_FOUND", "Không tìm thấy người dùng.")
    return build_user_detail(updated)
