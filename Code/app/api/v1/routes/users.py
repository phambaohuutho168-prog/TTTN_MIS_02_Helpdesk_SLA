from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authentication import CurrentUser
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.common import SuccessResponse
from app.schemas.user import ProfileUpdateRequest, UserDetail
from app.services.user_service import update_own_profile


router = APIRouter(prefix="/users", tags=["Users"])


@router.patch(
    "/me",
    response_model=SuccessResponse[UserDetail],
    summary="AUTH-05 - Cập nhật hồ sơ cá nhân",
)
async def update_me(
    request: Request,
    payload: ProfileUpdateRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    user_detail = await update_own_profile(session, user, payload)
    return success_response(
        request,
        data=user_detail,
        message="Cập nhật hồ sơ thành công.",
    )
