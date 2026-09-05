from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.notification import Notification
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_status import TicketStatus
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def notification_data(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        session.add_all(
            [
                TicketStatus(
                    status_code="ASSIGNED",
                    status_name="Đã phân công",
                    is_terminal=False,
                ),
                TicketStatus(
                    status_code="IN_PROGRESS",
                    status_name="Đang xử lý",
                    is_terminal=False,
                ),
                TicketStatus(
                    status_code="PENDING_INFO",
                    status_name="Chờ bổ sung",
                    is_terminal=False,
                ),
                TicketStatus(
                    status_code="RESOLVED",
                    status_name="Đã xử lý",
                    is_terminal=False,
                ),
            ]
        )

        def make_ticket(key: str, status_code: str) -> Ticket:
            return Ticket(
                ticket_code=f"TK-CV042-{key}",
                requester_id=seeded_users["active_user_id"],
                category_id=seeded_users["active_category_id"],
                priority_id=seeded_users["active_priority_id"],
                current_status_code=status_code,
                title=f"CV042 {key}",
                description="Kiểm thử thông báo in-app theo sự kiện ticket.",
                created_at=now - timedelta(days=1),
                updated_at=now,
            )

        tickets = {
            "assigned": make_ticket("ASSIGNED", "ASSIGNED"),
            "new": make_ticket("NEW", "NEW"),
            "workflow": make_ticket("WORKFLOW", "IN_PROGRESS"),
            "resolve": make_ticket("RESOLVE", "IN_PROGRESS"),
        }
        session.add_all(tickets.values())
        await session.flush()
        session.add_all(
            [
                TicketAssignment(
                    ticket_id=tickets[key].ticket_id,
                    assignee_id=seeded_users["processor_user_id"],
                    assigned_by=seeded_users["admin_user_id"],
                    assigned_at=now - timedelta(hours=2),
                    is_current=True,
                    reason="Phân công kiểm thử CV042.",
                )
                for key in ("assigned", "workflow", "resolve")
            ]
        )
        notifications = {
            "requester_assignment": Notification(
                recipient_id=seeded_users["active_user_id"],
                ticket_id=tickets["assigned"].ticket_id,
                notification_type="TICKET_ASSIGNED",
                title="Ticket đã được phân công",
                message="Ticket đã có người xử lý.",
                is_read=False,
                created_at=now - timedelta(minutes=3),
            ),
            "requester_reply": Notification(
                recipient_id=seeded_users["active_user_id"],
                ticket_id=tickets["assigned"].ticket_id,
                notification_type="TICKET_REPLY",
                title="Phản hồi mới",
                message="Ticket có phản hồi công khai mới.",
                is_read=True,
                created_at=now - timedelta(minutes=2),
                read_at=now - timedelta(minutes=1),
            ),
            "requester_warning": Notification(
                recipient_id=seeded_users["active_user_id"],
                ticket_id=tickets["assigned"].ticket_id,
                notification_type="SLA_WARNING",
                title="SLA sắp quá hạn",
                message="Ticket đã đạt ngưỡng cảnh báo SLA.",
                is_read=False,
                created_at=now,
            ),
            "processor_reply": Notification(
                recipient_id=seeded_users["processor_user_id"],
                ticket_id=tickets["assigned"].ticket_id,
                notification_type="TICKET_REPLY",
                title="Phản hồi từ người gửi",
                message="Ticket có phản hồi công khai mới.",
                is_read=False,
                created_at=now - timedelta(minutes=1),
            ),
        }
        session.add_all(notifications.values())
        await session.commit()
        return {
            **{key: ticket.ticket_id for key, ticket in tickets.items()},
            **{
                key: notification.notification_id
                for key, notification in notifications.items()
            },
        }


async def test_notification_list_requires_authentication(client):
    response = await client.get("/api/v1/notifications")
    assert response.status_code == 401


async def test_user_lists_only_own_notifications_in_newest_order(
    client,
    credentials,
    notification_data,
):
    response = await client.get(
        "/api/v1/notifications",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == "NOTIFICATIONS_LISTED"
    assert body["data"]["total"] == 3
    assert [item["type"] for item in body["data"]["items"]] == [
        "SLA_WARNING",
        "TICKET_REPLY",
        "TICKET_ASSIGNED",
    ]
    assert all(
        item["notification_id"] != notification_data["processor_reply"]
        for item in body["data"]["items"]
    )
    assert body["data"]["items"][0]["deep_link"] == (
        f"/tickets/{notification_data['assigned']}"
    )


async def test_notification_list_supports_read_and_type_filters(
    client,
    credentials,
    notification_data,
):
    response = await client.get(
        "/api/v1/notifications?is_read=false&type=ticket_assigned",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == 1
    assert response.json()["data"]["items"][0]["type"] == "TICKET_ASSIGNED"


async def test_notification_list_is_paginated(
    client,
    credentials,
    notification_data,
):
    response = await client.get(
        "/api/v1/notifications?page=2&page_size=1",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["page"] == 2
    assert data["page_size"] == 1
    assert data["total"] == 3
    assert data["total_pages"] == 3
    assert data["items"][0]["type"] == "TICKET_REPLY"


async def test_owner_marks_one_notification_read_idempotently(
    client,
    credentials,
    notification_data,
):
    url = (
        f"/api/v1/notifications/"
        f"{notification_data['requester_assignment']}/read"
    )
    headers = await _headers(client, credentials)
    first = await client.patch(url, headers=headers)
    second = await client.patch(url, headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["data"]["is_read"] is True
    assert first.json()["data"]["read_at"] is not None
    assert second.json()["data"]["read_at"] == first.json()["data"]["read_at"]
    assert first.json()["data"]["updated_at"] == first.json()["data"]["read_at"]


async def test_user_cannot_mark_another_users_notification(
    client,
    credentials,
    notification_data,
):
    response = await client.patch(
        f"/api/v1/notifications/{notification_data['processor_reply']}/read",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOTIFICATION_NOT_FOUND"


async def test_mark_all_read_can_be_filtered_and_is_idempotent(
    client,
    credentials,
    session_factory,
    notification_data,
):
    headers = await _headers(client, credentials)
    first = await client.patch(
        "/api/v1/notifications/read-all?type=ticket_assigned",
        headers=headers,
    )
    second = await client.patch(
        "/api/v1/notifications/read-all?type=TICKET_ASSIGNED",
        headers=headers,
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["updated_count"] == 1
    assert second.json()["data"]["updated_count"] == 0
    async with session_factory() as session:
        warning = await session.get(
            Notification,
            notification_data["requester_warning"],
        )
        processor = await session.get(
            Notification,
            notification_data["processor_reply"],
        )
        assert warning.is_read is False
        assert processor.is_read is False


@pytest.mark.parametrize(
    "query",
    ["page=0", "page_size=101", f"type={'X' * 31}"],
)
async def test_notification_query_is_validated(client, credentials, query):
    response = await client.get(
        f"/api/v1/notifications?{query}",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_assignment_notifies_new_assignee_and_requester(
    client,
    admin_credentials,
    processor_credentials,
    credentials,
    seeded_users,
    notification_data,
):
    response = await client.put(
        f"/api/v1/tickets/{notification_data['new']}/assignment",
        headers=await _headers(client, admin_credentials),
        json={"assignee_id": seeded_users["processor_user_id"]},
    )
    assert response.status_code == 200, response.text

    processor_box = await client.get(
        "/api/v1/notifications?type=TICKET_ASSIGNED",
        headers=await _headers(client, processor_credentials),
    )
    requester_box = await client.get(
        "/api/v1/notifications?type=TICKET_ASSIGNED",
        headers=await _headers(client, credentials),
    )
    assert any(
        item["ticket_id"] == notification_data["new"]
        for item in processor_box.json()["data"]["items"]
    )
    assert any(
        item["ticket_id"] == notification_data["new"]
        for item in requester_box.json()["data"]["items"]
    )


async def test_processor_public_reply_notifies_requester_without_content_leak(
    client,
    processor_credentials,
    credentials,
    notification_data,
):
    secret_content = "Mật khẩu tạm thời là SuperSecret123!"
    response = await client.post(
        f"/api/v1/tickets/{notification_data['assigned']}/comments",
        headers=await _headers(client, processor_credentials),
        json={
            "content": secret_content,
            "visibility": "PUBLIC",
            "comment_type": "REPLY",
        },
    )
    assert response.status_code == 201, response.text
    box = await client.get(
        "/api/v1/notifications?type=TICKET_REPLY",
        headers=await _headers(client, credentials),
    )
    newest = box.json()["data"]["items"][0]
    assert newest["ticket_id"] == notification_data["assigned"]
    assert secret_content not in newest["message"]
    assert "SuperSecret123" not in newest["message"]


async def test_requester_public_reply_notifies_current_processor(
    client,
    credentials,
    processor_credentials,
    notification_data,
):
    response = await client.post(
        f"/api/v1/tickets/{notification_data['assigned']}/comments",
        headers=await _headers(client, credentials),
        json={"content": "Tôi đã thử lại theo hướng dẫn."},
    )
    assert response.status_code == 201, response.text
    box = await client.get(
        "/api/v1/notifications?type=TICKET_REPLY",
        headers=await _headers(client, processor_credentials),
    )
    assert box.json()["data"]["items"][0]["ticket_id"] == (
        notification_data["assigned"]
    )


async def test_internal_comment_does_not_notify_requester(
    client,
    processor_credentials,
    session_factory,
    seeded_users,
    notification_data,
):
    async with session_factory() as session:
        before = await session.scalar(
            select(func.count(Notification.notification_id)).where(
                Notification.recipient_id == seeded_users["active_user_id"],
                Notification.ticket_id == notification_data["assigned"],
            )
        )
    response = await client.post(
        f"/api/v1/tickets/{notification_data['assigned']}/comments",
        headers=await _headers(client, processor_credentials),
        json={
            "content": "Ghi chú nội bộ không được lộ cho Requester.",
            "visibility": "INTERNAL",
            "comment_type": "SYSTEM_NOTE",
        },
    )
    assert response.status_code == 201, response.text
    async with session_factory() as session:
        after = await session.scalar(
            select(func.count(Notification.notification_id)).where(
                Notification.recipient_id == seeded_users["active_user_id"],
                Notification.ticket_id == notification_data["assigned"],
            )
        )
    assert after == before


async def test_request_info_status_notifies_requester(
    client,
    processor_credentials,
    credentials,
    notification_data,
):
    response = await client.post(
        f"/api/v1/tickets/{notification_data['workflow']}/request-info",
        headers=await _headers(client, processor_credentials),
        json={"content": "Vui lòng cung cấp thêm ảnh lỗi màn hình."},
    )
    assert response.status_code == 200, response.text
    box = await client.get(
        "/api/v1/notifications?type=INFO_REQUESTED",
        headers=await _headers(client, credentials),
    )
    assert box.json()["data"]["items"][0]["ticket_id"] == (
        notification_data["workflow"]
    )


async def test_resolved_status_notifies_requester(
    client,
    processor_credentials,
    credentials,
    notification_data,
):
    response = await client.post(
        f"/api/v1/tickets/{notification_data['resolve']}/resolve",
        headers=await _headers(client, processor_credentials),
        json={
            "resolution_note": (
                "Đã cập nhật cấu hình và kiểm tra hoàn tất."
            )
        },
    )
    assert response.status_code == 200, response.text
    box = await client.get(
        "/api/v1/notifications?type=TICKET_RESOLVED",
        headers=await _headers(client, credentials),
    )
    assert box.json()["data"]["items"][0]["ticket_id"] == (
        notification_data["resolve"]
    )
