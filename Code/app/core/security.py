from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.errors import AppError


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, password_digest: str) -> bool:
    return password_hash.verify(password, password_digest)


def _base_claims(
    *,
    user_id: int,
    token_type: str,
    expires_delta: timedelta,
    roles: list[str],
    jti: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "sub": str(user_id),
        "type": token_type,
        "roles": roles,
        "jti": jti or uuid4().hex,
        "iat": now,
        "exp": now + expires_delta,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }


def create_access_token(*, user_id: int, roles: list[str]) -> tuple[str, dict[str, Any]]:
    claims = _base_claims(
        user_id=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        roles=roles,
    )
    token = jwt.encode(
        claims,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, claims


def create_refresh_token(
    *,
    user_id: int,
    roles: list[str],
    family_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    claims = _base_claims(
        user_id=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        roles=roles,
    )
    claims["family_id"] = family_id or uuid4().hex
    token = jwt.encode(
        claims,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, claims


def decode_token(token: str, *, expected_type: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["sub", "type", "jti", "iat", "exp", "iss", "aud"]},
        )
    except ExpiredSignatureError as exc:
        raise AppError(401, "AUTH_TOKEN_EXPIRED", "Token đã hết hạn.") from exc
    except InvalidTokenError as exc:
        raise AppError(401, "AUTH_TOKEN_INVALID", "Token không hợp lệ.") from exc

    if claims.get("type") != expected_type:
        raise AppError(401, "AUTH_TOKEN_INVALID", "Sai loại token.")
    return claims
