from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import AnyBusinessRoleContext
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.common import SuccessResponse
from app.schemas.rating import RatingCreateRequest, RatingResponse
from app.services import rating_service


router = APIRouter(prefix="/tickets", tags=["Satisfaction Rating"])


@router.post(
    "/{ticket_id}/rating",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[RatingResponse],
    summary="RAT-01 - Gửi đánh giá mức hài lòng",
)
async def create_rating(
    request: Request,
    ticket_id: int,
    payload: RatingCreateRequest,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await rating_service.create_rating(
        session,
        ticket_id=ticket_id,
        actor=context.user,
        payload=payload,
        ip_address=request.client.host if request.client is not None else None,
    )
    return success_response(
        request,
        data=data,
        code="RATING_CREATED",
        message="Gửi đánh giá mức hài lòng thành công.",
    )


@router.get(
    "/{ticket_id}/rating",
    response_model=SuccessResponse[RatingResponse],
    summary="RAT-02 - Xem đánh giá mức hài lòng",
)
async def get_rating(
    request: Request,
    ticket_id: int,
    context: AnyBusinessRoleContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await rating_service.get_rating(
        session,
        ticket_id=ticket_id,
        current_user=context.user,
    )
    return success_response(
        request,
        data=data,
        code="RATING_RETRIEVED",
        message="Lấy đánh giá mức hài lòng thành công.",
    )
