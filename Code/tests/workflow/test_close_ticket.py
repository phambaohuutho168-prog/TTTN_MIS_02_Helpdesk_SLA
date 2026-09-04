from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.audit_log import AuditLog
from app.models.ticket import Ticket
from app.models.ticket_resolution import TicketResolution
from app.models.ticket_status import TicketStatus
from app.models.ticket_status_history import TicketStatusHistory
from app.services.workflow_service import auto_close_expired_tickets
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def close_ticket_data(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        session.add_all(
            [
                TicketStatus(status_code="IN_PROGRESS", status_name="Đang xử lý"),
                TicketStatus(status_code="RESOLVED", status_name="Đã xử lý"),
                TicketStatus(
                    status_code="CLOSED",
                    status_name="Đã đóng",
                    is_terminal=True,
                ),
            ]
        )

        def make_ticket(key: str, status: str, requester_id: int | None = None):
            return Ticket(
                ticket_code=f"TK-CV039-{key.upper()}",
                requester_id=requester_id or seeded_users["active_user_id"],
                category_id=seeded_users["active_category_id"],
                priority_id=seeded_users["active_priority_id"],
                current_status_code=status,
                title=f"CV039 {key}",
                description="Kiểm thử business rules đóng ticket.",
                created_at=now - timedelta(days=4),
                updated_at=now - timedelta(hours=1),
            )

        tickets = {
            "owner": make_ticket("OWNER", "RESOLVED"),
            "missing_solution": make_ticket("NO-SOLUTION", "RESOLVED"),
            "wrong_state": make_ticket("WRONG-STATE", "IN_PROGRESS"),
            "foreign": make_ticket(
                "FOREIGN",
                "RESOLVED",
                seeded_users["inactive_user_id"],
            ),
            "admin": make_ticket("ADMIN", "RESOLVED"),
            "processor": make_ticket("PROCESSOR", "RESOLVED"),
            "auto": make_ticket("AUTO", "RESOLVED"),
            "auto_missing_solution": make_ticket("AUTO-NO-SOLUTION", "RESOLVED"),
        }
        session.add_all(tickets.values())
        await session.flush()

        solution_times = {
            "owner": now - timedelta(hours=1),
            "foreign": now - timedelta(hours=1),
            "admin": now - timedelta(hours=1),
            "processor": now - timedelta(hours=1),
            "auto": now - timedelta(hours=73),
        }
        for key, resolved_at in solution_times.items():
            session.add(
                TicketResolution(
                    ticket_id=tickets[key].ticket_id,
                    resolved_by=seeded_users["processor_user_id"],
                    cycle_no=1,
                    resolution_note="Đã xác định nguyên nhân và khắc phục hoàn tất.",
                    resolved_at=resolved_at,
                )
            )
        await session.commit()

        return {
            **{key: ticket.ticket_id for key, ticket in tickets.items()},
            "now": now,
        }


async def _counts(session_factory, ticket_id: int) -> tuple[int, int]:
    async with session_factory() as session:
        histories = await session.scalar(
            select(func.count(TicketStatusHistory.history_id)).where(
                TicketStatusHistory.ticket_id == ticket_id
            )
        )
        audits = await session.scalar(
            select(func.count(AuditLog.audit_id)).where(
                AuditLog.ticket_id == ticket_id
            )
        )
    return int(histories or 0), int(audits or 0)


async def test_close_requires_authentication(client, close_ticket_data):
    response = await client.post(
        f"/api/v1/tickets/{close_ticket_data['owner']}/close",
        json={},
    )
    assert response.status_code == 401


async def test_owner_close_records_actor_time_history_and_audit(
    client,
    credentials,
    seeded_users,
    session_factory,
    close_ticket_data,
):
    response = await client.post(
        f"/api/v1/tickets/{close_ticket_data['owner']}/close",
        headers=await _headers(client, credentials),
        json={},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"]["status_code"] == "CLOSED"
    assert data["closed_at"] is not None
    assert data["closed_by"]["user_id"] == seeded_users["active_user_id"]

    async with session_factory() as session:
        ticket = await session.get(Ticket, close_ticket_data["owner"])
        history = (
            await session.execute(
                select(TicketStatusHistory).where(
                    TicketStatusHistory.ticket_id == close_ticket_data["owner"]
                )
            )
        ).scalar_one()
        audit = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.ticket_id == close_ticket_data["owner"]
                )
            )
        ).scalar_one()
        assert ticket.closed_by == seeded_users["active_user_id"]
        assert ticket.closed_at is not None
        assert history.changed_by == seeded_users["active_user_id"]
        assert audit.actor_user_id == seeded_users["active_user_id"]
        assert audit.action_code == "TICKET_CLOSED"
        assert audit.new_value_json["closed_by"] == seeded_users["active_user_id"]
        assert audit.new_value_json["closed_at"] == ticket.closed_at.replace(
            tzinfo=timezone.utc
        ).isoformat()


