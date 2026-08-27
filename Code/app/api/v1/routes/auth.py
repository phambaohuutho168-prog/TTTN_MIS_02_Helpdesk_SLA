import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authentication import CurrentAuthContext, CurrentUser
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.auth import AuthTokenData, LoginRequest, LogoutRequest, RefreshTokenRequest
from app.schemas.common import SuccessResponse
from app.schemas.user import UserDetail
from app.services import auth_service
from app.services.auth_service import build_user_detail
from app.services.auth_session_store import SessionStore, get_session_store


router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


@router.post(
    "/login",
    response_model=SuccessResponse[AuthTokenData],
    summary="AUTH-01 - Đăng nhập",
)
async def login(
    request: Request,
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[SessionStore, Depends(get_session_store)],
):
    client_ip = request.client.host if request.client else "unknown"
    token_data = await auth_service.login(
        session,
        store,
        email=str(payload.email),
        password=payload.password,
        ip_address=client_ip,
    )
    logger.info(
        "authentication_event request_id=%s code=LOGIN_SUCCESS user_id=%s",
        request.state.request_id,
        token_data.user.user_id,
    )
    return success_response(
        request,
        data=token_data,
        message="Đăng nhập thành công.",
    )


@router.post(
    "/refresh",
    response_model=SuccessResponse[AuthTokenData],
    summary="AUTH-02 - Làm mới token",
)
async def refresh_token(
    request: Request,
    payload: RefreshTokenRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[SessionStore, Depends(get_session_store)],
):
    token_data = await auth_service.refresh(
        session,
        store,
        refresh_token=payload.refresh_token,
    )
    return success_response(
        request,
        data=token_data,
        message="Làm mới token thành công.",
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="AUTH-03 - Đăng xuất",
)
async def logout(
    request: Request,
    payload: LogoutRequest,
    context: CurrentAuthContext,
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> Response:
    await auth_service.logout(
        store,
        context=context,
        refresh_token=payload.refresh_token,
    )
    logger.info(
        "authentication_event request_id=%s code=LOGOUT_SUCCESS user_id=%s",
        request.state.request_id,
        context.user.user_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=SuccessResponse[UserDetail],
    summary="AUTH-04 - Hồ sơ hiện tại",
)
async def get_me(request: Request, user: CurrentUser):
    return success_response(
        request,
        data=build_user_detail(user),
        message="Lấy hồ sơ thành công.",
    )
