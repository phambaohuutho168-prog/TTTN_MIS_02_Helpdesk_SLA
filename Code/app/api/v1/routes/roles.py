from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import AdminContext
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.common import SuccessResponse
from app.schemas.user import DepartmentResponse, RoleResponse
from app.services import role_service


router = APIRouter(prefix="/admin", tags=["Admin - Roles"])


@router.get(
    "/roles",
    response_model=SuccessResponse[list[RoleResponse]],
    summary="ADM-06 - Danh mục vai trò",
)
async def list_roles(
    request: Request,
    _context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await role_service.list_admin_roles(session)
    return success_response(
        request,
        data=data,
        message="Lấy danh mục vai trò thành công.",
    )


@router.get(
    "/departments",
    response_model=SuccessResponse[list[DepartmentResponse]],
    summary="ADM-07 - Danh mục phòng ban",
)
async def list_departments(
    request: Request,
    _context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    is_active: bool | None = None,
):
    data = await role_service.list_admin_departments(
        session,
        q=q,
        is_active=is_active,
    )
    return success_response(
        request,
        data=data,
        message="Lấy danh mục phòng ban thành công.",
    )
