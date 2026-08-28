from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.comment import Comment
from app.models.sla_pause_period import SLAPausePeriod
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_resolution import TicketResolution
from app.models.ticket_sla import TicketSLA
from app.models.ticket_status import TicketStatus
from app.models.ticket_status_history import TicketStatusHistory
from app.models.user import User
from app.models.user_role import UserRole
from app.services.workflow_service import auto_close_expired_tickets
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def workflow_data(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        session.add_all(
            [
                TicketStatus(status_code="ASSIGNED", status_name="Đã phân công"),
                TicketStatus(status_code="IN_PROGRESS", status_name="Đang xử lý"),
                TicketStatus(status_code="PENDING_INFO", status_name="Chờ thông tin"),
                TicketStatus(status_code="RESOLVED", status_name="Đã xử lý"),
                TicketStatus(
                    status_code="CLOSED",
                    status_name="Đã đóng",
                    is_terminal=True,
                ),
                TicketStatus(status_code="REOPENED", status_name="Đã mở lại"),
                TicketStatus(
                    status_code="REJECTED",
                    status_name="Bị từ chối",
                    is_terminal=True,
                ),
            ]
        )
        other_requester = User(
            email="workflow.other.requester@example.com",
            full_name="Workflow Other Requester",
            password_hash=hash_password("CorrectPassword123!"),
            is_active=True,
        )
        other_processor = User(
            email="workflow.other.processor@example.com",
            full_name="Workflow Other Processor",
            password_hash=hash_password("CorrectPassword123!"),
            department_id=seeded_users["department_id"],
            is_active=True,
        )
        session.add_all([other_requester, other_processor])
        await session.flush()
        session.add_all(
            [
                UserRole(
                    user_id=other_requester.user_id,
                    role_id=seeded_users["requester_role_id"],
                ),
                UserRole(
                    user_id=other_processor.user_id,
                    role_id=seeded_users["processor_role_id"],
                ),
            ]
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

        def make_ticket(key: str, status_code: str, *, requester_id: int | None = None):
            return Ticket(
                ticket_code=f"TK-20260828-WF-{key.upper():0>12}",
                requester_id=requester_id or seeded_users["active_user_id"],
                category_id=seeded_users["active_category_id"],
                priority_id=seeded_users["active_priority_id"],
                current_status_code=status_code,
                title=f"Workflow {key}",
                description=f"Ticket kiểm thử workflow {key}.",
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(minutes=5),
            )

        tickets = {
            "assigned": make_ticket("assigned", "ASSIGNED"),
            "wrong_assignee": make_ticket("wrongassignee", "ASSIGNED"),
            "request_info": make_ticket("requestinfo", "IN_PROGRESS"),
            "pending": make_ticket("pending", "PENDING_INFO"),
            "foreign_pending": make_ticket(
                "foreignpending",
                "PENDING_INFO",
                requester_id=other_requester.user_id,
            ),
            "resolve": make_ticket("resolve", "IN_PROGRESS"),
            "close": make_ticket("close", "RESOLVED"),
            "admin_close": make_ticket("adminclose", "RESOLVED"),
            "reopen": make_ticket("reopen", "RESOLVED"),
            "expired": make_ticket("expired", "RESOLVED"),
            "resume": make_ticket("resume", "REOPENED"),
            "reject": make_ticket("reject", "NEW"),
            "terminal": make_ticket("terminal", "CLOSED"),
            "auto_close": make_ticket("autoclose", "RESOLVED"),
            "auto_close_fresh": make_ticket("autoclosefresh", "RESOLVED"),
        }
        session.add_all(tickets.values())
        await session.flush()

        assigned_keys = {
            "assigned",
            "request_info",
            "pending",
            "foreign_pending",
            "resolve",
            "resume",
            "terminal",
        }
        for key in assigned_keys:
            session.add(
                TicketAssignment(
                    ticket_id=tickets[key].ticket_id,
                    assignee_id=seeded_users["processor_user_id"],
                    assigned_by=seeded_users["admin_user_id"],
                    is_current=True,
                    reason="Phân công kiểm thử workflow",
                )
            )
        session.add(
            TicketAssignment(
                ticket_id=tickets["wrong_assignee"].ticket_id,
                assignee_id=other_processor.user_id,
                assigned_by=seeded_users["admin_user_id"],
                is_current=True,
                reason="Phân công cho processor khác",
            )
        )

        running_slas = {}
        for key in {"request_info", "resolve"}:
            running_slas[key] = TicketSLA(
                ticket_id=tickets[key].ticket_id,
                sla_policy_id=policy.sla_policy_id,
                sla_type="RESOLUTION",
                cycle_no=1,
                started_at=now - timedelta(hours=1),
                due_at=now + timedelta(hours=3),
                runtime_status="RUNNING",
            )
            session.add(running_slas[key])

        pending_sla = TicketSLA(
            ticket_id=tickets["pending"].ticket_id,
            sla_policy_id=policy.sla_policy_id,
            sla_type="RESOLUTION",
            cycle_no=1,
            started_at=now - timedelta(hours=1),
            due_at=now + timedelta(hours=3),
            paused_at=now - timedelta(minutes=10),
            runtime_status="PAUSED",
        )
        session.add(pending_sla)
        await session.flush()
        session.add(
            SLAPausePeriod(
                ticket_sla_id=pending_sla.ticket_sla_id,
                paused_at=now - timedelta(minutes=10),
                reason="Chờ bổ sung",
            )
        )

        completed_keys = {
            "close": now - timedelta(hours=1),
            "admin_close": now - timedelta(hours=1),
            "reopen": now - timedelta(hours=1),
            "expired": now - timedelta(hours=73),
            "resume": now - timedelta(hours=1),
            "auto_close": now - timedelta(hours=73),
            "auto_close_fresh": now - timedelta(hours=71),
        }
        for key, resolved_at in completed_keys.items():
            session.add_all(
                [
                    TicketResolution(
                        ticket_id=tickets[key].ticket_id,
                        resolved_by=seeded_users["processor_user_id"],
                        cycle_no=1,
                        resolution_note="Đã xử lý xong nguyên nhân sự cố",
                        resolved_at=resolved_at,
                    ),
                    TicketSLA(
                        ticket_id=tickets[key].ticket_id,
                        sla_policy_id=policy.sla_policy_id,
                        sla_type="RESOLUTION",
                        cycle_no=1,
                        started_at=resolved_at - timedelta(hours=1),
                        due_at=resolved_at + timedelta(hours=3),
                        completed_at=resolved_at,
                        runtime_status="COMPLETED",
                        result="MET",
                    ),
                ]
            )

        for sla_type in ("RESPONSE", "RESOLUTION"):
            session.add(
                TicketSLA(
                    ticket_id=tickets["reject"].ticket_id,
                    sla_policy_id=policy.sla_policy_id,
                    sla_type=sla_type,
                    cycle_no=1,
                    started_at=now - timedelta(minutes=10),
                    due_at=now + timedelta(hours=1),
                    runtime_status="RUNNING",
                )
            )
        await session.commit()

    return {
        **{key: ticket.ticket_id for key, ticket in tickets.items()},
        "pending_sla_id": pending_sla.ticket_sla_id,
        "request_info_sla_id": running_slas["request_info"].ticket_sla_id,
        "resolve_sla_id": running_slas["resolve"].ticket_sla_id,
        "other_requester_credentials": {
            "email": other_requester.email,
            "password": "CorrectPassword123!",
        },
        "other_processor_credentials": {
            "email": other_processor.email,
            "password": "CorrectPassword123!",
        },
    }


async def _transition_counts(session_factory, ticket_id):
    async with session_factory() as session:
        history = await session.scalar(
            select(func.count(TicketStatusHistory.history_id)).where(
                TicketStatusHistory.ticket_id == ticket_id
            )
        )
        audits = await session.scalar(
            select(func.count(AuditLog.audit_id)).where(AuditLog.ticket_id == ticket_id)
        )
        ticket = await session.get(Ticket, ticket_id)
        return int(history or 0), int(audits or 0), ticket.current_status_code


async def test_workflow_requires_authentication(client, workflow_data):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['assigned']}/start",
        json={},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_MISSING"


async def test_wf01_current_processor_starts_and_audits(
    client,
    processor_credentials,
    seeded_users,
    session_factory,
    workflow_data,
):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['assigned']}/start",
        headers=await _headers(client, processor_credentials),
        json={"reason": "Bắt đầu kiểm tra sự cố"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["code"] == "TICKET_STARTED"
    assert response.json()["data"]["status"]["status_code"] == "IN_PROGRESS"
    async with session_factory() as session:
        history = (
            await session.execute(
                select(TicketStatusHistory).where(
                    TicketStatusHistory.ticket_id == workflow_data["assigned"]
                )
            )
        ).scalar_one()
        audit = (
            await session.execute(
                select(AuditLog).where(AuditLog.ticket_id == workflow_data["assigned"])
            )
        ).scalar_one()
        assert history.changed_by == seeded_users["processor_user_id"]
        assert (history.from_status_code, history.to_status_code) == (
            "ASSIGNED",
            "IN_PROGRESS",
        )
        assert audit.action_code == "TICKET_STARTED"
        assert audit.new_value_json["workflow_code"] == "WF-01"


async def test_wf01_wrong_state_is_atomic(
    client,
    processor_credentials,
    session_factory,
    workflow_data,
):
    before = await _transition_counts(session_factory, workflow_data["request_info"])
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['request_info']}/start",
        headers=await _headers(client, processor_credentials),
        json={},
    )
    after = await _transition_counts(session_factory, workflow_data["request_info"])
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_STATE_TRANSITION"
    assert after == before


