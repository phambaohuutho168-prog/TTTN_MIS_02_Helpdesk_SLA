from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import AnyBusinessRoleContext
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.common import SuccessResponse
from app.schemas.sla import TicketSLAResponse
from app.services import sla_service, ticket_detail_service


router = APIRouter(prefix="/tickets", tags=["SLA"])


@router.get(
    "/{ticket_id}/sla",
    response_model=SuccessResponse[TicketSLAResponse],
    summary="SLA-01 - Xem SLA của ticket",
)
async def get_ticket_sla(
    request: Request,
    ticket_id: int,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    ticket = await ticket_detail_service.load_scoped_ticket(
        session,
        ticket_id=ticket_id,
        current_user=context.user,
    )
    data = sla_service.build_ticket_sla_response(ticket)
    return success_response(
        request,
        data=data,
        code="TICKET_SLA_RETRIEVED",
        message="Lấy thông tin SLA của ticket thành công.",
    )
