from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.models.category import Category
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_status import TicketStatus
from app.models.user import User
from app.models.user_role import UserRole
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def ticket_list_data(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        other_requester = User(
            email="other.requester@example.com",
            full_name="Other Requester",
            password_hash=hash_password("CorrectPassword123!"),
            is_active=True,
        )
        other_category = Category(
            category_name="Mạng và kết nối",
            description="Sự cố mạng",
            is_active=True,
        )
        urgent_priority = Priority(
            priority_code="P1",
            priority_level=1,
            priority_name="Khẩn cấp",
            description="Gián đoạn nghiêm trọng",
            is_active=True,
        )
        closed_status = TicketStatus(
            status_code="CLOSED",
            status_name="Đã đóng",
            is_terminal=True,
            description="Ticket đã kết thúc",
        )
        session.add_all(
            [other_requester, other_category, urgent_priority, closed_status]
        )
        await session.flush()
        session.add(
            UserRole(
                user_id=other_requester.user_id,
                role_id=seeded_users["requester_role_id"],
            )
        )

        tickets = [
            Ticket(
                ticket_code="TK-20260828-AAA000000001",
                requester_id=seeded_users["active_user_id"],
                category_id=seeded_users["active_category_id"],
                priority_id=seeded_users["active_priority_id"],
                current_status_code="NEW",
                title="VPN không kết nối được",
                description="Không thể kết nối VPN từ mạng bên ngoài.",
                created_at=now - timedelta(days=4),
                updated_at=now - timedelta(days=4),
            ),
            Ticket(
                ticket_code="TK-20260828-AAA000000002",
                requester_id=seeded_users["active_user_id"],
                category_id=other_category.category_id,
                priority_id=urgent_priority.priority_id,
                current_status_code="CLOSED",
                title="Máy trạm mất mạng",
                description="Máy trạm đã được khôi phục kết nối.",
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(days=2),
                closed_at=now - timedelta(days=2),
            ),
            Ticket(
                ticket_code="TK-20260828-AAA000000003",
                requester_id=other_requester.user_id,
                category_id=seeded_users["active_category_id"],
                priority_id=urgent_priority.priority_id,
                current_status_code="NEW",
                title="ERP báo lỗi đăng nhập",
                description="Người dùng khác không đăng nhập được ERP.",
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=1),
            ),
            Ticket(
                ticket_code="TK-20260828-AAA000000004",
                requester_id=other_requester.user_id,
                category_id=other_category.category_id,
                priority_id=seeded_users["active_priority_id"],
                current_status_code="NEW",
                title="Wifi chập chờn",
                description="Kết nối wifi không ổn định tại tầng ba.",
                created_at=now - timedelta(days=1),
                updated_at=now,
            ),
        ]
        session.add_all(tickets)
        await session.flush()
        session.add_all(
            [
                TicketAssignment(
                    ticket_id=tickets[0].ticket_id,
                    assignee_id=seeded_users["processor_user_id"],
                    assigned_by=seeded_users["admin_user_id"],
                    assigned_at=now - timedelta(days=3, hours=12),
                    is_current=True,
                    reason="Phân công xử lý VPN",
                ),
                TicketAssignment(
                    ticket_id=tickets[2].ticket_id,
                    assignee_id=seeded_users["processor_user_id"],
                    assigned_by=seeded_users["admin_user_id"],
                    assigned_at=now - timedelta(days=1, hours=12),
                    is_current=True,
                    reason="Phân công xử lý ERP",
                ),
                TicketAssignment(
                    ticket_id=tickets[3].ticket_id,
                    assignee_id=seeded_users["processor_user_id"],
                    assigned_by=seeded_users["admin_user_id"],
                    assigned_at=now - timedelta(hours=20),
                    ended_at=now - timedelta(hours=10),
                    is_current=False,
                    reason="Đã điều chuyển",
                ),
            ]
        )
        await session.commit()

    return {
        "now": now,
        "other_requester_id": other_requester.user_id,
        "other_category_id": other_category.category_id,
        "urgent_priority_id": urgent_priority.priority_id,
        "ticket_ids": [ticket.ticket_id for ticket in tickets],
        "ticket_codes": [ticket.ticket_code for ticket in tickets],
    }


async def test_ticket_list_requires_authentication(client, ticket_list_data):
    response = await client.get("/api/v1/tickets")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_MISSING"