async def test_wf01_requires_current_assignment(
    client,
    processor_credentials,
    workflow_data,
):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['wrong_assignee']}/start",
        headers=await _headers(client, processor_credentials),
        json={},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ASSIGNMENT_REQUIRED"


async def test_wf02_creates_public_request_and_pauses_sla(
    client,
    processor_credentials,
    session_factory,
    workflow_data,
):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['request_info']}/request-info",
        headers=await _headers(client, processor_credentials),
        json={"content": "Vui lòng gửi ảnh thông báo lỗi chi tiết."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"]["status_code"] == "PENDING_INFO"
    async with session_factory() as session:
        comment = (
            await session.execute(
                select(Comment).where(Comment.ticket_id == workflow_data["request_info"])
            )
        ).scalar_one()
        sla = await session.get(TicketSLA, workflow_data["request_info_sla_id"])
        pause = (
            await session.execute(
                select(SLAPausePeriod).where(
                    SLAPausePeriod.ticket_sla_id == sla.ticket_sla_id
                )
            )
        ).scalar_one()
        assert (comment.visibility, comment.comment_type) == (
            "PUBLIC",
            "REQUEST_INFO",
        )
        assert sla.runtime_status == "PAUSED"
        assert sla.paused_at is not None
        assert pause.resumed_at is None


async def test_wf02_rejects_blank_content_without_mutation(
    client,
    processor_credentials,
    session_factory,
    workflow_data,
):
    before = await _transition_counts(session_factory, workflow_data["request_info"])
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['request_info']}/request-info",
        headers=await _headers(client, processor_credentials),
        json={"content": "   "},
    )
    after = await _transition_counts(session_factory, workflow_data["request_info"])
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert after == before


