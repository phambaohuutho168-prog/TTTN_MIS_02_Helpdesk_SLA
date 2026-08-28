from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import (
    AdminContext,
    AnyBusinessRoleContext,
    RequesterContext,
)
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.common import SuccessResponse
from app.schemas.ticket_detail import TicketDetailResponse
from app.schemas.workflow import (
    CloseRequest,
    ProvideInfoRequest,
    RejectRequest,
    ReopenRequest,
    RequestInfoRequest,
    ResolveRequest,
    TransitionReasonRequest,
)
from app.services import workflow_service


router = APIRouter(prefix="/tickets", tags=["Ticket Workflow"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


def _response(request: Request, result):
    return success_response(
        request,
        data=result.data,
        code=result.response_code,
        message=result.message,
    )


@router.post(
    "/{ticket_id}/start",
    response_model=SuccessResponse[TicketDetailResponse],
    summary="WF-01 - Bắt đầu xử lý ticket",
)
async def start_ticket(
    request: Request,
    ticket_id: int,
    payload: TransitionReasonRequest,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    result = await workflow_service.start_ticket(
        session,
        ticket_id=ticket_id,
        actor=context.user,
        payload=payload,
        ip_address=_client_ip(request),
    )
    return _response(request, result)


@router.post(
    "/{ticket_id}/request-info",
    response_model=SuccessResponse[TicketDetailResponse],
    summary="WF-02 - Yêu cầu bổ sung thông tin",
)
async def request_information(
    request: Request,
    ticket_id: int,
    payload: RequestInfoRequest,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    result = await workflow_service.request_information(
        session,
        ticket_id=ticket_id,
        actor=context.user,
        payload=payload,
        ip_address=_client_ip(request),
    )
    return _response(request, result)


@router.post(
    "/{ticket_id}/provide-info",
    response_model=SuccessResponse[TicketDetailResponse],
    summary="WF-03 - Bổ sung thông tin",
)
async def provide_information(
    request: Request,
    ticket_id: int,
    payload: ProvideInfoRequest,
    context: RequesterContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    result = await workflow_service.provide_information(
        session,
        ticket_id=ticket_id,
        actor=context.user,
        payload=payload,
        ip_address=_client_ip(request),
    )
    return _response(request, result)


@router.post(
    "/{ticket_id}/resolve",
    response_model=SuccessResponse[TicketDetailResponse],
    summary="WF-04 - Ghi nhận kết quả xử lý",
)
async def resolve_ticket(
    request: Request,
    ticket_id: int,
    payload: ResolveRequest,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    result = await workflow_service.resolve_ticket(
        session,
        ticket_id=ticket_id,
        actor=context.user,
        payload=payload,
        ip_address=_client_ip(request),
    )
    return _response(request, result)


@router.post(
    "/{ticket_id}/close",
    response_model=SuccessResponse[TicketDetailResponse],
    summary="WF-05 - Đóng ticket",
)
async def close_ticket(
    request: Request,
    ticket_id: int,
    payload: CloseRequest,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    result = await workflow_service.close_ticket(
        session,
        ticket_id=ticket_id,
        actor=context.user,
        payload=payload,
        ip_address=_client_ip(request),
    )
    return _response(request, result)


@router.post(
    "/{ticket_id}/reopen",
    response_model=SuccessResponse[TicketDetailResponse],
    summary="WF-06 - Mở lại ticket",
)
async def reopen_ticket(
    request: Request,
    ticket_id: int,
    payload: ReopenRequest,
    context: RequesterContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    result = await workflow_service.reopen_ticket(
        session,
        ticket_id=ticket_id,
        actor=context.user,
        payload=payload,
        ip_address=_client_ip(request),
    )
    return _response(request, result)


@router.post(
    "/{ticket_id}/resume",
    response_model=SuccessResponse[TicketDetailResponse],
    summary="WF-07 - Tiếp tục xử lý ticket mở lại",
)
async def resume_ticket(
    request: Request,
    ticket_id: int,
    payload: TransitionReasonRequest,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    result = await workflow_service.resume_reopened_ticket(
        session,
        ticket_id=ticket_id,
        actor=context.user,
        payload=payload,
        ip_address=_client_ip(request),
    )
    return _response(request, result)


@router.post(
    "/{ticket_id}/reject",
    response_model=SuccessResponse[TicketDetailResponse],
    summary="WF-08 - Từ chối ticket NEW",
)
async def reject_ticket(
    request: Request,
    ticket_id: int,
    payload: RejectRequest,
    context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    result = await workflow_service.reject_ticket(
        session,
        ticket_id=ticket_id,
        actor=context.user,
        payload=payload,
        ip_address=_client_ip(request),
    )
    return _response(request, result)
