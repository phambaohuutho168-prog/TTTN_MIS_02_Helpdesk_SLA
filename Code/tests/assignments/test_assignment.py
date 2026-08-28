from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_status import TicketStatus
from app.models.ticket_status_history import TicketStatusHistory
from app.models.user import User
from app.models.user_role import UserRole
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def assignment_data(session_factory, seeded_users):
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
                    status_code="CLOSED",
                    status_name="Đã đóng",
                    is_terminal=True,
                ),
            ]
        )
        second_processor = User(
            email="processor.two@example.com",
            full_name="Processor Two",
            password_hash=hash_password("CorrectPassword123!"),
            department_id=seeded_users["department_id"],
            is_active=True,
        )
        inactive_processor = User(
            email="processor.inactive@example.com",
            full_name="Processor Inactive",
            password_hash=hash_password("CorrectPassword123!"),
            department_id=seeded_users["department_id"],
            is_active=False,
        )
        session.add_all([second_processor, inactive_processor])
        await session.flush()
        session.add_all(
            [
                UserRole(
                    user_id=second_processor.user_id,
                    role_id=seeded_users["processor_role_id"],
                    assigned_by=seeded_users["admin_user_id"],
                ),
                UserRole(
                    user_id=inactive_processor.user_id,
                    role_id=seeded_users["processor_role_id"],
                    assigned_by=seeded_users["admin_user_id"],
                ),
            ]
        )
        new_ticket = Ticket(
            ticket_code="TK-20260828-ASN00000001",
            requester_id=seeded_users["active_user_id"],
            category_id=seeded_users["active_category_id"],
            priority_id=seeded_users["active_priority_id"],
            current_status_code="NEW",
            title="Ticket chờ phân công",
            description="Dữ liệu kiểm thử phân công lần đầu.",
        )
        active_ticket = Ticket(
            ticket_code="TK-20260828-ASN00000002",
            requester_id=seeded_users["active_user_id"],
            category_id=seeded_users["active_category_id"],
            priority_id=seeded_users["active_priority_id"],
            current_status_code="IN_PROGRESS",
            title="Ticket đang được xử lý",
            description="Dữ liệu kiểm thử tái phân công.",
        )
        closed_ticket = Ticket(
            ticket_code="TK-20260828-ASN00000003",
            requester_id=seeded_users["active_user_id"],
            category_id=seeded_users["active_category_id"],
            priority_id=seeded_users["active_priority_id"],
            current_status_code="CLOSED",
            title="Ticket đã đóng",
            description="Không được phép phân công.",
            closed_at=datetime.now(timezone.utc),
        )
        session.add_all([new_ticket, active_ticket, closed_ticket])
        await session.flush()
        current = TicketAssignment(
            ticket_id=active_ticket.ticket_id,
            assignee_id=seeded_users["processor_user_id"],
            assigned_by=seeded_users["admin_user_id"],
            is_current=True,
            reason="Phân công ban đầu",
        )
        session.add(current)
        await session.commit()

    return {
        "new_ticket_id": new_ticket.ticket_id,
        "active_ticket_id": active_ticket.ticket_id,
        "closed_ticket_id": closed_ticket.ticket_id,
        "current_assignment_id": current.assignment_id,
        "second_processor_id": second_processor.user_id,
        "inactive_processor_id": inactive_processor.user_id,
    }


async def _counts(session_factory, ticket_id):
    async with session_factory() as session:
        assignment_count = await session.scalar(
            select(func.count(TicketAssignment.assignment_id)).where(
                TicketAssignment.ticket_id == ticket_id
            )
        )
        audit_count = await session.scalar(
            select(func.count(AuditLog.audit_id)).where(AuditLog.ticket_id == ticket_id)
        )
        ticket = await session.get(Ticket, ticket_id)
        return int(assignment_count or 0), int(audit_count or 0), ticket.current_status_code


