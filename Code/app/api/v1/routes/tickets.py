from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import RequesterContext
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.common import SuccessResponse
from app.schemas.ticket import TicketCreateRequest, TicketDetail
from app.services import ticket_service


router = APIRouter(prefix="/tickets", tags=["Tickets"])


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
