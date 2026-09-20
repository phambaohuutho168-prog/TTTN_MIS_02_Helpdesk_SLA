"""CV051 - Negative tests cho validation và error contract.

Bao phủ invalid data, invalid state, duplicate, not found và system error.
"""

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

import pytest

from app.main import app
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.ticket import Ticket
from app.models.ticket_status_history import TicketStatusHistory
from app.services import ticket_service
from tests.conftest import login_client


async def _auth_headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _valid_ticket_payload(seeded_users):
    return {
        "title": "CV051 - Ticket kiểm thử lỗi nghiệp vụ",
        "description": "Ticket hợp lệ dùng làm dữ liệu nền cho negative test.",
        "category_id": seeded_users["active_category_id"],
        "priority_id": seeded_users["active_priority_id"],
    }


def _assert_error_contract(
    response,
    *,
    status_code,
    code,
    require_request_id_header=True,
):
    assert response.status_code == status_code
    body = response.json()
    assert body["success"] is False
    assert body["code"] == code
    assert "data" not in body
    assert body["message"]
    assert isinstance(body["errors"], list)
    assert body["meta"]["request_id"]
    assert body["meta"]["timestamp"]
    if require_request_id_header:
        assert response.headers["x-request-id"] == body["meta"]["request_id"]
    return body

@pytest.mark.business_rule
async def test_cv051_invalid_data_is_rejected_without_persistence(
    client,
    credentials,
    session_factory,
):
    # NEG-FT-01 - Nhiều field sai và field thừa phải được trả về cùng lúc.
    async with session_factory() as session:
        count_before = await session.scalar(select(func.count(Ticket.ticket_id)))

    response = await client.post(
        "/api/v1/tickets",
        headers=await _auth_headers(client, credentials),
        json={
            "title": "x",
            "description": "ngắn",
            "category_id": 0,
            "priority_id": 0,
            "unexpected": "field không được hỗ trợ",
        },
    )
    body = _assert_error_contract(
        response,
        status_code=422,
        code="VALIDATION_ERROR",
    )
    assert {error["field"] for error in body["errors"]} == {
        "title",
        "description",
        "category_id",
        "priority_id",
        "unexpected",
    }

    async with session_factory() as session:
        count_after = await session.scalar(select(func.count(Ticket.ticket_id)))
    assert count_after == count_before == 0

@pytest.mark.business_rule
async def test_cv051_invalid_state_is_rejected_atomically(
    client,
    credentials,
    admin_credentials,
    seeded_users,
    session_factory,
):
    # NEG-FT-02 - Không được đóng trực tiếp ticket NEW.
    created = await client.post(
        "/api/v1/tickets",
        headers=await _auth_headers(client, credentials),
        json=_valid_ticket_payload(seeded_users),
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["data"]["ticket_id"]

    async with session_factory() as session:
        history_before = await session.scalar(
            select(func.count(TicketStatusHistory.history_id)).where(
                TicketStatusHistory.ticket_id == ticket_id
            )
        )
        audit_before = await session.scalar(
            select(func.count(AuditLog.audit_id)).where(
                AuditLog.ticket_id == ticket_id
            )
        )

    response = await client.post(
        f"/api/v1/tickets/{ticket_id}/close",
        headers=await _auth_headers(client, admin_credentials),
        json={"reason": "Không được đóng ticket khi còn ở trạng thái NEW"},
    )
    _assert_error_contract(
        response,
        status_code=409,
        code="INVALID_STATE_TRANSITION",
    )

    async with session_factory() as session:
        ticket = await session.get(Ticket, ticket_id)
        history_after = await session.scalar(
            select(func.count(TicketStatusHistory.history_id)).where(
                TicketStatusHistory.ticket_id == ticket_id
            )
        )
        audit_after = await session.scalar(
            select(func.count(AuditLog.audit_id)).where(
                AuditLog.ticket_id == ticket_id
            )
        )
    assert ticket.current_status_code == "NEW"
    assert ticket.closed_at is None
    assert ticket.closed_by is None
    assert history_after == history_before
    assert audit_after == audit_before

@pytest.mark.business_rule
async def test_cv051_duplicate_data_is_rejected_without_new_record(
    client,
    admin_credentials,
    session_factory,
):
    # NEG-FT-03 - Tên category trùng không phân biệt hoa thường/khoảng trắng.
    async with session_factory() as session:
        count_before = await session.scalar(select(func.count(Category.category_id)))

    response = await client.post(
        "/api/v1/admin/categories",
        headers=await _auth_headers(client, admin_credentials),
        json={
            "category_name": "  PHẦN   MỀM  ",
            "description": "Bản ghi trùng không được tạo.",
        },
    )
    _assert_error_contract(
        response,
        status_code=409,
        code="CATEGORY_NAME_CONFLICT",
    )

    async with session_factory() as session:
        count_after = await session.scalar(select(func.count(Category.category_id)))
    assert count_after == count_before == 2

@pytest.mark.business_rule
async def test_cv051_missing_resource_returns_standard_not_found(
    client,
    credentials,
):
    # NEG-FT-04 - ID hợp lệ về định dạng nhưng không tồn tại trong database.
    response = await client.get(
        "/api/v1/tickets/999999",
        headers=await _auth_headers(client, credentials),
    )
    body = _assert_error_contract(
        response,
        status_code=404,
        code="TICKET_NOT_FOUND",
    )
    assert body["errors"] == []

@pytest.mark.business_rule
async def test_cv051_system_error_is_logged_but_response_is_sanitized(
    client,
    credentials,
    monkeypatch,
):
    # NEG-FT-05 - Mô phỏng lỗi tầng service/database không được xử lý trước đó.
    internal_detail = "DATABASE_URL=postgresql://secret-user:secret-pass@db/cv051"

    async def raise_unexpected_error(*args, **kwargs):
        raise RuntimeError(internal_detail)

    monkeypatch.setattr(ticket_service, "list_tickets", raise_unexpected_error)
    headers = await _auth_headers(client, credentials)

    # Client riêng tắt raise_app_exceptions để quan sát response 500 như production.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as fault_client:
        response = await fault_client.get("/api/v1/tickets", headers=headers)

    body = _assert_error_contract(
        response,
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        require_request_id_header=False,
    )
    assert body["message"] == "Hệ thống gặp lỗi không mong đợi."
    assert body["errors"] == []
    assert internal_detail not in response.text
    assert "secret-user" not in response.text
    assert "secret-pass" not in response.text
