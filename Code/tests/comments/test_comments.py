from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.comment import Comment
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_resolution import TicketResolution
from app.models.ticket_sla import TicketSLA
from app.models.ticket_status import TicketStatus
from app.models.user import User
from app.models.user_role import UserRole
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def comment_data(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
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
            ]
        )
        other_requester = User(
            email="comment.other@example.com",
            full_name="Comment Other Requester",
            password_hash=hash_password("CorrectPassword123!"),
            is_active=True,
        )
        session.add(other_requester)
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
            effective_from=now - timedelta(days=1),
            is_active=True,
        )
        session.add(policy)
        await session.flush()

        def ticket(code, status, requester_id=None):
            return Ticket(
                ticket_code=code,
                requester_id=requester_id or seeded_users["active_user_id"],
                category_id=seeded_users["active_category_id"],
                priority_id=seeded_users["active_priority_id"],
                current_status_code=status,
                title=f"Trao đổi {code}",
                description="Ticket dùng để kiểm thử Comment/Solution module.",
                created_at=now - timedelta(hours=1),
                updated_at=now - timedelta(minutes=10),
            )

        owner_ticket = ticket("TK-COM-OWNER", "NEW")
        processor_ticket = ticket("TK-COM-PROCESSOR", "IN_PROGRESS")
        foreign_ticket = ticket(
            "TK-COM-FOREIGN",
            "NEW",
            requester_id=other_requester.user_id,
        )
        terminal_ticket = ticket("TK-COM-TERMINAL", "CLOSED")
        session.add_all(
            [owner_ticket, processor_ticket, foreign_ticket, terminal_ticket]
        )
        await session.flush()
        session.add(
            TicketAssignment(
                ticket_id=processor_ticket.ticket_id,
                assignee_id=seeded_users["processor_user_id"],
                assigned_by=seeded_users["admin_user_id"],
                is_current=True,
                reason="Phân công kiểm thử comment",
            )
        )
        response_sla = TicketSLA(
            ticket_id=processor_ticket.ticket_id,
            sla_policy_id=policy.sla_policy_id,
            sla_type="RESPONSE",
            cycle_no=1,
            started_at=now - timedelta(minutes=10),
            due_at=now + timedelta(minutes=20),
            runtime_status="RUNNING",
        )
        resolution_sla = TicketSLA(
            ticket_id=processor_ticket.ticket_id,
            sla_policy_id=policy.sla_policy_id,
            sla_type="RESOLUTION",
            cycle_no=1,
            started_at=now - timedelta(minutes=10),
            due_at=now + timedelta(hours=3),
            runtime_status="RUNNING",
        )
        session.add_all([response_sla, resolution_sla])
        author_comment = Comment(
            ticket_id=owner_ticket.ticket_id,
            author_id=seeded_users["active_user_id"],
            content="Nội dung ban đầu của requester.",
            visibility="PUBLIC",
            comment_type="REPLY",
            created_at=now - timedelta(minutes=5),
        )
        expired_comment = Comment(
            ticket_id=owner_ticket.ticket_id,
            author_id=seeded_users["active_user_id"],
            content="Trao đổi đã quá thời hạn chỉnh sửa.",
            visibility="PUBLIC",
            comment_type="REPLY",
            created_at=now - timedelta(hours=1),
        )
        terminal_comment = Comment(
            ticket_id=terminal_ticket.ticket_id,
            author_id=seeded_users["active_user_id"],
            content="Trao đổi thuộc ticket đã đóng.",
            visibility="PUBLIC",
            comment_type="REPLY",
            created_at=now - timedelta(minutes=5),
        )
        session.add_all([author_comment, expired_comment, terminal_comment])
        await session.commit()
    return {
        "owner_ticket_id": owner_ticket.ticket_id,
        "processor_ticket_id": processor_ticket.ticket_id,
        "foreign_ticket_id": foreign_ticket.ticket_id,
        "terminal_ticket_id": terminal_ticket.ticket_id,
        "author_comment_id": author_comment.comment_id,
        "expired_comment_id": expired_comment.comment_id,
        "terminal_comment_id": terminal_comment.comment_id,
        "response_sla_id": response_sla.ticket_sla_id,
        "resolution_sla_id": resolution_sla.ticket_sla_id,
        "other_credentials": {
            "email": "comment.other@example.com",
            "password": "CorrectPassword123!",
        },
    }