async def test_requester_sees_only_own_tickets_and_cannot_use_privileged_filters(
    client,
    credentials,
    seeded_users,
    ticket_list_data,
):
    headers = await _headers(client, credentials)
    response = await client.get("/api/v1/tickets", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "TICKET_LISTED"
    assert body["data"]["total"] == 2
    assert {
        item["requester"]["user_id"] for item in body["data"]["items"]
    } == {seeded_users["active_user_id"]}

    for params in (
        {"requester_id": ticket_list_data["other_requester_id"]},
        {"assignee_id": seeded_users["processor_user_id"]},
    ):
        forbidden = await client.get(
            "/api/v1/tickets",
            params=params,
            headers=headers,
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["code"] == "FORBIDDEN_ACTION"


async def test_processor_sees_only_current_assignments(
    client,
    processor_credentials,
    seeded_users,
    ticket_list_data,
):
    headers = await _headers(client, processor_credentials)
    response = await client.get("/api/v1/tickets", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 2
    assert {item["ticket_id"] for item in data["items"]} == {
        ticket_list_data["ticket_ids"][0],
        ticket_list_data["ticket_ids"][2],
    }
    assert all(
        item["current_assignee"]["user_id"]
        == seeded_users["processor_user_id"]
        for item in data["items"]
    )

    intersection = await client.get(
        "/api/v1/tickets",
        params={"assignee_id": seeded_users["admin_user_id"]},
        headers=headers,
    )
    assert intersection.status_code == 200
    assert intersection.json()["data"]["total"] == 0


async def test_admin_sees_all_tickets_and_summary_fields(
    client,
    admin_credentials,
    ticket_list_data,
):
    response = await client.get(
        "/api/v1/tickets",
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 4
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_pages"] == 1
    assigned = next(
        item
        for item in data["items"]
        if item["ticket_id"] == ticket_list_data["ticket_ids"][0]
    )
    assert set(assigned) == {
        "ticket_id",
        "ticket_code",
        "title",
        "category",
        "priority",
        "status",
        "requester",
        "current_assignee",
        "created_at",
        "updated_at",
    }


async def test_admin_searches_and_combines_ticket_filters(
    client,
    admin_credentials,
    seeded_users,
    ticket_list_data,
):
    headers = await _headers(client, admin_credentials)
    cases = [
        ({"q": "  vpn  "}, {ticket_list_data["ticket_ids"][0]}),
        ({"q": "AAA000000003"}, {ticket_list_data["ticket_ids"][2]}),
        (
            {"status": "closed"},
            {ticket_list_data["ticket_ids"][1]},
        ),
        (
            {"category_id": ticket_list_data["other_category_id"]},
            {
                ticket_list_data["ticket_ids"][1],
                ticket_list_data["ticket_ids"][3],
            },
        ),
        (
            {"priority_id": ticket_list_data["urgent_priority_id"]},
            {
                ticket_list_data["ticket_ids"][1],
                ticket_list_data["ticket_ids"][2],
            },
        ),
        (
            {"requester_id": ticket_list_data["other_requester_id"]},
            {
                ticket_list_data["ticket_ids"][2],
                ticket_list_data["ticket_ids"][3],
            },
        ),
        (
            {"assignee_id": seeded_users["processor_user_id"]},
            {
                ticket_list_data["ticket_ids"][0],
                ticket_list_data["ticket_ids"][2],
            },
        ),
    ]

    for params, expected_ids in cases:
        response = await client.get(
            "/api/v1/tickets",
            params=params,
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert {
            item["ticket_id"] for item in response.json()["data"]["items"]
        } == expected_ids


async def test_status_accepts_repeated_and_comma_separated_values(
    client,
    admin_credentials,
    ticket_list_data,
):
    response = await client.get(
        "/api/v1/tickets",
        params=[("status", "new,CLOSED"), ("status", "new")],
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 4


async def test_created_time_range_is_inclusive_and_invalid_range_is_rejected(
    client,
    admin_credentials,
    ticket_list_data,
):
    headers = await _headers(client, admin_credentials)
    now = ticket_list_data["now"]
    response = await client.get(
        "/api/v1/tickets",
        params={
            "created_from": (now - timedelta(days=3)).isoformat(),
            "created_to": (now - timedelta(days=1)).isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert {item["ticket_id"] for item in response.json()["data"]["items"]} == {
        ticket_list_data["ticket_ids"][1],
        ticket_list_data["ticket_ids"][2],
        ticket_list_data["ticket_ids"][3],
    }

    invalid = await client.get(
        "/api/v1/tickets",
        params={
            "created_from": now.isoformat(),
            "created_to": (now - timedelta(days=1)).isoformat(),
        },
        headers=headers,
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "VALIDATION_ERROR"


async def test_pagination_and_sorting_are_deterministic(
    client,
    admin_credentials,
    ticket_list_data,
):
    headers = await _headers(client, admin_credentials)
    first_page = await client.get(
        "/api/v1/tickets",
        params={"page": 1, "page_size": 2, "sort": "created_at"},
        headers=headers,
    )
    second_page = await client.get(
        "/api/v1/tickets",
        params={"page": 2, "page_size": 2, "sort": "created_at"},
        headers=headers,
    )

    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["data"]["total"] == 4
    assert first_page.json()["data"]["total_pages"] == 2
    assert [item["ticket_id"] for item in first_page.json()["data"]["items"]] == (
        ticket_list_data["ticket_ids"][:2]
    )
    assert [item["ticket_id"] for item in second_page.json()["data"]["items"]] == (
        ticket_list_data["ticket_ids"][2:]
    )

    priority_order = await client.get(
        "/api/v1/tickets",
        params={"sort": "priority_level"},
        headers=headers,
    )
    levels = [
        item["priority"]["priority_level"]
        for item in priority_order.json()["data"]["items"]
    ]
    assert levels == sorted(levels)


async def test_invalid_status_and_query_constraints_return_validation_error(
    client,
    admin_credentials,
):
    headers = await _headers(client, admin_credentials)
    cases = [
        ({"status": "NOT_A_STATUS"}, 422),
        ({"page": 0}, 422),
        ({"page_size": 101}, 422),
        ({"sort": "title"}, 422),
        ({"created_from": "2026-08-28T00:00:00"}, 422),
        ({"q": "x" * 101}, 422),
    ]

    for params, expected_status in cases:
        response = await client.get(
            "/api/v1/tickets",
            params=params,
            headers=headers,
        )
        assert response.status_code == expected_status
        assert response.json()["code"] == "VALIDATION_ERROR"
