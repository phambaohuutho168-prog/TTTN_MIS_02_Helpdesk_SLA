from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import ProcessorOrAdminContext
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.common import PageData, SuccessResponse
from app.schemas.escalation import SLABreachQuery, SLAEventResponse
from app.services import escalation_service


router = APIRouter(prefix="/sla", tags=["SLA - Escalation"])


@router.get(
    "/breaches",
    response_model=SuccessResponse[PageData[SLAEventResponse]],
    summary="SLA-02 - Danh sách cảnh báo và escalation SLA",
)
async def list_sla_breaches(
    request: Request,
    filters: Annotated[SLABreachQuery, Query()],
    context: ProcessorOrAdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await escalation_service.list_sla_events(
        session,
        query=filters,
        current_user_id=context.user.user_id,
        role_codes=set(context.user.role_codes),
    )
    return success_response(
        request,
        data=data,
        code="SLA_EVENTS_LISTED",
        message="Lấy danh sách cảnh báo và escalation SLA thành công.",
    )
