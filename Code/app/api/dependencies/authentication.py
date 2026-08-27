from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.database.session import get_db
from app.models.user import User
from app.services.auth_service import AuthContext, authenticate_access_token
from app.services.auth_session_store import SessionStore, get_session_store


bearer_scheme = HTTPBearer(auto_error=False)


async def get_auth_context(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(
            401,
            "AUTH_TOKEN_MISSING",
            "Thiếu Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await authenticate_access_token(session, store, credentials.credentials)


async def get_current_user(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> User:
    return context.user


CurrentAuthContext = Annotated[AuthContext, Depends(get_auth_context)]
CurrentUser = Annotated[User, Depends(get_current_user)]
