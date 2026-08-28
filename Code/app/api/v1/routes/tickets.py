from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import AnyBusinessRoleContext, RequesterContext
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.common import PageData, SuccessResponse
from app.schemas.ticket import (
    TicketCreateRequest,
    TicketDetail,
    TicketListQuery,
    TicketSummaryResponse,
)
from app.services import ticket_service


router = APIRouter(prefix="/tickets", tags=["Tickets"])


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
