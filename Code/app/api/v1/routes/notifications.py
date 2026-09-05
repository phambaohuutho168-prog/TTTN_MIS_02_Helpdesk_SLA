from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import AnyBusinessRoleContext
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.common import PageData, SuccessResponse
from app.schemas.notification import (
    BulkUpdateResponse,
    NotificationListQuery,
    NotificationResponse,
)
from app.services import notification_service


router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=SuccessResponse[PageData[NotificationResponse]],
    summary="NTF-01 - Lấy hộp thông báo",
)
async def list_notifications(
    request: Request,
    filters: Annotated[NotificationListQuery, Query()],
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await notification_service.list_notifications(
        session,
        current_user_id=context.user.user_id,
        query=filters,
    )
    return success_response(
        request,
        data=data,
        code="NOTIFICATIONS_LISTED",
        message="Lấy hộp thông báo thành công.",
    )


@router.patch(
    "/read-all",
    response_model=SuccessResponse[BulkUpdateResponse],
    summary="NTF-03 - Đánh dấu tất cả thông báo đã đọc",
)
async def mark_all_notifications_read(
    request: Request,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
    type: Annotated[str | None, Query(max_length=30)] = None,
):
    data = await notification_service.mark_all_notifications_read(
        session,
        current_user_id=context.user.user_id,
        notification_type=type,
    )
    return success_response(
        request,
        data=data,
        code="NOTIFICATIONS_MARKED_READ",
        message=(
            "Đánh dấu các thông báo phù hợp là đã đọc thành công."
        ),
    )


@router.patch(
    "/{notification_id}/read",
    response_model=SuccessResponse[NotificationResponse],
    summary="NTF-02 - Đánh dấu một thông báo đã đọc",
)
async def mark_notification_read(
    request: Request,
    notification_id: int,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await notification_service.mark_notification_read(
        session,
        notification_id=notification_id,
        current_user_id=context.user.user_id,
    )
    return success_response(
        request,
        data=data,
        code="NOTIFICATION_MARKED_READ",
        message="Đánh dấu thông báo là đã đọc thành công.",
    )
