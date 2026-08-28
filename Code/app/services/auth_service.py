from dataclasses import dataclass
from typing import Any

from anyio import to_thread
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import User
from app.repositories import audit_repository
from app.repositories.user_repository import get_user_by_email, get_user_by_id
from app.schemas.auth import AuthTokenData
from app.schemas.user import DepartmentBrief, RoleBrief, UserDetail
from app.services.auth_session_store import SessionStore


@dataclass
class AuthContext:
    user: User
    claims: dict[str, Any]
    token: str


def build_user_detail(user: User) -> UserDetail:
    department = None
    if user.department is not None:
        department = DepartmentBrief.model_validate(user.department)
    roles = [
        RoleBrief.model_validate(user_role.role)
        for user_role in user.user_roles
        if user_role.role is not None and user_role.role.is_active
    ]
    roles.sort(key=lambda item: item.role_code)
    return UserDetail(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        department=department,
        roles=roles,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def _issue_token_pair(
    user: User,
    store: SessionStore,
    *,
    family_id: str | None = None,
    old_refresh_claims: dict[str, Any] | None = None,
) -> AuthTokenData:
    roles = user.role_codes
    access_token, _access_claims = create_access_token(
        user_id=user.user_id,
        roles=roles,
    )
    refresh_token, refresh_claims = create_refresh_token(
        user_id=user.user_id,
        roles=roles,
        family_id=family_id,
    )
    if old_refresh_claims is None:
        await store.create_refresh_session(refresh_claims)
    else:
        rotated = await store.rotate_refresh_session(old_refresh_claims, refresh_claims)
        if not rotated:
            await store.revoke_family(str(old_refresh_claims["family_id"]))
            raise AppError(
                401,
                "AUTH_REFRESH_TOKEN_INVALID",
                "Refresh token không hợp lệ hoặc đã được sử dụng.",
            )

    return AuthTokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=build_user_detail(user),
    )


async def login(
    session: AsyncSession,
    store: SessionStore,
    *,
    email: str,
    password: str,
    ip_address: str,
) -> AuthTokenData:
    normalized_email = email.strip().lower()
    retry_after = await store.login_retry_after(email, ip_address)
    if retry_after:
        await audit_repository.append_audit(
            session,
            action_code="LOGIN_FAILED",
            entity_type="AUTH_SESSION",
            new_value={"email": normalized_email, "outcome": "RATE_LIMITED"},
            reason="RATE_LIMIT_EXCEEDED",
            ip_address=ip_address,
        )
        await session.commit()
        raise AppError(
            429,
            "RATE_LIMIT_EXCEEDED",
            "Đăng nhập bị tạm giới hạn. Vui lòng thử lại sau.",
            headers={"Retry-After": str(retry_after)},
        )

    user = await get_user_by_email(session, email)
    password_valid = False
    if user is not None:
        try:
            password_valid = await to_thread.run_sync(
                verify_password,
                password,
                user.password_hash,
            )
        except Exception:
            password_valid = False

    if user is None or not password_valid:
        await store.record_login_failure(email, ip_address)
        await audit_repository.append_audit(
            session,
            actor_user_id=user.user_id if user is not None else None,
            action_code="LOGIN_FAILED",
            entity_type="USER",
            entity_id=user.user_id if user is not None else None,
            new_value={"email": normalized_email, "outcome": "INVALID_CREDENTIALS"},
            reason="AUTH_INVALID_CREDENTIALS",
            ip_address=ip_address,
        )
        await session.commit()
        raise AppError(
            401,
            "AUTH_INVALID_CREDENTIALS",
            "Email hoặc mật khẩu không đúng.",
        )

    if not user.is_active:
        await audit_repository.append_audit(
            session,
            actor_user_id=user.user_id,
            action_code="LOGIN_FAILED",
            entity_type="USER",
            entity_id=user.user_id,
            new_value={"email": normalized_email, "outcome": "ACCOUNT_INACTIVE"},
            reason="AUTH_ACCOUNT_INACTIVE",
            ip_address=ip_address,
        )
        await session.commit()
        raise AppError(
            403,
            "AUTH_ACCOUNT_INACTIVE",
            "Tài khoản đã bị khóa hoặc vô hiệu hóa.",
        )

    await store.clear_login_failures(email, ip_address)
    token_data = await _issue_token_pair(user, store)
    await audit_repository.append_audit(
        session,
        actor_user_id=user.user_id,
        action_code="LOGIN_SUCCEEDED",
        entity_type="USER",
        entity_id=user.user_id,
        new_value={"email": normalized_email, "outcome": "SUCCEEDED"},
        ip_address=ip_address,
    )
    await session.commit()
    return token_data


