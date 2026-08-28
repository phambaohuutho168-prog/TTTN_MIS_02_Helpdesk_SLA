from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import AnyBusinessRoleContext
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.comment import CommentCreateRequest, CommentUpdateRequest
from app.schemas.common import SuccessResponse
from app.schemas.ticket_detail import CommentResponse
from app.services import comment_service


router = APIRouter(tags=["Comments"])


@router.post(
    "/tickets/{ticket_id}/comments",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[CommentResponse],
    summary="COM-02 - Tạo trao đổi hoặc ghi chú nội bộ",
)
async def create_comment(
    request: Request,
    ticket_id: int,
    payload: CommentCreateRequest,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await comment_service.create_comment(
        session,
        ticket_id=ticket_id,
        actor=context.user,
        payload=payload,
        ip_address=request.client.host if request.client is not None else None,
    )
    return success_response(
        request,
        data=data,
        code="COMMENT_CREATED",
        message="Tạo trao đổi thành công.",
    )


@router.patch(
    "/comments/{comment_id}",
    response_model=SuccessResponse[CommentResponse],
    summary="COM-03 - Chỉnh sửa nội dung trao đổi",
)
async def update_comment(
    request: Request,
    comment_id: int,
    payload: CommentUpdateRequest,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await comment_service.update_comment(
        session,
        comment_id=comment_id,
        actor=context.user,
        payload=payload,
        ip_address=request.client.host if request.client is not None else None,
    )
    return success_response(
        request,
        data=data,
        code="COMMENT_UPDATED",
        message="Cập nhật trao đổi thành công.",
    )
