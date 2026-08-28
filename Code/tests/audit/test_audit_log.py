from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.request_context import reset_request_context, set_request_context
from app.models.audit_log import AuditLog
from app.repositories.audit_repository import append_audit, sanitize_audit_value


async def _headers(client, credentials, *, request_id: str | None = None):
    headers = {"X-Request-ID": request_id} if request_id else {}
    response = await client.post(
        "/api/v1/auth/login",
        json=credentials,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def test_admin_lists_and_filters_audit_logs(
    client,
    admin_credentials,
    seeded_users,
):
    request_id = "tc-aud-01-login"
    headers = await _headers(client, admin_credentials, request_id=request_id)
    response = await client.get(
        "/api/v1/admin/audit-logs",
        params={
            "actor_user_id": seeded_users["admin_user_id"],
            "action_code": "login_succeeded",
            "entity_type": "user",
            "page": 1,
            "page_size": 10,
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == "AUDIT_LOG_LISTED"
    assert body["data"]["total"] >= 1
    record = next(
        item
        for item in body["data"]["items"]
        if item["request_id"] == request_id
    )
    assert record["actor_user_id"] == seeded_users["admin_user_id"]
    assert record["action_code"] == "LOGIN_SUCCEEDED"
    assert record["entity_type"] == "USER"


async def test_audit_log_requires_admin(
    client,
    credentials,
):
    response = await client.get(
        "/api/v1/admin/audit-logs",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACTION"


async def test_audit_log_requires_authentication(client):
    response = await client.get("/api/v1/admin/audit-logs")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_MISSING"


async def test_failed_login_is_audited_without_credentials(
    client,
    admin_credentials,
):
    failed = await client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "WrongPassword123!"},
        headers={"X-Request-ID": "tc-aud-login-failed"},
    )
    assert failed.status_code == 401

    response = await client.get(
        "/api/v1/admin/audit-logs",
        params={"action_code": "LOGIN_FAILED"},
        headers=await _headers(client, admin_credentials),
    )
    assert response.status_code == 200
    record = next(
        item
        for item in response.json()["data"]["items"]
        if item["request_id"] == "tc-aud-login-failed"
    )
    serialized = str(record).lower()
    assert "wrongpassword" not in serialized
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert record["new_value_json"]["outcome"] == "INVALID_CREDENTIALS"


async def test_role_assignment_creates_permission_audit(
    client,
    admin_credentials,
    seeded_users,
):
    headers = await _headers(client, admin_credentials)
    assigned = await client.put(
        (
            f"/api/v1/admin/users/{seeded_users['active_user_id']}"
            f"/roles/{seeded_users['processor_role_id']}"
        ),
        headers=headers,
    )
    assert assigned.status_code == 200, assigned.text

    audit = await client.get(
        "/api/v1/admin/audit-logs",
        params={
            "action_code": "ROLE_ASSIGNED",
            "entity_type": "USER_ROLE",
            "entity_id": seeded_users["active_user_id"],
        },
        headers=headers,
    )
    assert audit.status_code == 200
    record = audit.json()["data"]["items"][0]
    assert record["actor_user_id"] == seeded_users["admin_user_id"]
    assert record["new_value_json"]["role_code"] == "PROCESSOR"


async def test_ticket_creation_and_sla_initialization_are_audited(
    client,
    credentials,
    admin_credentials,
    seeded_users,
    session_factory,
):
    from app.models.sla_policy import SLAPolicy

    async with session_factory() as session:
        session.add(
            SLAPolicy(
                priority_id=seeded_users["active_priority_id"],
                version_no=1,
                response_target_minutes=30,
                resolution_target_minutes=240,
                warning_percent=80,
                escalation_percent=100,
                effective_from=datetime.now(timezone.utc) - timedelta(days=1),
                is_active=True,
            )
        )
        await session.commit()

    created = await client.post(
        "/api/v1/tickets",
        headers=await _headers(client, credentials),
        json={
            "title": "Kiểm tra audit ticket",
            "description": "Tạo ticket để kiểm tra audit và SLA runtime.",
            "category_id": seeded_users["active_category_id"],
            "priority_id": seeded_users["active_priority_id"],
        },
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["data"]["ticket_id"]
    audits = await client.get(
        "/api/v1/admin/audit-logs",
        params={"ticket_id": ticket_id, "page_size": 20},
        headers=await _headers(client, admin_credentials),
    )
    assert audits.status_code == 200
    action_codes = {item["action_code"] for item in audits.json()["data"]["items"]}
    assert "TICKET_CREATED" in action_codes
    assert "SLA_RUNTIME_CREATED" in action_codes


async def test_audit_filters_validate_timezone_and_range(
    client,
    admin_credentials,
):
    headers = await _headers(client, admin_credentials)
    naive = await client.get(
        "/api/v1/admin/audit-logs",
        params={"created_from": "2026-08-28T00:00:00"},
        headers=headers,
    )
    reversed_range = await client.get(
        "/api/v1/admin/audit-logs",
        params={
            "created_from": "2026-08-29T00:00:00Z",
            "created_to": "2026-08-28T00:00:00Z",
        },
        headers=headers,
    )
    assert naive.status_code == 422
    assert reversed_range.status_code == 422


async def test_audit_api_exposes_no_update_or_delete(
    client,
    admin_credentials,
):
    headers = await _headers(client, admin_credentials)
    assert (
        await client.put("/api/v1/admin/audit-logs", headers=headers, json={})
    ).status_code == 405
    assert (
        await client.delete("/api/v1/admin/audit-logs", headers=headers)
    ).status_code == 405


async def test_audit_model_rejects_update_and_delete(session_factory):
    async with session_factory() as session:
        audit = await append_audit(
            session,
            action_code="TEST_APPEND_ONLY",
            entity_type="TEST",
            entity_id=1,
            new_value={"ok": True},
        )
        await session.commit()
        audit_id = audit.audit_id
        audit.reason = "tamper"
        with pytest.raises(ValueError, match="AUDIT_LOG_APPEND_ONLY"):
            await session.commit()
        await session.rollback()

        saved = await session.scalar(
            select(AuditLog).where(AuditLog.audit_id == audit_id)
        )
        assert saved is not None
        await session.delete(saved)
        with pytest.raises(ValueError, match="AUDIT_LOG_APPEND_ONLY"):
            await session.commit()
        await session.rollback()


def test_sensitive_values_are_redacted_recursively():
    value = sanitize_audit_value(
        {
            "email": "user@example.com",
            "password_hash": "hash",
            "nested": {
                "access_token": "jwt",
                "storage_path": "/private/object",
                "safe": [1, {"secret_key": "secret"}],
            },
        }
    )
    assert value["email"] == "user@example.com"
    assert value["password_hash"] == "[REDACTED]"
    assert value["nested"]["access_token"] == "[REDACTED]"
    assert value["nested"]["storage_path"] == "[REDACTED]"
    assert value["nested"]["safe"][1]["secret_key"] == "[REDACTED]"


async def test_model_enforces_tracing_and_redaction_for_direct_writers(
    session_factory,
):
    tokens = set_request_context(
        request_id="tc-aud-direct-writer",
        client_ip="127.0.0.1",
    )
    try:
        async with session_factory() as session:
            audit = AuditLog(
                action_code="  ticket_assigned  ",
                entity_type="  ticket_assignment  ",
                entity_id=1,
                new_value_json={"assignee_id": 2, "access_token": "secret"},
            )
            session.add(audit)
            await session.commit()
            await session.refresh(audit)

            assert audit.action_code == "TICKET_ASSIGNED"
            assert audit.entity_type == "TICKET_ASSIGNMENT"
            assert audit.request_id == "tc-aud-direct-writer"
            assert audit.ip_address == "127.0.0.1"
            assert audit.new_value_json["access_token"] == "[REDACTED]"
    finally:
        reset_request_context(tokens)
