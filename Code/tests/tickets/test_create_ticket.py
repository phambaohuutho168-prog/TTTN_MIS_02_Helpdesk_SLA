import re

from sqlalchemy import select

from app.models.ticket import Ticket
from app.models.ticket_status import TicketStatus
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _payload(seeded_users):
    return {
        "title": "  Không   truy cập được   hệ thống  ",
        "description": "  Người dùng không thể đăng nhập vào hệ thống nội bộ.  ",
        "category_id": seeded_users["active_category_id"],
        "priority_id": seeded_users["active_priority_id"],
    }


async def test_requester_creates_ticket_successfully(
    client,
    credentials,
    seeded_users,
):
    response = await client.post(
        "/api/v1/tickets",
        json=_payload(seeded_users),
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["code"] == "TICKET_CREATED"
    ticket = body["data"]
    assert re.fullmatch(r"TK-\d{8}-[A-F0-9]{12}", ticket["ticket_code"])
    assert ticket["requester_id"] == seeded_users["active_user_id"]
    assert ticket["title"] == "Không truy cập được hệ thống"
    assert ticket["current_status_code"] == "NEW"
    assert ticket["current_status"]["status_name"] == "Mới"
    assert ticket["category"]["category_name"] == "Phần mềm"
    assert ticket["priority"]["priority_code"] == "MEDIUM"
    assert ticket["created_at"]
    assert ticket["updated_at"]
    assert ticket["first_response_at"] is None


async def test_created_ticket_is_persisted(
    client,
    credentials,
    seeded_users,
    session_factory,
):
    response = await client.post(
        "/api/v1/tickets",
        json=_payload(seeded_users),
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 201
    created = response.json()["data"]

    async with session_factory() as session:
        ticket = await session.get(Ticket, created["ticket_id"])

    assert ticket is not None
    assert ticket.ticket_code == created["ticket_code"]
    assert ticket.requester_id == seeded_users["active_user_id"]
    assert ticket.current_status_code == "NEW"
    assert ticket.created_at is not None


async def test_system_generates_unique_ticket_codes(
    client,
    credentials,
    seeded_users,
):
    headers = await _headers(client, credentials)
    first = await client.post(
        "/api/v1/tickets",
        json=_payload(seeded_users),
        headers=headers,
    )
    second = await client.post(
        "/api/v1/tickets",
        json=_payload(seeded_users),
        headers=headers,
    )

    assert first.status_code == second.status_code == 201
    assert first.json()["data"]["ticket_code"] != second.json()["data"]["ticket_code"]


async def test_create_ticket_requires_authentication(client, seeded_users):
    response = await client.post("/api/v1/tickets", json=_payload(seeded_users))

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_MISSING"


async def test_processor_cannot_create_requester_ticket(
    client,
    processor_credentials,
    seeded_users,
):
    response = await client.post(
        "/api/v1/tickets",
        json=_payload(seeded_users),
        headers=await _headers(client, processor_credentials),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACTION"


async def test_unknown_category_is_rejected(client, credentials, seeded_users):
    payload = {**_payload(seeded_users), "category_id": 999999}
    response = await client.post(
        "/api/v1/tickets",
        json=payload,
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "CATEGORY_NOT_FOUND"


async def test_inactive_category_is_rejected(client, credentials, seeded_users):
    payload = {
        **_payload(seeded_users),
        "category_id": seeded_users["inactive_category_id"],
    }
    response = await client.post(
        "/api/v1/tickets",
        json=payload,
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "CATEGORY_INACTIVE"


async def test_unknown_priority_is_rejected(client, credentials, seeded_users):
    payload = {**_payload(seeded_users), "priority_id": 999999}
    response = await client.post(
        "/api/v1/tickets",
        json=payload,
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "PRIORITY_NOT_FOUND"


async def test_inactive_priority_is_rejected(client, credentials, seeded_users):
    payload = {
        **_payload(seeded_users),
        "priority_id": seeded_users["inactive_priority_id"],
    }
    response = await client.post(
        "/api/v1/tickets",
        json=payload,
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "PRIORITY_INACTIVE"


async def test_invalid_ticket_content_returns_validation_error(
    client,
    credentials,
    seeded_users,
):
    headers = await _headers(client, credentials)
    invalid_payloads = [
        {**_payload(seeded_users), "title": "   "},
        {**_payload(seeded_users), "description": "ngắn"},
        {**_payload(seeded_users), "category_id": 0},
    ]

    for payload in invalid_payloads:
        response = await client.post(
            "/api/v1/tickets",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"


async def test_requester_cannot_supply_server_managed_fields(
    client,
    credentials,
    seeded_users,
):
    payload = {
        **_payload(seeded_users),
        "requester_id": seeded_users["admin_user_id"],
        "ticket_code": "TK-FAKE",
        "current_status_code": "CLOSED",
    }
    response = await client.post(
        "/api/v1/tickets",
        json=payload,
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_missing_new_status_reports_configuration_error(
    client,
    credentials,
    seeded_users,
    session_factory,
):
    async with session_factory() as session:
        status = await session.get(TicketStatus, "NEW")
        await session.delete(status)
        await session.commit()

    response = await client.post(
        "/api/v1/tickets",
        json=_payload(seeded_users),
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 500
    assert response.json()["code"] == "TICKET_STATUS_CONFIGURATION_ERROR"
