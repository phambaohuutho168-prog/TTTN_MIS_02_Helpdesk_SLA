from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import (
    AdminContext,
    AnyBusinessRoleContext,
    RequesterContext,
)
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.common import PageData, SuccessResponse
from app.schemas.assignment import AssignmentRequest
from app.schemas.ticket import (
    TicketCreateRequest,
    TicketDetail,
    TicketListQuery,
    TicketSummaryResponse,
)
from app.services import ticket_service
from app.schemas.ticket_detail import (
    AssignmentResponse,
    CommentResponse,
    StatusHistoryResponse,
    TicketDetailResponse,
    TicketTimelineQuery,
)
from app.services import assignment_service, ticket_detail_service


router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.put(
    "/{ticket_id}/assignment",
    response_model=SuccessResponse[AssignmentResponse],
    summary="ASN-01 - Phân công hoặc tái phân công ticket",
)
async def assign_ticket(
    request: Request,
    ticket_id: int,
    payload: AssignmentRequest,
    context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    result = await assignment_service.assign_ticket(
        session,
        ticket_id=ticket_id,
        actor=context.user,
        payload=payload,
        ip_address=request.client.host if request.client is not None else None,
    )
    return success_response(
        request,
        data=result.data,
        code=result.response_code,
        message=result.message,
    )


@router.get(
    "/{ticket_id}",
    response_model=SuccessResponse[TicketDetailResponse],
    summary="TKT-03 - Xem chi tiết ticket",
)
async def get_ticket_detail(
    request: Request,
    ticket_id: int,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await ticket_detail_service.get_ticket_detail(
        session,
        ticket_id=ticket_id,
        current_user=context.user,
    )
    return success_response(
        request,
        data=data,
        code="TICKET_DETAIL_RETRIEVED",
        message="Lấy chi tiết ticket thành công.",
    )


@router.get(
    "/{ticket_id}/status-history",
    response_model=SuccessResponse[PageData[StatusHistoryResponse]],
    summary="TKT-06 - Xem lịch sử trạng thái ticket",
)
async def get_ticket_status_history(
    request: Request,
    ticket_id: int,
    query: Annotated[TicketTimelineQuery, Query()],
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await ticket_detail_service.list_status_history(
        session,
        ticket_id=ticket_id,
        current_user=context.user,
        query=query,
    )
    return success_response(
        request,
        data=data,
        code="TICKET_STATUS_HISTORY_RETRIEVED",
        message="Lấy lịch sử trạng thái ticket thành công.",
    )


@router.get(
    "/{ticket_id}/comments",
    response_model=SuccessResponse[PageData[CommentResponse]],
    summary="COM-01 - Xem trao đổi của ticket",
)
async def get_ticket_comments(
    request: Request,
    ticket_id: int,
    query: Annotated[TicketTimelineQuery, Query()],
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await ticket_detail_service.list_comments(
        session,
        ticket_id=ticket_id,
        current_user=context.user,
        query=query,
    )
    return success_response(
        request,
        data=data,
        code="TICKET_COMMENTS_RETRIEVED",
        message="Lấy trao đổi ticket thành công.",
    )


@router.get(
    "/{ticket_id}/assignments",
    response_model=SuccessResponse[PageData[AssignmentResponse]],
    summary="ASN-02 - Xem lịch sử phân công ticket",
)
async def get_ticket_assignments(
    request: Request,
    ticket_id: int,
    query: Annotated[TicketTimelineQuery, Query()],
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await ticket_detail_service.list_assignments(
        session,
        ticket_id=ticket_id,
        current_user=context.user,
        query=query,
    )
    return success_response(
        request,
        data=data,
        code="TICKET_ASSIGNMENTS_RETRIEVED",
        message="Lấy lịch sử phân công ticket thành công.",
    )


@router.get(
    "",
    response_model=SuccessResponse[PageData[TicketSummaryResponse]],
    summary="TKT-02 - Danh sách, tìm kiếm và lọc ticket",
)
async def list_tickets(
    request: Request,
    filters: Annotated[TicketListQuery, Query()],
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await ticket_service.list_tickets(
        session,
        current_user=context.user,
        query=filters,
    )
    return success_response(
        request,
        data=data,
        code="TICKET_LISTED",
        message="Lấy danh sách ticket thành công.",
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[TicketDetail],
    summary="TKT-01 - Tạo ticket",
)
async def create_ticket(
    request: Request,
    payload: TicketCreateRequest,
    context: RequesterContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await ticket_service.create_ticket(
        session,
        requester=context.user,
        payload=payload,
    )
    return success_response(
        request,
        data=data,
        code="TICKET_CREATED",
        message="Tạo ticket thành công.",
    )
