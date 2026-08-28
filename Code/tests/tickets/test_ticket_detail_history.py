from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_resolution import TicketResolution
from app.models.ticket_sla import TicketSLA
from app.models.ticket_status import TicketStatus
from app.models.ticket_status_history import TicketStatusHistory
from app.models.user import User
from app.models.user_role import UserRole
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def ticket_detail_data(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        other_requester = User(
            email="detail.other@example.com",
            full_name="Detail Other Requester",
            password_hash=hash_password("CorrectPassword123!"),
            is_active=True,
        )
        statuses = [
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
        ]
        session.add_all([other_requester, *statuses])
        await session.flush()
        session.add(
            UserRole(
                user_id=other_requester.user_id,
                role_id=seeded_users["requester_role_id"],
            )
        )
        policy = SLAPolicy(
            priority_id=seeded_users["active_priority_id"],
            version_no=1,
            response_target_minutes=30,
            resolution_target_minutes=240,
            effective_from=now - timedelta(days=30),
            is_active=True,
        )
        session.add(policy)
        await session.flush()

        ticket = Ticket(
            ticket_code="TK-20260828-DETAIL000001",
            requester_id=seeded_users["active_user_id"],
            category_id=seeded_users["active_category_id"],
            priority_id=seeded_users["active_priority_id"],
            current_status_code="IN_PROGRESS",
            title="Chi tiết ticket cần kiểm tra",
            description="Nội dung đầy đủ phục vụ kiểm thử trang chi tiết.",
            first_response_at=now - timedelta(hours=2),
            created_at=now - timedelta(hours=3),
            updated_at=now - timedelta(minutes=5),
        )
        foreign_ticket = Ticket(
            ticket_code="TK-20260828-DETAIL000002",
            requester_id=other_requester.user_id,
            category_id=seeded_users["active_category_id"],
            priority_id=seeded_users["active_priority_id"],
            current_status_code="NEW",
            title="Ticket không thuộc phạm vi",
            description="Ticket dùng để kiểm tra phân quyền dữ liệu.",
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
        )
        session.add_all([ticket, foreign_ticket])
        await session.flush()

        past_assignment = TicketAssignment(
            ticket_id=ticket.ticket_id,
            assignee_id=seeded_users["admin_user_id"],
            assigned_by=seeded_users["admin_user_id"],
            assigned_at=now - timedelta(hours=2, minutes=50),
            ended_at=now - timedelta(hours=2, minutes=30),
            is_current=False,
            reason="Điều chuyển sang chuyên viên",
        )
        current_assignment = TicketAssignment(
            ticket_id=ticket.ticket_id,
            assignee_id=seeded_users["processor_user_id"],
            assigned_by=seeded_users["admin_user_id"],
            assigned_at=now - timedelta(hours=2, minutes=30),
            is_current=True,
            reason="Phân công xử lý",
        )
        public_comment = Comment(
            ticket_id=ticket.ticket_id,
            author_id=seeded_users["active_user_id"],
            content="Thông tin bổ sung công khai",
            visibility="PUBLIC",
            comment_type="REPLY",
            created_at=now - timedelta(hours=2),
        )
        internal_comment = Comment(
            ticket_id=ticket.ticket_id,
            author_id=seeded_users["processor_user_id"],
            content="Ghi chú chỉ nội bộ được xem",
            visibility="INTERNAL",
            comment_type="SYSTEM_NOTE",
            created_at=now - timedelta(hours=1),
        )
        session.add_all(
            [
                past_assignment,
                current_assignment,
                public_comment,
                internal_comment,
            ]
        )
        await session.flush()
        direct_attachment = Attachment(
            ticket_id=ticket.ticket_id,
            comment_id=None,
            uploaded_by=seeded_users["active_user_id"],
            file_name="minh-chung.pdf",
            storage_path=f"{ticket.ticket_id}/private-object.pdf",
            mime_type="application/pdf",
            file_size=512,
            uploaded_at=now - timedelta(hours=2),
        )
        internal_attachment = Attachment(
            ticket_id=ticket.ticket_id,
            comment_id=internal_comment.comment_id,
            uploaded_by=seeded_users["processor_user_id"],
            file_name="noi-bo.txt",
            storage_path=f"{ticket.ticket_id}/private-internal.txt",
            mime_type="text/plain",
            file_size=128,
            uploaded_at=now - timedelta(minutes=50),
        )
        histories = [
            TicketStatusHistory(
                ticket_id=ticket.ticket_id,
                from_status_code=None,
                to_status_code="NEW",
                changed_by=seeded_users["active_user_id"],
                reason="Ticket được tạo",
                changed_at=now - timedelta(hours=3),
            ),
            TicketStatusHistory(
                ticket_id=ticket.ticket_id,
                from_status_code="NEW",
                to_status_code="ASSIGNED",
                changed_by=seeded_users["admin_user_id"],
                reason="Phân công",
                changed_at=now - timedelta(hours=2, minutes=30),
            ),
            TicketStatusHistory(
                ticket_id=ticket.ticket_id,
                from_status_code="ASSIGNED",
                to_status_code="IN_PROGRESS",
                changed_by=seeded_users["processor_user_id"],
                reason="Bắt đầu xử lý",
                changed_at=now - timedelta(hours=2),
            ),
        ]
        resolution = TicketResolution(
            ticket_id=ticket.ticket_id,
            resolved_by=seeded_users["processor_user_id"],
            cycle_no=1,
            resolution_note="Khôi phục cấu hình dịch vụ",
            resolved_at=now - timedelta(minutes=30),
        )
        response_sla = TicketSLA(
            ticket_id=ticket.ticket_id,
            sla_policy_id=policy.sla_policy_id,
            sla_type="RESPONSE",
            cycle_no=1,
            started_at=now - timedelta(hours=3),
            due_at=now - timedelta(hours=2, minutes=30),
            completed_at=now - timedelta(hours=2, minutes=40),
            runtime_status="COMPLETED",
            result="MET",
        )
        resolution_sla = TicketSLA(
            ticket_id=ticket.ticket_id,
            sla_policy_id=policy.sla_policy_id,
            sla_type="RESOLUTION",
            cycle_no=1,
            started_at=now - timedelta(hours=3),
            due_at=now + timedelta(hours=1),
            runtime_status="RUNNING",
        )
        session.add_all(
            [
                direct_attachment,
                internal_attachment,
                *histories,
                resolution,
                response_sla,
                resolution_sla,
            ]
        )
        await session.commit()

    return {
        "ticket_id": ticket.ticket_id,
        "foreign_ticket_id": foreign_ticket.ticket_id,
        "other_requester_id": other_requester.user_id,
    }


async def test_ticket_detail_requires_authentication(client, ticket_detail_data):
    response = await client.get(f"/api/v1/tickets/{ticket_detail_data['ticket_id']}")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_MISSING"


async def test_requester_sees_complete_safe_ticket_detail(
    client,
    credentials,
    seeded_users,
    ticket_detail_data,
):
    response = await client.get(
        f"/api/v1/tickets/{ticket_detail_data['ticket_id']}",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 200, response.text
    ticket = response.json()["data"]
    assert ticket["requester"]["user_id"] == seeded_users["active_user_id"]
    assert ticket["current_assignment"]["assignee"]["user_id"] == seeded_users["processor_user_id"]
    assert ticket["attachments"][0]["file_name"] == "minh-chung.pdf"
    assert ticket["sla_summary"]["response_sla"]["result"] == "MET"
    assert len(ticket["sla_summary"]["resolution_cycles"]) == 1
    assert ticket["resolutions"][0]["cycle_no"] == 1
    assert "VIEW_ASSIGNMENT_HISTORY" not in ticket["permissions"]
    assert "storage_path" not in response.text
    assert "password_hash" not in response.text


async def test_requester_cannot_view_foreign_ticket(
    client,
    credentials,
    ticket_detail_data,
):
    response = await client.get(
        f"/api/v1/tickets/{ticket_detail_data['foreign_ticket_id']}",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "TICKET_ACCESS_DENIED"


async def test_current_processor_and_admin_can_view_scoped_detail(
    client,
    processor_credentials,
    admin_credentials,
    ticket_detail_data,
):
    processor_response = await client.get(
        f"/api/v1/tickets/{ticket_detail_data['ticket_id']}",
        headers=await _headers(client, processor_credentials),
    )
    admin_response = await client.get(
        f"/api/v1/tickets/{ticket_detail_data['foreign_ticket_id']}",
        headers=await _headers(client, admin_credentials),
    )
    assert processor_response.status_code == 200
    assert "VIEW_INTERNAL_COMMENTS" in processor_response.json()["data"]["permissions"]
    assert admin_response.status_code == 200


async def test_missing_ticket_returns_404(client, admin_credentials, ticket_detail_data):
    response = await client.get(
        "/api/v1/tickets/999999",
        headers=await _headers(client, admin_credentials),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "TICKET_NOT_FOUND"


async def test_requester_comments_hide_internal_content_and_attachment(
    client,
    credentials,
    ticket_detail_data,
):
    response = await client.get(
        f"/api/v1/tickets/{ticket_detail_data['ticket_id']}/comments",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert [item["visibility"] for item in data["items"]] == ["PUBLIC"]
    assert "noi-bo.txt" not in response.text


async def test_current_processor_sees_internal_comment_attachment(
    client,
    processor_credentials,
    ticket_detail_data,
):
    response = await client.get(
        f"/api/v1/tickets/{ticket_detail_data['ticket_id']}/comments",
        headers=await _headers(client, processor_credentials),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 2
    internal = next(item for item in data["items"] if item["visibility"] == "INTERNAL")
    assert internal["attachments"][0]["file_name"] == "noi-bo.txt"
    assert "storage_path" not in response.text


async def test_status_history_is_chronological_and_paginated(
    client,
    credentials,
    ticket_detail_data,
):
    response = await client.get(
        f"/api/v1/tickets/{ticket_detail_data['ticket_id']}/status-history?page=2&page_size=2",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3
    assert data["total_pages"] == 2
    assert data["items"][0]["to_status_code"] == "IN_PROGRESS"


async def test_assignment_history_is_restricted_and_paginated(
    client,
    credentials,
    processor_credentials,
    ticket_detail_data,
):
    url = f"/api/v1/tickets/{ticket_detail_data['ticket_id']}/assignments"
    requester_response = await client.get(
        url,
        headers=await _headers(client, credentials),
    )
    processor_response = await client.get(
        f"{url}?page=1&page_size=1",
        headers=await _headers(client, processor_credentials),
    )
    assert requester_response.status_code == 403
    assert processor_response.status_code == 200
    assert processor_response.json()["data"]["total"] == 2
    assert processor_response.json()["data"]["total_pages"] == 2


async def test_unassigned_processor_cannot_view_ticket(
    client,
    processor_credentials,
    ticket_detail_data,
):
    response = await client.get(
        f"/api/v1/tickets/{ticket_detail_data['foreign_ticket_id']}",
        headers=await _headers(client, processor_credentials),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "TICKET_ACCESS_DENIED"


async def test_create_ticket_initializes_history_and_sla(
    client,
    credentials,
    seeded_users,
    ticket_detail_data,
):
    headers = await _headers(client, credentials)
    response = await client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "title": "Ticket có SLA ban đầu",
            "description": "Kiểm tra lịch sử và SLA được tạo cùng transaction.",
            "category_id": seeded_users["active_category_id"],
            "priority_id": seeded_users["active_priority_id"],
        },
    )
    assert response.status_code == 201, response.text
    ticket_id = response.json()["data"]["ticket_id"]
    history = await client.get(
        f"/api/v1/tickets/{ticket_id}/status-history",
        headers=headers,
    )
    detail = await client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert history.status_code == 200
    assert history.json()["data"]["items"][0]["to_status_code"] == "NEW"
    assert detail.status_code == 200
    assert detail.json()["data"]["sla_summary"]["response_sla"] is not None
    assert len(detail.json()["data"]["sla_summary"]["resolution_cycles"]) == 1


async def test_timeline_pagination_is_validated(
    client,
    credentials,
    ticket_detail_data,
):
    response = await client.get(
        f"/api/v1/tickets/{ticket_detail_data['ticket_id']}/comments?page=0&page_size=101",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
