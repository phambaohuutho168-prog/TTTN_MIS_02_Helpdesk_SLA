"""CV047 - Functional test cho luồng ticket bình thường.

Luồng nghiệp vụ được kiểm thử qua API thật của ứng dụng:
Tạo -> Phân công -> Phản hồi -> Xử lý -> Đóng -> Đánh giá.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.sla_policy import SLAPolicy
from app.models.ticket_status import TicketStatus
from tests.conftest import login_client


async def _auth_headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def cv047_runtime_configuration(session_factory, seeded_users):
    """Bổ sung trạng thái và SLA cần cho một luồng ticket hoàn chỉnh."""
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


async def test_cv047_normal_ticket_flow(
    client,
    credentials,
    admin_credentials,
    processor_credentials,
    seeded_users,
    cv047_runtime_configuration,
):
    requester_headers = await _auth_headers(client, credentials)
    admin_headers = await _auth_headers(client, admin_credentials)
    processor_headers = await _auth_headers(client, processor_credentials)

    # FT-01 - Requester tạo ticket.
    created = await client.post(
        "/api/v1/tickets",
        headers=requester_headers,
        json={
            "title": "CV047 - Không truy cập được hệ thống nghiệp vụ",
            "description": (
                "Người dùng nhận thông báo không đủ quyền khi đăng nhập "
                "hệ thống nghiệp vụ nội bộ."
            ),
            "category_id": seeded_users["active_category_id"],
            "priority_id": seeded_users["active_priority_id"],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["code"] == "TICKET_CREATED"
    ticket_id = created.json()["data"]["ticket_id"]
    assert created.json()["data"]["current_status_code"] == "NEW"

    # FT-02 - Admin phân công ticket cho Processor.
    assigned = await client.put(
        f"/api/v1/tickets/{ticket_id}/assignment",
        headers=admin_headers,
        json={
            "assignee_id": seeded_users["processor_user_id"],
            "reason": "Phân công đúng nhóm hỗ trợ ứng dụng",
        },
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["code"] == "TICKET_ASSIGNED"
    assert assigned.json()["data"]["assignee"]["user_id"] == seeded_users["processor_user_id"]

    # FT-03 - Processor phản hồi công khai; đây là first response của SLA.
    replied = await client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers=processor_headers,
        json={
            "content": "Đã tiếp nhận yêu cầu và đang kiểm tra quyền truy cập.",
            "visibility": "PUBLIC",
            "comment_type": "REPLY",
        },
    )
    assert replied.status_code == 201, replied.text
    assert replied.json()["code"] == "COMMENT_CREATED"
    assert replied.json()["data"]["author"]["user_id"] == seeded_users["processor_user_id"]

    # FT-04 - Processor bắt đầu xử lý rồi xác nhận đã xử lý xong.
    started = await client.post(
        f"/api/v1/tickets/{ticket_id}/start",
        headers=processor_headers,
        json={"reason": "Bắt đầu kiểm tra và cấp lại quyền"},
    )
    assert started.status_code == 200, started.text
    assert started.json()["code"] == "TICKET_STARTED"
    assert started.json()["data"]["status"]["status_code"] == "IN_PROGRESS"

    resolved = await client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        headers=processor_headers,
        json={
            "resolution_note": (
                "Đã đồng bộ lại vai trò người dùng và xác nhận đăng nhập thành công."
            )
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["code"] == "TICKET_RESOLVED"
    assert resolved.json()["data"]["status"]["status_code"] == "RESOLVED"

    # FT-05 - Requester xác nhận kết quả và đóng ticket.
    closed = await client.post(
        f"/api/v1/tickets/{ticket_id}/close",
        headers=requester_headers,
        json={"reason": "Đã truy cập lại được và đồng ý đóng yêu cầu"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["code"] == "TICKET_CLOSED"
    assert closed.json()["data"]["status"]["status_code"] == "CLOSED"
    assert closed.json()["data"]["closed_by"]["user_id"] == seeded_users["active_user_id"]
    assert closed.json()["data"]["closed_at"] is not None

    # FT-06 - Requester đánh giá mức hài lòng sau khi ticket đã đóng.
    rated = await client.post(
        f"/api/v1/tickets/{ticket_id}/rating",
        headers=requester_headers,
        json={
            "score": 5,
            "comment": "Phản hồi rõ ràng, xử lý nhanh và đúng yêu cầu.",
        },
    )
    assert rated.status_code == 201, rated.text
    assert rated.json()["code"] == "RATING_CREATED"
    assert rated.json()["data"]["score"] == 5

    # FT-07 - Đối soát bằng chứng xuyên suốt sau giao dịch.
    history = await client.get(
        f"/api/v1/tickets/{ticket_id}/status-history?page_size=20",
        headers=requester_headers,
    )
    assert history.status_code == 200, history.text
    assert [item["to_status_code"] for item in history.json()["data"]["items"]] == [
        "NEW",
        "ASSIGNED",
        "IN_PROGRESS",
        "RESOLVED",
        "CLOSED",
    ]

    requester_notifications = await client.get(
        "/api/v1/notifications?page_size=100",
        headers=requester_headers,
    )
    assert requester_notifications.status_code == 200, requester_notifications.text
    notification_types = {
        item["type"]
        for item in requester_notifications.json()["data"]["items"]
        if item["ticket_id"] == ticket_id
    }
    assert {"TICKET_REPLY", "TICKET_RESOLVED"} <= notification_types

    audit = await client.get(
        f"/api/v1/admin/audit-logs?ticket_id={ticket_id}&page_size=100",
        headers=admin_headers,
    )
    assert audit.status_code == 200, audit.text
    audit_codes = {item["action_code"] for item in audit.json()["data"]["items"]}
    assert {
        "TICKET_CREATED",
        "TICKET_ASSIGNED",
        "COMMENT_CREATED",
        "TICKET_STARTED",
        "TICKET_RESOLVED",
        "TICKET_CLOSED",
        "TICKET_RATED",
    } <= audit_codes

    dashboard = await client.get("/api/v1/dashboard/overview", headers=admin_headers)
    assert dashboard.status_code == 200, dashboard.text
    dashboard_data = dashboard.json()["data"]
    assert dashboard_data["ticket_counts"]["closed"] == 1
    assert dashboard_data["satisfaction"]["rated_tickets"] == 1
    assert dashboard_data["satisfaction"]["average_score"] == 5.0
    assert dashboard_data["sla_compliance"]["compliance_rate"] == 100.0
