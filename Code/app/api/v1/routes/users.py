from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import AdminContext, AnyBusinessRoleContext
from app.core.rbac import RoleCode
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.common import PageData, SuccessResponse
from app.schemas.user import (
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    ProfileUpdateRequest,
    UserDetail,
)
from app.services import role_service, user_service


router = APIRouter(prefix="/users", tags=["Users"])
admin_router = APIRouter(prefix="/admin/users", tags=["Admin - Users"])


@router.patch(
    "/me",
    response_model=SuccessResponse[UserDetail],
    summary="AUTH-05 - Cập nhật hồ sơ cá nhân",
)
async def update_me(
    request: Request,
    payload: ProfileUpdateRequest,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    user_detail = await user_service.update_own_profile(
        session,
        context.user,
        payload,
    )
    return success_response(
        request,
        data=user_detail,
        message="Cập nhật hồ sơ thành công.",
    )


@admin_router.get(
    "",
    response_model=SuccessResponse[PageData[UserDetail]],
    summary="ADM-01 - Tra cứu tài khoản",
)
async def list_users(
    request: Request,
    _context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    department_id: Annotated[int | None, Query(gt=0)] = None,
    role_code: RoleCode | None = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    data = await user_service.list_admin_users(
        session,
        q=q,
        department_id=department_id,
        role_code=role_code,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return success_response(
        request,
        data=data,
        message="Lấy danh sách tài khoản thành công.",
    )


@admin_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[UserDetail],
    summary="ADM-00 - Tạo tài khoản",
)
async def create_user(
    request: Request,
    payload: AdminUserCreateRequest,
    context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await user_service.create_admin_user(
        session,
        actor=context.user,
        payload=payload,
    )
    return success_response(
        request,
        data=data,
        message="Tạo tài khoản thành công.",
    )


@admin_router.get(
    "/{user_id}",
    response_model=SuccessResponse[UserDetail],
    summary="ADM-02 - Xem chi tiết tài khoản",
)
async def get_user(
    request: Request,
    user_id: int,
    _context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await user_service.get_admin_user(session, user_id)
    return success_response(
        request,
        data=data,
        message="Lấy thông tin tài khoản thành công.",
    )


@admin_router.patch(
    "/{user_id}",
    response_model=SuccessResponse[UserDetail],
    summary="ADM-03 - Cập nhật tài khoản",
)
async def update_user(
    request: Request,
    user_id: int,
    payload: AdminUserUpdateRequest,
    context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await user_service.update_admin_user(
        session,
        user_id=user_id,
        actor=context.user,
        payload=payload,
    )
    return success_response(
        request,
        data=data,
        message="Cập nhật tài khoản thành công.",
    )


@admin_router.put(
    "/{user_id}/roles/{role_id}",
    response_model=SuccessResponse[UserDetail],
    summary="ADM-04 - Gán vai trò",
)
async def assign_user_role(
    request: Request,
    user_id: int,
    role_id: int,
    context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await role_service.assign_role(
        session,
        actor=context.user,
        user_id=user_id,
        role_id=role_id,
    )
    return success_response(
        request,
        data=data,
        message="Gán vai trò thành công.",
    )


@admin_router.delete(
    "/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="ADM-05 - Thu hồi vai trò",
)
async def remove_user_role(
    user_id: int,
    role_id: int,
    context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await role_service.remove_role(
        session,
        actor=context.user,
        user_id=user_id,
        role_id=role_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