async def test_wf03_owner_provides_info_and_resumes_sla(
    client,
    credentials,
    session_factory,
    workflow_data,
):
    async with session_factory() as session:
        before = await session.get(TicketSLA, workflow_data["pending_sla_id"])
        due_before = before.due_at
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['pending']}/provide-info",
        headers=await _headers(client, credentials),
        json={"content": "Đây là ảnh và mô tả lỗi đã được bổ sung."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"]["status_code"] == "IN_PROGRESS"
    async with session_factory() as session:
        sla = await session.get(TicketSLA, workflow_data["pending_sla_id"])
        pause = (
            await session.execute(
                select(SLAPausePeriod).where(
                    SLAPausePeriod.ticket_sla_id == sla.ticket_sla_id
                )
            )
        ).scalar_one()
        assert sla.runtime_status == "RUNNING"
        assert sla.paused_at is None
        assert sla.total_paused_seconds >= 599
        assert sla.due_at == due_before
        assert pause.resumed_at is not None
        assert pause.duration_seconds == sla.total_paused_seconds


async def test_wf03_foreign_requester_is_denied(
    client,
    credentials,
    workflow_data,
):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['foreign_pending']}/provide-info",
        headers=await _headers(client, credentials),
        json={"content": "Không phải ticket của tôi."},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "TICKET_ACCESS_DENIED"


async def test_wf04_creates_resolution_and_completes_sla(
    client,
    processor_credentials,
    seeded_users,
    session_factory,
    workflow_data,
):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['resolve']}/resolve",
        headers=await _headers(client, processor_credentials),
        json={"resolution_note": "Đã khôi phục cấu hình kết nối dịch vụ."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"]["status_code"] == "RESOLVED"
    async with session_factory() as session:
        resolution = (
            await session.execute(
                select(TicketResolution).where(
                    TicketResolution.ticket_id == workflow_data["resolve"]
                )
            )
        ).scalar_one()
        sla = await session.get(TicketSLA, workflow_data["resolve_sla_id"])
        assert resolution.cycle_no == 1
        assert resolution.resolved_by == seeded_users["processor_user_id"]
        assert sla.runtime_status == "COMPLETED"
        assert sla.result == "MET"


async def test_wf04_missing_note_is_validation_error(
    client,
    processor_credentials,
    workflow_data,
):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['resolve']}/resolve",
        headers=await _headers(client, processor_credentials),
        json={"resolution_note": " "},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_wf05_owner_closes_resolved_ticket(
    client,
    credentials,
    session_factory,
    workflow_data,
):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['close']}/close",
        headers=await _headers(client, credentials),
        json={},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"]["status_code"] == "CLOSED"
    async with session_factory() as session:
        ticket = await session.get(Ticket, workflow_data["close"])
        assert ticket.closed_at is not None


async def test_wf05_admin_must_supply_reason(
    client,
    admin_credentials,
    workflow_data,
):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['admin_close']}/close",
        headers=await _headers(client, admin_credentials),
        json={},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "CLOSE_REASON_REQUIRED"