async def test_com02_requires_authentication(client, comment_data):
    response = await client.post(
        f"/api/v1/tickets/{comment_data['owner_ticket_id']}/comments",
        json={"content": "Trao đổi không có token."},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_MISSING"


async def test_requester_creates_public_reply_with_author_time_and_audit(
    client,
    credentials,
    seeded_users,
    session_factory,
    comment_data,
):
    response = await client.post(
        f"/api/v1/tickets/{comment_data['owner_ticket_id']}/comments",
        headers=await _headers(client, credentials),
        json={"content": "  Tôi đã bổ sung thông tin cần thiết.  "},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["code"] == "COMMENT_CREATED"
    comment = body["data"]
    assert comment["content"] == "Tôi đã bổ sung thông tin cần thiết."
    assert comment["visibility"] == "PUBLIC"
    assert comment["comment_type"] == "REPLY"
    assert comment["author"]["user_id"] == seeded_users["active_user_id"]
    assert comment["created_at"] is not None
    async with session_factory() as session:
        audit = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "COMMENT",
                    AuditLog.entity_id == comment["comment_id"],
                    AuditLog.action_code == "COMMENT_CREATED",
                )
            )
        ).scalar_one()
        assert audit.actor_user_id == seeded_users["active_user_id"]


async def test_requester_cannot_create_internal_note(
    client,
    credentials,
    session_factory,
    comment_data,
):
    response = await client.post(
        f"/api/v1/tickets/{comment_data['owner_ticket_id']}/comments",
        headers=await _headers(client, credentials),
        json={
            "content": "Ghi chú không được phép.",
            "visibility": "INTERNAL",
            "comment_type": "SYSTEM_NOTE",
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "INTERNAL_COMMENT_FORBIDDEN"
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count(Comment.comment_id)).where(
                Comment.ticket_id == comment_data["owner_ticket_id"],
                Comment.visibility == "INTERNAL",
            )
        )
        assert count == 0


async def test_com02_rejects_blank_reserved_type_and_extra_fields(
    client,
    credentials,
    comment_data,
):
    headers = await _headers(client, credentials)
    url = f"/api/v1/tickets/{comment_data['owner_ticket_id']}/comments"
    blank = await client.post(url, headers=headers, json={"content": "   "})
    reserved = await client.post(
        url,
        headers=headers,
        json={"content": "Xin bổ sung.", "comment_type": "REQUEST_INFO"},
    )
    extra = await client.post(
        url,
        headers=headers,
        json={"content": "Hợp lệ", "author_id": 999},
    )
    assert blank.status_code == 422
    assert reserved.status_code == 422
    assert extra.status_code == 422


async def test_foreign_and_terminal_ticket_are_blocked(
    client,
    credentials,
    comment_data,
):
    headers = await _headers(client, credentials)
    foreign = await client.post(
        f"/api/v1/tickets/{comment_data['foreign_ticket_id']}/comments",
        headers=headers,
        json={"content": "Không thuộc ticket của tôi."},
    )
    terminal = await client.post(
        f"/api/v1/tickets/{comment_data['terminal_ticket_id']}/comments",
        headers=headers,
        json={"content": "Ticket đã đóng."},
    )
    assert foreign.status_code == 403
    assert foreign.json()["code"] == "TICKET_ACCESS_DENIED"
    assert terminal.status_code == 409
    assert terminal.json()["code"] == "TICKET_ALREADY_TERMINAL"


async def test_processor_public_reply_completes_response_sla_only_once(
    client,
    processor_credentials,
    session_factory,
    comment_data,
):
    headers = await _headers(client, processor_credentials)
    url = f"/api/v1/tickets/{comment_data['processor_ticket_id']}/comments"
    first = await client.post(
        url,
        headers=headers,
        json={"content": "Đã tiếp nhận và bắt đầu kiểm tra."},
    )
    assert first.status_code == 201, first.text
    async with session_factory() as session:
        ticket = await session.get(Ticket, comment_data["processor_ticket_id"])
        sla = await session.get(TicketSLA, comment_data["response_sla_id"])
        first_response_at = ticket.first_response_at
        assert first_response_at is not None
        assert sla.runtime_status == "COMPLETED"
        assert sla.result == "MET"
        assert sla.completed_at is not None

    second = await client.post(
        url,
        headers=headers,
        json={"content": "Phản hồi công khai lần thứ hai."},
    )
    assert second.status_code == 201
    async with session_factory() as session:
        ticket = await session.get(Ticket, comment_data["processor_ticket_id"])
        assert ticket.first_response_at == first_response_at


async def test_internal_note_is_hidden_from_requester_and_does_not_close_sla(
    client,
    credentials,
    processor_credentials,
    session_factory,
    comment_data,
):
    processor_headers = await _headers(client, processor_credentials)
    created = await client.post(
        f"/api/v1/tickets/{comment_data['processor_ticket_id']}/comments",
        headers=processor_headers,
        json={
            "content": "Ghi chú kỹ thuật chỉ bộ phận xử lý được xem.",
            "visibility": "INTERNAL",
            "comment_type": "SYSTEM_NOTE",
        },
    )
    assert created.status_code == 201, created.text
    async with session_factory() as session:
        ticket = await session.get(Ticket, comment_data["processor_ticket_id"])
        sla = await session.get(TicketSLA, comment_data["response_sla_id"])
        assert ticket.first_response_at is None
        assert sla.runtime_status == "RUNNING"

    requester_list = await client.get(
        f"/api/v1/tickets/{comment_data['processor_ticket_id']}/comments",
        headers=await _headers(client, credentials),
    )
    processor_list = await client.get(
        f"/api/v1/tickets/{comment_data['processor_ticket_id']}/comments",
        headers=processor_headers,
    )
    assert requester_list.status_code == 200
    assert requester_list.json()["data"]["items"] == []
    assert processor_list.status_code == 200
    assert processor_list.json()["data"]["items"][0]["visibility"] == "INTERNAL"