async def test_assignment_requires_authentication(client, assignment_data):
    response = await client.put(
        f"/api/v1/tickets/{assignment_data['new_ticket_id']}/assignment",
        json={"assignee_id": assignment_data["second_processor_id"]},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_MISSING"


async def test_requester_cannot_assign_and_does_not_mutate(
    client,
    credentials,
    session_factory,
    assignment_data,
):
    before = await _counts(session_factory, assignment_data["new_ticket_id"])
    response = await client.put(
        f"/api/v1/tickets/{assignment_data['new_ticket_id']}/assignment",
        headers=await _headers(client, credentials),
        json={"assignee_id": assignment_data["second_processor_id"]},
    )
    after = await _counts(session_factory, assignment_data["new_ticket_id"])
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACTION"
    assert after == before


async def test_processor_cannot_assign_and_does_not_mutate(
    client,
    processor_credentials,
    session_factory,
    assignment_data,
):
    before = await _counts(session_factory, assignment_data["active_ticket_id"])
    response = await client.put(
        f"/api/v1/tickets/{assignment_data['active_ticket_id']}/assignment",
        headers=await _headers(client, processor_credentials),
        json={
            "assignee_id": assignment_data["second_processor_id"],
            "reason": "Không đủ quyền",
        },
    )
    after = await _counts(session_factory, assignment_data["active_ticket_id"])
    assert response.status_code == 403
    assert after == before


async def test_admin_initial_assignment_changes_status_history_and_audit(
    client,
    admin_credentials,
    seeded_users,
    session_factory,
    assignment_data,
):
    response = await client.put(
        f"/api/v1/tickets/{assignment_data['new_ticket_id']}/assignment",
        headers=await _headers(client, admin_credentials),
        json={"assignee_id": assignment_data["second_processor_id"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == "TICKET_ASSIGNED"
    assignment = body["data"]
    assert assignment["assignee"]["user_id"] == assignment_data["second_processor_id"]
    assert assignment["assigned_by"]["user_id"] == seeded_users["admin_user_id"]
    assert assignment["is_current"] is True

    async with session_factory() as session:
        ticket = await session.get(Ticket, assignment_data["new_ticket_id"])
        histories = list(
            (
                await session.execute(
                    select(TicketStatusHistory).where(
                        TicketStatusHistory.ticket_id == ticket.ticket_id
                    )
                )
            ).scalars()
        )
        audit = (
            await session.execute(
                select(AuditLog).where(AuditLog.ticket_id == ticket.ticket_id)
            )
        ).scalar_one()
        assert ticket.current_status_code == "ASSIGNED"
        assert len(histories) == 1
        assert histories[0].from_status_code == "NEW"
        assert histories[0].to_status_code == "ASSIGNED"
        assert histories[0].changed_by == seeded_users["admin_user_id"]
        assert audit.action_code == "TICKET_ASSIGNED"
        assert audit.actor_user_id == seeded_users["admin_user_id"]
        assert audit.old_value_json["assignee_id"] is None
        assert audit.new_value_json["assignee_id"] == assignment_data["second_processor_id"]


async def test_admin_reassigns_closes_old_row_preserves_status_and_audits_reason(
    client,
    admin_credentials,
    seeded_users,
    session_factory,
    assignment_data,
):
    response = await client.put(
        f"/api/v1/tickets/{assignment_data['active_ticket_id']}/assignment",
        headers=await _headers(client, admin_credentials),
        json={
            "assignee_id": assignment_data["second_processor_id"],
            "reason": "  Điều chuyển do chuyên môn phù hợp hơn  ",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["code"] == "TICKET_REASSIGNED"
    assert response.json()["data"]["reason"] == "Điều chuyển do chuyên môn phù hợp hơn"

    async with session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(TicketAssignment)
                    .where(TicketAssignment.ticket_id == assignment_data["active_ticket_id"])
                    .order_by(TicketAssignment.assignment_id)
                )
            ).scalars()
        )
        ticket = await session.get(Ticket, assignment_data["active_ticket_id"])
        audit = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.ticket_id == assignment_data["active_ticket_id"]
                )
            )
        ).scalar_one()
        assert len(rows) == 2
        assert rows[0].is_current is False and rows[0].ended_at is not None
        assert rows[1].is_current is True and rows[1].ended_at is None
        assert rows[1].assignee_id == assignment_data["second_processor_id"]
        assert ticket.current_status_code == "IN_PROGRESS"
        assert audit.action_code == "TICKET_REASSIGNED"
        assert audit.old_value_json["assignee_id"] == seeded_users["processor_user_id"]
        assert audit.new_value_json["assignee_id"] == assignment_data["second_processor_id"]
        assert audit.reason == "Điều chuyển do chuyên môn phù hợp hơn"