async def test_wf06_owner_reopens_within_72_hours_without_overwriting_cycle(
    client,
    credentials,
    session_factory,
    workflow_data,
):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['reopen']}/reopen",
        headers=await _headers(client, credentials),
        json={"reason": "Sự cố vẫn còn tái diễn sau xử lý."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"]["status_code"] == "REOPENED"
    async with session_factory() as session:
        resolution_count = await session.scalar(
            select(func.count(TicketResolution.resolution_id)).where(
                TicketResolution.ticket_id == workflow_data["reopen"]
            )
        )
        sla_count = await session.scalar(
            select(func.count(TicketSLA.ticket_sla_id)).where(
                TicketSLA.ticket_id == workflow_data["reopen"]
            )
        )
        assert resolution_count == 1
        assert sla_count == 1


async def test_wf06_expired_window_is_rejected_atomically(
    client,
    credentials,
    session_factory,
    workflow_data,
):
    before = await _transition_counts(session_factory, workflow_data["expired"])
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['expired']}/reopen",
        headers=await _headers(client, credentials),
        json={"reason": "Muốn mở lại sau khi đã quá hạn."},
    )
    after = await _transition_counts(session_factory, workflow_data["expired"])
    assert response.status_code == 409
    assert response.json()["code"] == "REOPEN_WINDOW_EXPIRED"
    assert after == before


async def test_wf07_assignee_creates_next_resolution_cycle(
    client,
    processor_credentials,
    session_factory,
    workflow_data,
):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['resume']}/resume",
        headers=await _headers(client, processor_credentials),
        json={"reason": "Tiếp tục xử lý sự cố tái diễn"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"]["status_code"] == "IN_PROGRESS"
    async with session_factory() as session:
        records = list(
            (
                await session.execute(
                    select(TicketSLA)
                    .where(
                        TicketSLA.ticket_id == workflow_data["resume"],
                        TicketSLA.sla_type == "RESOLUTION",
                    )
                    .order_by(TicketSLA.cycle_no)
                )
            ).scalars()
        )
        assert [record.cycle_no for record in records] == [1, 2]
        assert records[0].runtime_status == "COMPLETED"
        assert records[1].runtime_status == "RUNNING"


async def test_wf08_admin_rejects_new_and_marks_sla_not_applicable(
    client,
    admin_credentials,
    session_factory,
    workflow_data,
):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['reject']}/reject",
        headers=await _headers(client, admin_credentials),
        json={"reason": "Ticket trùng lặp với yêu cầu đã có."},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"]["status_code"] == "REJECTED"
    assert data["rejection_reason"] == "Ticket trùng lặp với yêu cầu đã có."
    async with session_factory() as session:
        slas = list(
            (
                await session.execute(
                    select(TicketSLA).where(
                        TicketSLA.ticket_id == workflow_data["reject"]
                    )
                )
            ).scalars()
        )
        assert all(record.runtime_status == "NOT_APPLICABLE" for record in slas)
        assert all(record.result == "NOT_APPLICABLE" for record in slas)


async def test_wf08_non_admin_is_forbidden_without_mutation(
    client,
    credentials,
    session_factory,
    workflow_data,
):
    before = await _transition_counts(session_factory, workflow_data["reject"])
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['reject']}/reject",
        headers=await _headers(client, credentials),
        json={"reason": "Không đủ quyền để từ chối ticket."},
    )
    after = await _transition_counts(session_factory, workflow_data["reject"])
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACTION"
    assert after == before


async def test_terminal_ticket_has_no_outgoing_transition(
    client,
    processor_credentials,
    workflow_data,
):
    response = await client.post(
        f"/api/v1/tickets/{workflow_data['terminal']}/start",
        headers=await _headers(client, processor_credentials),
        json={},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "TICKET_ALREADY_TERMINAL"


async def test_auto_close_is_expiry_scoped_and_idempotent(
    session_factory,
    workflow_data,
):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        first = await auto_close_expired_tickets(session, now=now)
        second = await auto_close_expired_tickets(session, now=now)
    # Both the dedicated auto-close fixture and the expired reopen fixture
    # are beyond the same 72-hour business window.
    assert first == 2
    assert second == 0
    async with session_factory() as session:
        expired = await session.get(Ticket, workflow_data["auto_close"])
        fresh = await session.get(Ticket, workflow_data["auto_close_fresh"])
        audit_count = await session.scalar(
            select(func.count(AuditLog.audit_id)).where(
                AuditLog.ticket_id == workflow_data["auto_close"]
            )
        )
        assert expired.current_status_code == "CLOSED"
        assert expired.closed_at.replace(tzinfo=timezone.utc) == now
        assert fresh.current_status_code == "RESOLVED"
        assert audit_count == 1