async def test_author_updates_content_without_changing_metadata(
    client,
    credentials,
    seeded_users,
    session_factory,
    comment_data,
):
    response = await client.patch(
        f"/api/v1/comments/{comment_data['author_comment_id']}",
        headers=await _headers(client, credentials),
        json={"content": "Nội dung requester đã chỉnh sửa."},
    )
    assert response.status_code == 200, response.text
    item = response.json()["data"]
    assert item["content"] == "Nội dung requester đã chỉnh sửa."
    assert item["author"]["user_id"] == seeded_users["active_user_id"]
    assert item["visibility"] == "PUBLIC"
    assert item["comment_type"] == "REPLY"
    assert item["updated_at"] is not None
    async with session_factory() as session:
        audit = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "COMMENT",
                    AuditLog.entity_id == comment_data["author_comment_id"],
                    AuditLog.action_code == "COMMENT_UPDATED",
                )
            )
        ).scalar_one()
        assert audit.old_value_json["content"] == "Nội dung ban đầu của requester."


async def test_non_author_and_expired_author_cannot_edit(
    client,
    credentials,
    processor_credentials,
    comment_data,
):
    non_author = await client.patch(
        f"/api/v1/comments/{comment_data['author_comment_id']}",
        headers=await _headers(client, processor_credentials),
        json={"content": "Processor không được sửa comment này."},
    )
    expired = await client.patch(
        f"/api/v1/comments/{comment_data['expired_comment_id']}",
        headers=await _headers(client, credentials),
        json={"content": "Requester sửa quá hạn."},
    )
    assert non_author.status_code == 403
    assert non_author.json()["code"] == "TICKET_ACCESS_DENIED"
    assert expired.status_code == 409
    assert expired.json()["code"] == "COMMENT_NOT_EDITABLE"


async def test_admin_can_edit_expired_comment_but_not_terminal_comment(
    client,
    admin_credentials,
    comment_data,
):
    headers = await _headers(client, admin_credentials)
    expired = await client.patch(
        f"/api/v1/comments/{comment_data['expired_comment_id']}",
        headers=headers,
        json={"content": "Admin hiệu chỉnh nội dung quá hạn."},
    )
    terminal = await client.patch(
        f"/api/v1/comments/{comment_data['terminal_comment_id']}",
        headers=headers,
        json={"content": "Admin không sửa ticket đã kết thúc."},
    )
    assert expired.status_code == 200
    assert terminal.status_code == 409
    assert terminal.json()["code"] == "COMMENT_NOT_EDITABLE"


async def test_missing_comment_and_immutable_fields_are_rejected(
    client,
    credentials,
    comment_data,
):
    headers = await _headers(client, credentials)
    missing = await client.patch(
        "/api/v1/comments/999999",
        headers=headers,
        json={"content": "Không tồn tại."},
    )
    immutable = await client.patch(
        f"/api/v1/comments/{comment_data['author_comment_id']}",
        headers=headers,
        json={"content": "Nội dung mới.", "visibility": "INTERNAL"},
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "COMMENT_NOT_FOUND"
    assert immutable.status_code == 422


async def test_wf04_persists_solution_note_and_returns_it_in_detail(
    client,
    processor_credentials,
    session_factory,
    comment_data,
):
    headers = await _headers(client, processor_credentials)
    response = await client.post(
        f"/api/v1/tickets/{comment_data['processor_ticket_id']}/resolve",
        headers=headers,
        json={
            "resolution_note": (
                "Đã cấu hình lại kết nối và xác nhận dịch vụ ổn định."
            )
        },
    )
    assert response.status_code == 200, response.text
    detail = await client.get(
        f"/api/v1/tickets/{comment_data['processor_ticket_id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    resolutions = detail.json()["data"]["resolutions"]
    assert resolutions[0]["cycle_no"] == 1
    assert "xác nhận dịch vụ ổn định" in resolutions[0]["resolution_note"]
    async with session_factory() as session:
        row = (
            await session.execute(
                select(TicketResolution).where(
                    TicketResolution.ticket_id == comment_data["processor_ticket_id"]
                )
            )
        ).scalar_one()
        assert row.resolved_by is not None