async def test_reassignment_requires_nonblank_reason(
    client,
    admin_credentials,
    session_factory,
    assignment_data,
):
    before = await _counts(session_factory, assignment_data["active_ticket_id"])
    response = await client.put(
        f"/api/v1/tickets/{assignment_data['active_ticket_id']}/assignment",
        headers=await _headers(client, admin_credentials),
        json={"assignee_id": assignment_data["second_processor_id"], "reason": "   "},
    )
    after = await _counts(session_factory, assignment_data["active_ticket_id"])
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert after == before


async def test_same_assignee_is_rejected_without_mutation(
    client,
    admin_credentials,
    seeded_users,
    session_factory,
    assignment_data,
):
    before = await _counts(session_factory, assignment_data["active_ticket_id"])
    response = await client.put(
        f"/api/v1/tickets/{assignment_data['active_ticket_id']}/assignment",
        headers=await _headers(client, admin_credentials),
        json={
            "assignee_id": seeded_users["processor_user_id"],
            "reason": "Không làm thay đổi người xử lý",
        },
    )
    after = await _counts(session_factory, assignment_data["active_ticket_id"])
    assert response.status_code == 409
    assert response.json()["code"] == "ASSIGNMENT_UNCHANGED"
    assert after == before


async def test_inactive_processor_is_rejected(
    client,
    admin_credentials,
    assignment_data,
):
    response = await client.put(
        f"/api/v1/tickets/{assignment_data['new_ticket_id']}/assignment",
        headers=await _headers(client, admin_credentials),
        json={"assignee_id": assignment_data["inactive_processor_id"]},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ASSIGNEE_INACTIVE"


async def test_non_processor_and_missing_user_are_invalid(
    client,
    admin_credentials,
    seeded_users,
    assignment_data,
):
    headers = await _headers(client, admin_credentials)
    for assignee_id in [seeded_users["active_user_id"], 999999]:
        response = await client.put(
            f"/api/v1/tickets/{assignment_data['new_ticket_id']}/assignment",
            headers=headers,
            json={"assignee_id": assignee_id},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "ASSIGNEE_INVALID"


async def test_terminal_ticket_cannot_be_assigned(
    client,
    admin_credentials,
    assignment_data,
):
    response = await client.put(
        f"/api/v1/tickets/{assignment_data['closed_ticket_id']}/assignment",
        headers=await _headers(client, admin_credentials),
        json={"assignee_id": assignment_data["second_processor_id"]},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "TICKET_ALREADY_TERMINAL"


async def test_missing_assigned_status_reports_configuration_error(
    client,
    admin_credentials,
    session_factory,
    assignment_data,
):
    async with session_factory() as session:
        status_row = await session.get(TicketStatus, "ASSIGNED")
        await session.delete(status_row)
        await session.commit()
    response = await client.put(
        f"/api/v1/tickets/{assignment_data['new_ticket_id']}/assignment",
        headers=await _headers(client, admin_credentials),
        json={"assignee_id": assignment_data["second_processor_id"]},
    )
    assert response.status_code == 500
    assert response.json()["code"] == "TICKET_STATUS_CONFIGURATION_ERROR"


async def test_missing_ticket_returns_domain_404(
    client,
    admin_credentials,
    assignment_data,
):
    response = await client.put(
        "/api/v1/tickets/999999/assignment",
        headers=await _headers(client, admin_credentials),
        json={"assignee_id": assignment_data["second_processor_id"]},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "TICKET_NOT_FOUND"


async def test_assignment_payload_rejects_unknown_and_invalid_fields(
    client,
    admin_credentials,
    assignment_data,
):
    headers = await _headers(client, admin_credentials)
    invalid_payloads = [
        {"assignee_id": 0},
        {"assignee_id": assignment_data["second_processor_id"], "is_current": True},
        {"assignee_id": assignment_data["second_processor_id"], "reason": "x" * 1001},
    ]
    for payload in invalid_payloads:
        response = await client.put(
            f"/api/v1/tickets/{assignment_data['new_ticket_id']}/assignment",
            headers=headers,
            json=payload,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"
