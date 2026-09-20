"""CV053 - User Acceptance Test cho ba vai trò của Helpdesk SLA.

Ba kịch bản mô phỏng thao tác chấp nhận của REQUESTER, PROCESSOR và ADMIN
trên API thật của ứng dụng. Mỗi test chỉ xác nhận các chức năng mà người dùng
thuộc vai trò đó cần để hoàn thành công việc hằng ngày.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.sla_policy import SLAPolicy
from app.models.ticket_status import TicketStatus
from tests.conftest import login_client


pytestmark = pytest.mark.uat


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _ticket_payload(seeded_users, title):
    return {
        "title": title,
        "description": "Kịch bản nghiệm thu người dùng CV053 cho hệ thống Helpdesk SLA.",
        "category_id": seeded_users["active_category_id"],
        "priority_id": seeded_users["active_priority_id"],
    }


@pytest.fixture
async def cv053_uat_configuration(session_factory, seeded_users):
    """Chuẩn bị state machine và SLA dùng chung cho ba kịch bản UAT."""
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        session.add_all(
            [
                TicketStatus(status_code="ASSIGNED", status_name="Đã phân công"),
                TicketStatus(status_code="IN_PROGRESS", status_name="Đang xử lý"),
                TicketStatus(status_code="RESOLVED", status_name="Đã xử lý"),
                TicketStatus(
                    status_code="CLOSED",
                    status_name="Đã đóng",
                    is_terminal=True,
                ),
                SLAPolicy(
                    priority_id=seeded_users["active_priority_id"],
                    version_no=1,
                    response_target_minutes=30,
                    resolution_target_minutes=240,
                    effective_from=now - timedelta(days=1),
                    is_active=True,
                ),
            ]
        )
        await session.commit()


async def _create_ticket(client, credentials, seeded_users, title):
    response = await client.post(
        "/api/v1/tickets",
        headers=await _headers(client, credentials),
        json=_ticket_payload(seeded_users, title),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _assign_ticket(
    client,
    admin_credentials,
    seeded_users,
    ticket_id,
):
    response = await client.put(
        f"/api/v1/tickets/{ticket_id}/assignment",
        headers=await _headers(client, admin_credentials),
        json={
            "assignee_id": seeded_users["processor_user_id"],
            "reason": "Phân công theo kịch bản UAT CV053",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_uat_01_requester_creates_and_tracks_own_ticket(
    client,
    credentials,
    seeded_users,
    cv053_uat_configuration,
):
    """UAT-REQ-01: Requester tạo yêu cầu và theo dõi ticket của chính mình."""
    requester_headers = await _headers(client, credentials)

    categories = await client.get("/api/v1/categories", headers=requester_headers)
    priorities = await client.get("/api/v1/priorities", headers=requester_headers)
    assert categories.status_code == 200, categories.text
    assert priorities.status_code == 200, priorities.text
    assert categories.json()["data"]
    assert priorities.json()["data"]

    ticket = await _create_ticket(
        client,
        credentials,
        seeded_users,
        "CV053 UAT - Requester không truy cập được ứng dụng",
    )
    assert ticket["current_status_code"] == "NEW"
    assert ticket["requester_id"] == seeded_users["active_user_id"]

    ticket_list = await client.get("/api/v1/tickets", headers=requester_headers)
    assert ticket_list.status_code == 200, ticket_list.text
    own_ids = {item["ticket_id"] for item in ticket_list.json()["data"]["items"]}
    assert ticket["ticket_id"] in own_ids

    detail = await client.get(
        f"/api/v1/tickets/{ticket['ticket_id']}",
        headers=requester_headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["ticket_id"] == ticket["ticket_id"]


async def test_uat_02_processor_handles_assigned_ticket(
    client,
    credentials,
    admin_credentials,
    processor_credentials,
    seeded_users,
    cv053_uat_configuration,
):
    """UAT-PRO-01: Processor tiếp nhận, phản hồi và xử lý ticket được giao."""
    ticket = await _create_ticket(
        client,
        credentials,
        seeded_users,
        "CV053 UAT - Processor xử lý yêu cầu được phân công",
    )
    ticket_id = ticket["ticket_id"]
    await _assign_ticket(client, admin_credentials, seeded_users, ticket_id)
    processor_headers = await _headers(client, processor_credentials)

    queue = await client.get("/api/v1/tickets", headers=processor_headers)
    assert queue.status_code == 200, queue.text
    assert ticket_id in {
        item["ticket_id"] for item in queue.json()["data"]["items"]
    }

    reply = await client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers=processor_headers,
        json={
            "content": "Đã tiếp nhận yêu cầu và bắt đầu kiểm tra.",
            "visibility": "PUBLIC",
            "comment_type": "REPLY",
        },
    )
    assert reply.status_code == 201, reply.text

    started = await client.post(
        f"/api/v1/tickets/{ticket_id}/start",
        headers=processor_headers,
        json={"reason": "Bắt đầu xử lý theo UAT"},
    )
    assert started.status_code == 200, started.text
    assert started.json()["data"]["status"]["status_code"] == "IN_PROGRESS"

    resolved = await client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        headers=processor_headers,
        json={"resolution_note": "Đã khắc phục và xác nhận dịch vụ hoạt động."},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["data"]["status"]["status_code"] == "RESOLVED"


async def test_uat_03_admin_monitors_and_assigns_ticket(
    client,
    credentials,
    admin_credentials,
    seeded_users,
    cv053_uat_configuration,
):
    """UAT-ADM-01: Admin giám sát hàng đợi, phân công và kiểm tra audit."""
    ticket = await _create_ticket(
        client,
        credentials,
        seeded_users,
        "CV053 UAT - Admin phân công và giám sát",
    )
    ticket_id = ticket["ticket_id"]
    admin_headers = await _headers(client, admin_credentials)

    users = await client.get(
        "/api/v1/admin/users",
        params={"role_code": "PROCESSOR", "is_active": True},
        headers=admin_headers,
    )
    assert users.status_code == 200, users.text
    assert seeded_users["processor_user_id"] in {
        item["user_id"] for item in users.json()["data"]["items"]
    }

    tickets = await client.get("/api/v1/tickets", headers=admin_headers)
    assert tickets.status_code == 200, tickets.text
    assert ticket_id in {
        item["ticket_id"] for item in tickets.json()["data"]["items"]
    }

    assignment = await _assign_ticket(
        client,
        admin_credentials,
        seeded_users,
        ticket_id,
    )
    assert assignment["assignee"]["user_id"] == seeded_users["processor_user_id"]

    dashboard = await client.get("/api/v1/dashboard/overview", headers=admin_headers)
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["data"]["ticket_counts"]["total"] == 1

    audit = await client.get(
        "/api/v1/admin/audit-logs",
        params={"ticket_id": ticket_id, "page_size": 100},
        headers=admin_headers,
    )
    assert audit.status_code == 200, audit.text
    assert {item["action_code"] for item in audit.json()["data"]["items"]} >= {
        "TICKET_CREATED",
        "TICKET_ASSIGNED",
    }
