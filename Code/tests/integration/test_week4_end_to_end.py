from datetime import datetime, timedelta, timezone

import pytest

from app.models.sla_policy import SLAPolicy
from app.models.ticket_status import TicketStatus
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def week4_runtime_configuration(session_factory, seeded_users):
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


async def test_week4_main_flow_runs_end_to_end(
    client,
    credentials,
    admin_credentials,
    processor_credentials,
    seeded_users,
    week4_runtime_configuration,
):
    requester_headers = await _headers(client, credentials)
    admin_headers = await _headers(client, admin_credentials)
    processor_headers = await _headers(client, processor_credentials)

    created = await client.post(
        "/api/v1/tickets",
        headers=requester_headers,
        json={
            "title": "Kiểm thử tích hợp Tuần 4",
            "description": "Luồng ticket chạy xuyên suốt từ tạo đến đánh giá.",
            "category_id": seeded_users["active_category_id"],
            "priority_id": seeded_users["active_priority_id"],
        },
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["data"]["ticket_id"]
    assert created.json()["data"]["current_status_code"] == "NEW"

    assigned = await client.put(
        f"/api/v1/tickets/{ticket_id}/assignment",
        headers=admin_headers,
        json={
            "assignee_id": seeded_users["processor_user_id"],
            "reason": "Phân công kiểm thử tích hợp",
        },
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["code"] == "TICKET_ASSIGNED"

    started = await client.post(
        f"/api/v1/tickets/{ticket_id}/start",
        headers=processor_headers,
        json={"reason": "Bắt đầu tiếp nhận"},
    )
    assert started.status_code == 200, started.text
    assert started.json()["data"]["status"]["status_code"] == "IN_PROGRESS"

    replied = await client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers=processor_headers,
        json={
            "content": "Đã xác định nguyên nhân và đang áp dụng biện pháp khắc phục.",
            "visibility": "PUBLIC",
            "comment_type": "REPLY",
        },
    )
    assert replied.status_code == 201, replied.text
    assert replied.json()["code"] == "COMMENT_CREATED"

    resolved = await client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        headers=processor_headers,
        json={"resolution_note": "Đã cấu hình lại quyền và xác nhận truy cập thành công."},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["data"]["status"]["status_code"] == "RESOLVED"

    closed = await client.post(
        f"/api/v1/tickets/{ticket_id}/close",
        headers=requester_headers,
        json={"reason": "Đã kiểm tra và đồng ý kết quả xử lý"},
    )
    assert closed.status_code == 200, closed.text
    closed_data = closed.json()["data"]
    assert closed_data["status"]["status_code"] == "CLOSED"
    assert closed_data["closed_by"]["user_id"] == seeded_users["active_user_id"]
    assert closed_data["closed_at"] is not None

    rated = await client.post(
        f"/api/v1/tickets/{ticket_id}/rating",
        headers=requester_headers,
        json={"score": 5, "comment": "Luồng hỗ trợ rõ ràng và hoàn tất đúng hạn."},
    )
    assert rated.status_code == 201, rated.text
    assert rated.json()["data"]["score"] == 5

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
    assert requester_notifications.status_code == 200
    requester_types = {
        item["type"] for item in requester_notifications.json()["data"]["items"]
        if item["ticket_id"] == ticket_id
    }
    assert {"TICKET_REPLY", "TICKET_RESOLVED"} <= requester_types

    audit = await client.get(
        f"/api/v1/admin/audit-logs?ticket_id={ticket_id}&page_size=100",
        headers=admin_headers,
    )
    assert audit.status_code == 200, audit.text
    audit_codes = {item["action_code"] for item in audit.json()["data"]["items"]}
    assert {
        "TICKET_CREATED",
        "TICKET_ASSIGNED",
        "TICKET_STARTED",
        "COMMENT_CREATED",
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


async def test_integration_error_contract_and_empty_result(
    client,
    credentials,
    processor_credentials,
    seeded_users,
):
    requester_headers = await _headers(client, credentials)
    processor_headers = await _headers(client, processor_credentials)

    invalid = await client.post(
        "/api/v1/tickets",
        headers=requester_headers,
        json={
            "title": "x",
            "description": "ngắn",
            "category_id": 0,
            "priority_id": 0,
            "unexpected": True,
        },
    )
    assert invalid.status_code == 422
    invalid_body = invalid.json()
    assert invalid_body["code"] == "VALIDATION_ERROR"
    assert invalid_body["success"] is False
    assert {error["field"] for error in invalid_body["errors"]} == {
        "title",
        "description",
        "category_id",
        "priority_id",
        "unexpected",
    }

    forbidden = await client.post(
        "/api/v1/tickets",
        headers=processor_headers,
        json={
            "title": "Processor không được tạo",
            "description": "Kiểm tra trạng thái không có quyền ở tầng API.",
            "category_id": seeded_users["active_category_id"],
            "priority_id": seeded_users["active_priority_id"],
        },
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["success"] is False

    empty = await client.get(
        "/api/v1/tickets?q=CV046-NO-MATCH&page=1&page_size=20",
        headers=requester_headers,
    )
    assert empty.status_code == 200
    assert empty.json()["data"]["items"] == []
    assert empty.json()["data"]["total"] == 0


async def test_unknown_route_and_method_use_standard_error_envelope(client):
    not_found = await client.get("/api/v1/endpoint-khong-ton-tai")
    assert not_found.status_code == 404
    assert not_found.json()["code"] == "ROUTE_NOT_FOUND"
    assert not_found.json()["success"] is False
    assert not_found.headers["x-request-id"] == not_found.json()["meta"]["request_id"]

    method_not_allowed = await client.post("/api/v1/health/live")
    assert method_not_allowed.status_code == 405
    assert method_not_allowed.json()["code"] == "METHOD_NOT_ALLOWED"
    assert method_not_allowed.headers["allow"] == "GET"
