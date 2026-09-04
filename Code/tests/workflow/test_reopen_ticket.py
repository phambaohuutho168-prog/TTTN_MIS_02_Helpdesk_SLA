from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_resolution import TicketResolution
from app.models.ticket_sla import TicketSLA
from app.models.ticket_status import TicketStatus
from app.models.ticket_status_history import TicketStatusHistory
from app.repositories import user_repository
from app.schemas.workflow import ReopenRequest
from app.services import workflow_service
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def reopen_ticket_data(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        session.add_all(
            [
                TicketStatus(status_code="IN_PROGRESS", status_name="Đang xử lý"),
                TicketStatus(status_code="RESOLVED", status_name="Đã xử lý"),
                TicketStatus(status_code="REOPENED", status_name="Đã mở lại"),
                TicketStatus(
                    status_code="CLOSED",
                    status_name="Đã đóng",
                    is_terminal=True,
                ),
            ]
        )
        policy = SLAPolicy(
            priority_id=seeded_users["active_priority_id"],
            version_no=40,
            response_target_minutes=30,
            resolution_target_minutes=240,
            effective_from=now - timedelta(days=30),
            is_active=True,
        )
        session.add(policy)
        await session.flush()

        def make_ticket(
            key: str,
            status_code: str,
            *,
            requester_id: int | None = None,
        ) -> Ticket:
            return Ticket(
                ticket_code=f"TK-CV040-{key.upper()}",
                requester_id=requester_id or seeded_users["active_user_id"],
                category_id=seeded_users["active_category_id"],
                priority_id=seeded_users["active_priority_id"],
                current_status_code=status_code,
                title=f"CV040 {key}",
                description="Kiểm thử business rules mở lại ticket.",
                created_at=now - timedelta(days=5),
                updated_at=now - timedelta(hours=1),
                closed_at=(now - timedelta(hours=1) if status_code == "CLOSED" else None),
                closed_by=(
                    seeded_users["active_user_id"]
                    if status_code == "CLOSED"
                    else None
                ),
            )

        tickets = {
            "valid": make_ticket("VALID", "RESOLVED"),
            "foreign": make_ticket(
                "FOREIGN",
                "RESOLVED",
                requester_id=seeded_users["inactive_user_id"],
            ),
            "expired": make_ticket("EXPIRED", "RESOLVED"),
            "boundary": make_ticket("BOUNDARY", "RESOLVED"),
            "missing_resolution": make_ticket("NO-RESOLUTION", "RESOLVED"),
            "wrong_state": make_ticket("WRONG-STATE", "IN_PROGRESS"),
            "closed": make_ticket("CLOSED", "CLOSED"),
            "full_cycle": make_ticket("FULL-CYCLE", "RESOLVED"),
        }
        session.add_all(tickets.values())
        await session.flush()

        session.add(
            TicketAssignment(
                ticket_id=tickets["full_cycle"].ticket_id,
                assignee_id=seeded_users["processor_user_id"],
                assigned_by=seeded_users["admin_user_id"],
                is_current=True,
                reason="Phân công xử lý ticket sẽ mở lại",
            )
        )

        resolution_times = {
            "valid": now - timedelta(hours=1),
            "foreign": now - timedelta(hours=1),
            "expired": now - timedelta(hours=73),
            "boundary": now - timedelta(hours=72),
            "full_cycle": now - timedelta(hours=1),
        }
        for key, resolved_at in resolution_times.items():
            session.add_all(
                [
                    TicketResolution(
                        ticket_id=tickets[key].ticket_id,
                        resolved_by=seeded_users["processor_user_id"],
                        cycle_no=1,
                        resolution_note=(
                            "Đã hoàn tất cách xử lý của chu kỳ đầu tiên."
                        ),
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
        await session.commit()
        return {
            **{key: ticket.ticket_id for key, ticket in tickets.items()},
            "now": now,
        }


async def _mutation_counts(session_factory, ticket_id: int) -> tuple[int, int, int]:
    async with session_factory() as session:
        history_count = await session.scalar(
            select(func.count(TicketStatusHistory.history_id)).where(
                TicketStatusHistory.ticket_id == ticket_id
            )
        )
        audit_count = await session.scalar(
            select(func.count(AuditLog.audit_id)).where(
                AuditLog.ticket_id == ticket_id
            )
        )
        sla_count = await session.scalar(
            select(func.count(TicketSLA.ticket_sla_id)).where(
                TicketSLA.ticket_id == ticket_id
            )
        )
    return int(history_count or 0), int(audit_count or 0), int(sla_count or 0)


async def test_reopen_requires_authentication(client, reopen_ticket_data):
    response = await client.post(
        f"/api/v1/tickets/{reopen_ticket_data['valid']}/reopen",
        json={"reason": "Sự cố vẫn còn tái diễn."},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"reason": "   "},
        {"reason": "Ngắn"},
    ],
)
async def test_reopen_reason_is_required_and_has_minimum_length(
    client,
    credentials,
    reopen_ticket_data,
    payload,
):
    response = await client.post(
        f"/api/v1/tickets/{reopen_ticket_data['valid']}/reopen",
        headers=await _headers(client, credentials),
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_owner_reopens_and_preserves_completed_sla_cycle(
    client,
    credentials,
    seeded_users,
    session_factory,
    reopen_ticket_data,
):
    ticket_id = reopen_ticket_data["valid"]
    reason = "Sự cố vẫn tái diễn sau kết quả xử lý trước."
    response = await client.post(
        f"/api/v1/tickets/{ticket_id}/reopen",
        headers=await _headers(client, credentials),
        json={"reason": reason},
    )
    assert response.status_code == 200, response.text
    assert response.json()["code"] == "TICKET_REOPENED"
    assert response.json()["data"]["status"]["status_code"] == "REOPENED"

    async with session_factory() as session:
        ticket = await session.get(Ticket, ticket_id)
        history = (
            await session.execute(
                select(TicketStatusHistory).where(
                    TicketStatusHistory.ticket_id == ticket_id
                )
            )
        ).scalar_one()
        audit = (
            await session.execute(
                select(AuditLog).where(AuditLog.ticket_id == ticket_id)
            )
        ).scalar_one()
        slas = list(
            (
                await session.execute(
                    select(TicketSLA).where(TicketSLA.ticket_id == ticket_id)
                )
            ).scalars()
        )
        assert ticket.current_status_code == "REOPENED"
        assert history.changed_by == seeded_users["active_user_id"]
        assert history.reason == reason
        assert audit.action_code == "TICKET_REOPENED"
        assert audit.actor_user_id == seeded_users["active_user_id"]
        assert audit.reason == reason
        assert audit.new_value_json["source_resolution_cycle"] == 1
        assert audit.new_value_json["next_resolution_cycle"] == 2
        assert (
            audit.new_value_json["sla_action"]
            == "PRESERVE_COMPLETED_CYCLES_UNTIL_RESUME"
        )
        assert len(slas) == 1
        assert slas[0].runtime_status == "COMPLETED"
        assert slas[0].cycle_no == 1


async def test_requester_cannot_reopen_foreign_ticket(
    client,
    credentials,
    reopen_ticket_data,
):
    response = await client.post(
        f"/api/v1/tickets/{reopen_ticket_data['foreign']}/reopen",
        headers=await _headers(client, credentials),
        json={"reason": "Ticket này không thuộc người đang đăng nhập."},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "TICKET_ACCESS_DENIED"


@pytest.mark.parametrize("credential_fixture", ["processor_credentials", "admin_credentials"])
async def test_non_requester_roles_cannot_reopen_ticket(
    request,
    client,
    reopen_ticket_data,
    credential_fixture,
):
    credentials = request.getfixturevalue(credential_fixture)
    response = await client.post(
        f"/api/v1/tickets/{reopen_ticket_data['valid']}/reopen",
        headers=await _headers(client, credentials),
        json={"reason": "Vai trò này không được phép mở lại ticket."},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACTION"


async def test_ticket_must_be_resolved_to_reopen(
    client,
    credentials,
    reopen_ticket_data,
):
    response = await client.post(
        f"/api/v1/tickets/{reopen_ticket_data['wrong_state']}/reopen",
        headers=await _headers(client, credentials),
        json={"reason": "Yêu cầu mở lại từ trạng thái không hợp lệ."},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_STATE_TRANSITION"


async def test_closed_ticket_cannot_be_reopened(
    client,
    credentials,
    reopen_ticket_data,
):
    response = await client.post(
        f"/api/v1/tickets/{reopen_ticket_data['closed']}/reopen",
        headers=await _headers(client, credentials),
        json={"reason": "Ticket đã đóng không còn trong cửa sổ mở lại."},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "TICKET_ALREADY_TERMINAL"


async def test_expired_reopen_window_is_rejected_atomically(
    client,
    credentials,
    session_factory,
    reopen_ticket_data,
):
    ticket_id = reopen_ticket_data["expired"]
    before = await _mutation_counts(session_factory, ticket_id)
    response = await client.post(
        f"/api/v1/tickets/{ticket_id}/reopen",
        headers=await _headers(client, credentials),
        json={"reason": "Đã quá thời hạn nhưng vẫn thử mở lại."},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "REOPEN_WINDOW_EXPIRED"
    assert await _mutation_counts(session_factory, ticket_id) == before


async def test_missing_resolution_is_rejected_atomically(
    client,
    credentials,
    session_factory,
    reopen_ticket_data,
):
    ticket_id = reopen_ticket_data["missing_resolution"]
    before = await _mutation_counts(session_factory, ticket_id)
    response = await client.post(
        f"/api/v1/tickets/{ticket_id}/reopen",
        headers=await _headers(client, credentials),
        json={"reason": "Ticket thiếu bản ghi kết quả xử lý."},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "RESOLUTION_RECORD_MISSING"
    assert await _mutation_counts(session_factory, ticket_id) == before


async def test_exact_72_hour_boundary_is_allowed(
    session_factory,
    seeded_users,
    reopen_ticket_data,
):
    async with session_factory() as session:
        actor = await user_repository.get_user_by_id(
            session,
            seeded_users["active_user_id"],
        )
        result = await workflow_service.reopen_ticket(
            session,
            ticket_id=reopen_ticket_data["boundary"],
            actor=actor,
            payload=ReopenRequest(reason="Mở lại đúng tại biên thời gian 72 giờ."),
            ip_address="127.0.0.1",
            now=reopen_ticket_data["now"],
        )
        assert result.response_code == "TICKET_REOPENED"
        assert result.data.status.status_code == "REOPENED"


async def test_second_reopen_does_not_duplicate_history_or_audit(
    client,
    credentials,
    session_factory,
    reopen_ticket_data,
):
    ticket_id = reopen_ticket_data["valid"]
    headers = await _headers(client, credentials)
    first = await client.post(
        f"/api/v1/tickets/{ticket_id}/reopen",
        headers=headers,
        json={"reason": "Sự cố vẫn xảy ra sau lần xử lý trước."},
    )
    first_counts = await _mutation_counts(session_factory, ticket_id)
    second = await client.post(
        f"/api/v1/tickets/{ticket_id}/reopen",
        headers=headers,
        json={"reason": "Thử gửi lại cùng yêu cầu mở lại lần nữa."},
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "INVALID_STATE_TRANSITION"
    assert await _mutation_counts(session_factory, ticket_id) == first_counts


async def test_resume_creates_next_sla_cycle_and_detailed_audit(
    client,
    credentials,
    processor_credentials,
    session_factory,
    reopen_ticket_data,
):
    ticket_id = reopen_ticket_data["full_cycle"]
    reopened = await client.post(
        f"/api/v1/tickets/{ticket_id}/reopen",
        headers=await _headers(client, credentials),
        json={"reason": "Lỗi tái diễn và cần tiếp tục xử lý."},
    )
    resumed = await client.post(
        f"/api/v1/tickets/{ticket_id}/resume",
        headers=await _headers(client, processor_credentials),
        json={"reason": "Tiếp nhận lại ticket đã được mở lại."},
    )
    assert reopened.status_code == 200, reopened.text
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["data"]["status"]["status_code"] == "IN_PROGRESS"

    async with session_factory() as session:
        slas = list(
            (
                await session.execute(
                    select(TicketSLA)
                    .where(
                        TicketSLA.ticket_id == ticket_id,
                        TicketSLA.sla_type == "RESOLUTION",
                    )
                    .order_by(TicketSLA.cycle_no)
                )
            ).scalars()
        )
        audits = list(
            (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.ticket_id == ticket_id)
                    .order_by(AuditLog.audit_id)
                )
            ).scalars()
        )
        assert [sla.cycle_no for sla in slas] == [1, 2]
        assert slas[0].runtime_status == "COMPLETED"
        assert slas[1].runtime_status == "RUNNING"
        actions = [audit.action_code for audit in audits]
        assert actions == [
            "TICKET_REOPENED",
            "SLA_RUNTIME_CREATED",
            "TICKET_RESUMED",
        ]
        sla_audit = audits[1]
        resume_audit = audits[2]
        assert sla_audit.entity_id == slas[1].ticket_sla_id
        assert sla_audit.new_value_json["cycle_no"] == 2
        assert resume_audit.new_value_json["resolution_cycle"] == 2
        assert resume_audit.new_value_json["ticket_sla_id"] == slas[1].ticket_sla_id
