from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies.authentication import get_auth_context
from app.api.dependencies.authorization import AdminContext, require_roles
from app.core.errors import register_exception_handlers
from app.core.rbac import RoleCode
from app.middleware.request_id import RequestIDMiddleware
from app.services.auth_service import AuthContext


def _context(
    database_roles: list[str],
    *,
    token_roles: list[str] | None = None,
) -> AuthContext:
    user = SimpleNamespace(user_id=101, role_codes=database_roles)
    return AuthContext(
        user=user,
        claims={"roles": token_roles or []},
        token="test-access-token",
    )


async def _request_admin_endpoint(
    context: AuthContext,
    *,
    headers: dict[str, str] | None = None,
):
    test_app = FastAPI()
    test_app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(test_app)

    @test_app.get("/admin-only")
    async def admin_only(auth_context: AdminContext):
        return {"user_id": auth_context.user.user_id}

    async def override_auth_context() -> AuthContext:
        return context

    test_app.dependency_overrides[get_auth_context] = override_auth_context
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/admin-only", headers=headers)


def test_require_roles_rejects_empty_policy():
    with pytest.raises(ValueError, match="ít nhất một vai trò"):
        require_roles()


async def test_admin_role_is_allowed():
    response = await _request_admin_endpoint(_context([RoleCode.ADMIN.value]))

    assert response.status_code == 200
    assert response.json() == {"user_id": 101}


async def test_requester_is_denied_with_standard_403_envelope():
    response = await _request_admin_endpoint(_context([RoleCode.REQUESTER.value]))

    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert body["code"] == "FORBIDDEN_ACTION"
    assert body["message"] == "Bạn không có quyền thực hiện thao tác này."
    assert body["errors"] == []
    assert body["meta"]["request_id"]
    assert body["meta"]["timestamp"]


async def test_client_header_and_stale_admin_claim_cannot_escalate_requester():
    context = _context(
        [RoleCode.REQUESTER.value],
        token_roles=[RoleCode.ADMIN.value],
    )
    response = await _request_admin_endpoint(
        context,
        headers={"X-User-Role": RoleCode.ADMIN.value},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACTION"


async def test_current_database_admin_role_wins_over_stale_requester_claim():
    context = _context(
        [RoleCode.ADMIN.value],
        token_roles=[RoleCode.REQUESTER.value],
    )
    response = await _request_admin_endpoint(context)

    assert response.status_code == 200


async def test_multi_role_user_is_allowed_when_one_role_matches():
    response = await _request_admin_endpoint(
        _context([RoleCode.REQUESTER.value, RoleCode.ADMIN.value])
    )

    assert response.status_code == 200


async def test_authenticated_user_without_active_role_is_denied():
    response = await _request_admin_endpoint(_context([]))

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACTION"