async def test_resolved_ticket_without_solution_cannot_close_atomically(
    client,
    credentials,
    session_factory,
    close_ticket_data,
):
    ticket_id = close_ticket_data["missing_solution"]
    before = await _counts(session_factory, ticket_id)
    response = await client.post(
        f"/api/v1/tickets/{ticket_id}/close",
        headers=await _headers(client, credentials),
        json={},
    )
    after = await _counts(session_factory, ticket_id)
    assert response.status_code == 409
    assert response.json()["code"] == "RESOLUTION_RECORD_MISSING"
    assert after == before
    async with session_factory() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.current_status_code == "RESOLVED"
        assert ticket.closed_at is None
        assert ticket.closed_by is None


async def test_only_resolved_ticket_can_close(
    client,
    credentials,
    close_ticket_data,
):
    response = await client.post(
        f"/api/v1/tickets/{close_ticket_data['wrong_state']}/close",
        headers=await _headers(client, credentials),
        json={},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_STATE_TRANSITION"


async def test_requester_cannot_close_foreign_ticket(
    client,
    credentials,
    close_ticket_data,
):
    response = await client.post(
        f"/api/v1/tickets/{close_ticket_data['foreign']}/close",
        headers=await _headers(client, credentials),
        json={},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "TICKET_ACCESS_DENIED"


async def test_processor_cannot_close_ticket(
    client,
    processor_credentials,
    close_ticket_data,
):
    response = await client.post(
        f"/api/v1/tickets/{close_ticket_data['processor']}/close",
        headers=await _headers(client, processor_credentials),
        json={},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACTION"


async def test_admin_reason_is_required_and_admin_is_recorded(
    client,
    admin_credentials,
    seeded_users,
    session_factory,
    close_ticket_data,
):
    url = f"/api/v1/tickets/{close_ticket_data['admin']}/close"
    headers = await _headers(client, admin_credentials)
    missing_reason = await client.post(url, headers=headers, json={})
    assert missing_reason.status_code == 422
    assert missing_reason.json()["code"] == "CLOSE_REASON_REQUIRED"

    response = await client.post(
        url,
        headers=headers,
        json={"reason": "Admin xác nhận kết quả xử lý hợp lệ."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["closed_by"]["user_id"] == seeded_users[
        "admin_user_id"
    ]
    async with session_factory() as session:
        ticket = await session.get(Ticket, close_ticket_data["admin"])
        assert ticket.closed_by == seeded_users["admin_user_id"]


async def test_closing_twice_is_rejected_without_duplicate_records(
    client,
    credentials,
    session_factory,
    close_ticket_data,
):
    ticket_id = close_ticket_data["owner"]
    headers = await _headers(client, credentials)
    first = await client.post(
        f"/api/v1/tickets/{ticket_id}/close",
        headers=headers,
        json={},
    )
    first_counts = await _counts(session_factory, ticket_id)
    second = await client.post(
        f"/api/v1/tickets/{ticket_id}/close",
        headers=headers,
        json={},
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "TICKET_ALREADY_TERMINAL"
    assert await _counts(session_factory, ticket_id) == first_counts == (1, 1)


async def test_auto_close_records_system_actor_and_skips_missing_solution(
    session_factory,
    close_ticket_data,
):
    async with session_factory() as session:
        closed = await auto_close_expired_tickets(
            session,
            now=close_ticket_data["now"],
        )
    assert closed == 1
    async with session_factory() as session:
        auto = await session.get(Ticket, close_ticket_data["auto"])
        missing = await session.get(
            Ticket,
            close_ticket_data["auto_missing_solution"],
        )
        audit = (
            await session.execute(
                select(AuditLog).where(AuditLog.ticket_id == auto.ticket_id)
            )
        ).scalar_one()
        assert auto.current_status_code == "CLOSED"
        assert auto.closed_at.replace(tzinfo=timezone.utc) == close_ticket_data["now"]
        assert auto.closed_by is None
        assert audit.actor_user_id is None
        assert audit.action_code == "TICKET_AUTO_CLOSED"
        assert audit.new_value_json["closed_by"] is None
        assert missing.current_status_code == "RESOLVED"
        assert missing.closed_at is None


async def test_database_rejects_closer_without_close_time(
    session_factory,
    seeded_users,
    close_ticket_data,
):
    async with session_factory() as session:
        ticket = await session.get(Ticket, close_ticket_data["missing_solution"])
        ticket.closed_by = seeded_users["admin_user_id"]
        with pytest.raises(IntegrityError):
            await session.flush()
