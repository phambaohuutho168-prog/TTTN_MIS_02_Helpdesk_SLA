from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import AdminContext, AnyBusinessRoleContext
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.catalog import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
    PriorityCreateRequest,
    PriorityResponse,
    PriorityUpdateRequest,
    TicketStatusResponse,
)
from app.schemas.common import SuccessResponse
from app.services import catalog_service


router = APIRouter(tags=["Catalogs"])
admin_router = APIRouter(prefix="/admin", tags=["Admin - Catalogs"])


@router.get(
    "/categories",
    response_model=SuccessResponse[list[CategoryResponse]],
    summary="CAT-01 - Danh mục Ticket",
)
async def list_categories(
    request: Request,
    _context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    is_active: bool | None = True,
):
    data = await catalog_service.list_categories(
        session,
        q=q,
        is_active=is_active,
    )
    return success_response(
        request,
        data=data,
        message="Lấy danh mục Ticket thành công.",
    )


@router.get(
    "/priorities",
    response_model=SuccessResponse[list[PriorityResponse]],
    summary="CAT-02 - Danh mục mức ưu tiên",
)
async def list_priorities(
    request: Request,
    _context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    is_active: bool | None = True,
):
    data = await catalog_service.list_priorities(
        session,
        q=q,
        is_active=is_active,
    )
    return success_response(
        request,
        data=data,
        message="Lấy danh mục mức ưu tiên thành công.",
    )


@router.get(
    "/ticket-statuses",
    response_model=SuccessResponse[list[TicketStatusResponse]],
    summary="CAT-03 - Danh mục trạng thái Ticket",
)
async def list_ticket_statuses(
    request: Request,
    _context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await catalog_service.list_ticket_statuses(session)
    return success_response(
        request,
        data=data,
        message="Lấy danh mục trạng thái Ticket thành công.",
    )


@admin_router.post(
    "/categories",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[CategoryResponse],
    summary="CAT-04 - Tạo danh mục Ticket",
)
async def create_category(
    request: Request,
    payload: CategoryCreateRequest,
    _context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await catalog_service.create_category(session, payload)
    return success_response(
        request,
        data=data,
        code="CATEGORY_CREATED",
        message="Tạo danh mục Ticket thành công.",
    )


@admin_router.patch(
    "/categories/{category_id}",
    response_model=SuccessResponse[CategoryResponse],
    summary="CAT-05 - Cập nhật danh mục Ticket",
)
async def update_category(
    request: Request,
    category_id: int,
    payload: CategoryUpdateRequest,
    _context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await catalog_service.update_category(
        session,
        category_id=category_id,
        payload=payload,
    )
    return success_response(
        request,
        data=data,
        message="Cập nhật danh mục Ticket thành công.",
    )


@admin_router.post(
    "/priorities",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[PriorityResponse],
    summary="CAT-06 - Tạo mức ưu tiên",
)
async def create_priority(
    request: Request,
    payload: PriorityCreateRequest,
    _context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await catalog_service.create_priority(session, payload)
    return success_response(
        request,
        data=data,
        code="PRIORITY_CREATED",
        message="Tạo mức ưu tiên thành công.",
    )


@admin_router.patch(
    "/priorities/{priority_id}",
    response_model=SuccessResponse[PriorityResponse],
    summary="CAT-07 - Cập nhật mức ưu tiên",
)
async def update_priority(
    request: Request,
    priority_id: int,
    payload: PriorityUpdateRequest,
    _context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await catalog_service.update_priority(
        session,
        priority_id=priority_id,
        payload=payload,
    )
    return success_response(
        request,
        data=data,
        message="Cập nhật mức ưu tiên thành công.",
    )