async def refresh(
    session: AsyncSession,
    store: SessionStore,
    *,
    refresh_token: str,
) -> AuthTokenData:
    try:
        claims = decode_token(refresh_token, expected_type="refresh")
    except AppError as exc:
        if exc.code == "AUTH_TOKEN_EXPIRED":
            raise
        raise AppError(
            401,
            "AUTH_REFRESH_TOKEN_INVALID",
            "Refresh token không hợp lệ.",
        ) from exc

    family_id = str(claims.get("family_id", ""))
    if not family_id:
        raise AppError(401, "AUTH_REFRESH_TOKEN_INVALID", "Refresh token không hợp lệ.")

    status = await store.get_refresh_status(str(claims["jti"]))
    if status != "active":
        await store.revoke_family(family_id)
        raise AppError(
            401,
            "AUTH_REFRESH_TOKEN_INVALID",
            "Refresh token không hợp lệ, đã dùng lại hoặc đã thu hồi.",
        )

    user = await get_user_by_id(session, int(claims["sub"]))
    if user is None:
        await store.revoke_family(family_id)
        raise AppError(401, "AUTH_REFRESH_TOKEN_INVALID", "Refresh token không hợp lệ.")
    if not user.is_active:
        await store.revoke_family(family_id)
        raise AppError(
            403,
            "AUTH_ACCOUNT_INACTIVE",
            "Tài khoản đã bị khóa hoặc vô hiệu hóa.",
        )

    return await _issue_token_pair(
        user,
        store,
        family_id=family_id,
        old_refresh_claims=claims,
    )


async def authenticate_access_token(
    session: AsyncSession,
    store: SessionStore,
    token: str,
) -> AuthContext:
    claims = decode_token(token, expected_type="access")
    if await store.is_access_revoked(str(claims["jti"])):
        raise AppError(401, "AUTH_TOKEN_INVALID", "Token đã bị thu hồi.")

    user = await get_user_by_id(session, int(claims["sub"]))
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "Không tìm thấy người dùng.")
    if not user.is_active:
        raise AppError(
            403,
            "AUTH_ACCOUNT_INACTIVE",
            "Tài khoản đã bị khóa hoặc vô hiệu hóa.",
        )
    return AuthContext(user=user, claims=claims, token=token)


async def logout(
    session: AsyncSession,
    store: SessionStore,
    *,
    context: AuthContext,
    refresh_token: str,
    ip_address: str | None = None,
) -> None:
    try:
        refresh_claims = decode_token(refresh_token, expected_type="refresh")
    except AppError as exc:
        raise AppError(401, "AUTH_TOKEN_INVALID", "Token không hợp lệ.") from exc

    if str(refresh_claims["sub"]) != str(context.user.user_id):
        raise AppError(401, "AUTH_TOKEN_INVALID", "Token không thuộc phiên hiện tại.")

    family_id = str(refresh_claims.get("family_id", ""))
    if not family_id:
        raise AppError(401, "AUTH_TOKEN_INVALID", "Token không hợp lệ.")

    await store.revoke_family(family_id)
    await store.revoke_access(
        str(context.claims["jti"]),
        int(context.claims["exp"]),
    )
    await audit_repository.append_audit(
        session,
        actor_user_id=context.user.user_id,
        action_code="LOGOUT_SUCCEEDED",
        entity_type="USER",
        entity_id=context.user.user_id,
        new_value={"outcome": "SUCCEEDED"},
        ip_address=ip_address,
    )
    await session.commit()
