from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.core.sla import reached_sla_thresholds
from app.models.audit_log import AuditLog
from app.models.notification import Notification
from app.models.priority import Priority
from app.models.role import Role
from app.models.sla_event import SLAEvent
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_sla import TicketSLA
from app.models.ticket_status import TicketStatus
from app.models.user import User
from app.models.user_role import UserRole
from app.services.escalation_service import process_sla_escalations
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.mark.parametrize(
    ("progress", "remaining", "priority_level", "expected"),
    [
        (79.99, 1200, 2, []),
        (80, 1200, 2, ["WARNING"]),
        (100, 0, 2, ["WARNING"]),
        (100.01, -1, 2, ["WARNING", "OVERDUE"]),
        (149.99, -1, 2, ["WARNING", "OVERDUE"]),
        (150, -1, 2, ["WARNING", "OVERDUE", "ESCALATED"]),
        (100.01, -1, 1, ["WARNING", "OVERDUE", "ESCALATED"]),
    ],
)
def test_sla_threshold_business_rules(
    progress,
    remaining,
    priority_level,
    expected,
):
    events = reached_sla_thresholds(
        progress_percent=progress,
        remaining_seconds=remaining,
        warning_percent=80,
        escalation_percent=150,
        priority_level=priority_level,
    )
    assert [event.event_type for event in events] == expected


def test_sla_threshold_configuration_is_validated():
    with pytest.raises(ValueError):
        reached_sla_thresholds(
            progress_percent=90,
            remaining_seconds=60,
            warning_percent=100,
            escalation_percent=150,
            priority_level=2,
        )
    with pytest.raises(ValueError):
        reached_sla_thresholds(
            progress_percent=110,
            remaining_seconds=-1,
            warning_percent=80,
            escalation_percent=99,
            priority_level=2,
        )


@pytest.fixture
async def escalation_data(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        p1 = Priority(
            priority_code="P1",
            priority_level=1,
            priority_name="Khẩn cấp",
            is_active=True,
        )
        p2 = Priority(
            priority_code="P2",
            priority_level=2,
            priority_name="Cao",
            is_active=True,
        )
        other_processor = User(
            email="escalation.processor@example.com",
            full_name="Escalation Processor",
            password_hash=hash_password("CorrectPassword123!"),
            department_id=seeded_users["department_id"],
            is_active=True,
        )
        session.add_all(
            [
                p1,
                p2,
                other_processor,
                TicketStatus(
                    status_code="ASSIGNED",
                    status_name="Đã phân công",
                    is_terminal=False,
                ),
            ]
        )
        await session.flush()
        processor_role_id = await session.scalar(
            select(Role.role_id).where(Role.role_code == "PROCESSOR")
        )
        session.add(
            UserRole(
                user_id=other_processor.user_id,
                role_id=processor_role_id,
            )
        )
        policies = {}
        for priority in (p1, p2):
            policy = SLAPolicy(
                priority_id=priority.priority_id,
                version_no=1,
                response_target_minutes=100,
                resolution_target_minutes=200,
                warning_percent=80,
                escalation_percent=150,
                effective_from=now - timedelta(days=30),
                is_active=True,
            )
            policies[priority.priority_code] = policy
            session.add(policy)
        await session.flush()

        specs = [
            ("P2-160", p2, policies["P2"], 160, "RUNNING", seeded_users["processor_user_id"]),
            ("P1-101", p1, policies["P1"], 101, "RUNNING", other_processor.user_id),
            ("P2-085", p2, policies["P2"], 85, "RUNNING", seeded_users["processor_user_id"]),
            ("P2-PAUSED", p2, policies["P2"], 160, "PAUSED", seeded_users["processor_user_id"]),
        ]
        tickets = {}
        for code, priority, policy, progress, runtime_status, assignee_id in specs:
            ticket = Ticket(
                ticket_code=f"TK-ESC-{code}",
                requester_id=seeded_users["active_user_id"],
                category_id=seeded_users["active_category_id"],
                priority_id=priority.priority_id,
                current_status_code="ASSIGNED",
                title=f"Escalation {code}",
                description="Ticket phục vụ kiểm thử escalation SLA.",
            )
            session.add(ticket)
            await session.flush()
            session.add(
                TicketAssignment(
                    ticket_id=ticket.ticket_id,
                    assignee_id=assignee_id,
                    assigned_by=seeded_users["admin_user_id"],
                    assigned_at=now - timedelta(hours=4),
                    is_current=True,
                    reason="Phân công kiểm thử escalation",
                )
            )
            started_at = now - timedelta(minutes=progress)
            session.add(
                TicketSLA(
                    ticket_id=ticket.ticket_id,
                    sla_policy_id=policy.sla_policy_id,
                    sla_type=(
                        "RESOLUTION" if runtime_status == "PAUSED" else "RESPONSE"
                    ),
                    cycle_no=1,
                    started_at=started_at,
                    due_at=started_at + timedelta(minutes=100),
                    paused_at=(now if runtime_status == "PAUSED" else None),
                    runtime_status=runtime_status,
                    total_paused_seconds=0,
                )
            )
            tickets[code] = ticket.ticket_id
        await session.commit()
    return {
        "now": now,
        "tickets": tickets,
        "other_processor_id": other_processor.user_id,
    }


async def test_worker_creates_warning_overdue_and_priority_escalation(
    session_factory,
    seeded_users,
    escalation_data,
):
    async with session_factory() as session:
        result = await process_sla_escalations(
            session,
            now=escalation_data["now"],
        )
    assert result.scanned_runtimes == 3
    assert result.created_events == 7
    assert result.created_notifications == 14
    assert result.skipped_without_recipient == 0

    async with session_factory() as session:
        events = (
            await session.execute(
                select(SLAEvent, Ticket.ticket_code)
                .join(TicketSLA, TicketSLA.ticket_sla_id == SLAEvent.ticket_sla_id)
                .join(Ticket, Ticket.ticket_id == TicketSLA.ticket_id)
                .order_by(Ticket.ticket_code, SLAEvent.threshold_percent)
            )
        ).all()
        by_ticket = {}
        for event, ticket_code in events:
            by_ticket.setdefault(ticket_code, []).append(
                (event.event_type, event.threshold_percent)
            )

    assert by_ticket["TK-ESC-P1-101"] == [
        ("WARNING", 80),
        ("OVERDUE", 100),
        ("ESCALATED", 100),
    ]
    assert by_ticket["TK-ESC-P2-160"] == [
        ("WARNING", 80),
        ("OVERDUE", 100),
        ("ESCALATED", 150),
    ]
    assert by_ticket["TK-ESC-P2-085"] == [("WARNING", 80)]
    assert "TK-ESC-P2-PAUSED" not in by_ticket


async def test_worker_is_idempotent_and_does_not_reassign_ticket(
    session_factory,
    escalation_data,
):
    async with session_factory() as session:
        initial_assignments = await session.scalar(
            select(func.count(TicketAssignment.assignment_id))
        )
        first = await process_sla_escalations(
            session,
            now=escalation_data["now"],
        )
    async with session_factory() as session:
        second = await process_sla_escalations(
            session,
            now=escalation_data["now"] + timedelta(minutes=1),
        )
        counts = {
            "events": await session.scalar(select(func.count(SLAEvent.sla_event_id))),
            "notifications": await session.scalar(
                select(func.count(Notification.notification_id))
            ),
            "audits": await session.scalar(
                select(func.count(AuditLog.audit_id)).where(
                    AuditLog.entity_type == "SLA_EVENT"
                )
            ),
            "assignments": await session.scalar(
                select(func.count(TicketAssignment.assignment_id))
            ),
        }

    assert first.created_events == 7
    assert second.created_events == 0
    assert second.created_notifications == 0
    assert counts == {
        "events": 7,
        "notifications": 14,
        "audits": 7,
        "assignments": initial_assignments,
    }


async def test_notifications_target_current_assignee_and_active_admin(
    session_factory,
    seeded_users,
    escalation_data,
):
    async with session_factory() as session:
        await process_sla_escalations(session, now=escalation_data["now"])
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(Ticket.ticket_code, Notification.recipient_id)
                .join(Notification, Notification.ticket_id == Ticket.ticket_id)
                .order_by(Ticket.ticket_code, Notification.recipient_id)
            )
        ).all()
    recipients = {}
    for ticket_code, recipient_id in rows:
        recipients.setdefault(ticket_code, set()).add(recipient_id)

    assert recipients["TK-ESC-P2-160"] == {
        seeded_users["processor_user_id"],
        seeded_users["admin_user_id"],
    }
    assert recipients["TK-ESC-P1-101"] == {
        escalation_data["other_processor_id"],
        seeded_users["admin_user_id"],
    }
    assert "TK-ESC-P2-PAUSED" not in recipients


async def test_worker_writes_append_only_audit_context(
    session_factory,
    escalation_data,
):
    async with session_factory() as session:
        await process_sla_escalations(session, now=escalation_data["now"])
    async with session_factory() as session:
        audits = list(
            (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.entity_type == "SLA_EVENT")
                    .order_by(AuditLog.audit_id)
                )
            )
            .scalars()
            .all()
        )
    assert len(audits) == 7
    assert {audit.action_code for audit in audits} == {
        "SLA_WARNING_TRIGGERED",
        "SLA_OVERDUE_TRIGGERED",
        "SLA_ESCALATED_TRIGGERED",
    }
    assert all(audit.actor_user_id is None for audit in audits)
    assert all(audit.ticket_id is not None for audit in audits)
    assert all(audit.new_value_json["recipient_ids"] for audit in audits)


async def test_sla_breaches_requires_processor_or_admin(
    client,
    credentials,
    escalation_data,
):
    unauthenticated = await client.get("/api/v1/sla/breaches")
    requester = await client.get(
        "/api/v1/sla/breaches",
        headers=await _headers(client, credentials),
    )
    assert unauthenticated.status_code == 401
    assert requester.status_code == 403


async def test_processor_sees_only_currently_assigned_sla_events(
    client,
    processor_credentials,
    session_factory,
    escalation_data,
):
    async with session_factory() as session:
        await process_sla_escalations(session, now=escalation_data["now"])
    response = await client.get(
        "/api/v1/sla/breaches?page_size=100",
        headers=await _headers(client, processor_credentials),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == "SLA_EVENTS_LISTED"
    assert body["data"]["total"] == 4
    assert {
        item["ticket"]["ticket_code"] for item in body["data"]["items"]
    } == {"TK-ESC-P2-160", "TK-ESC-P2-085"}
    assert all(item["recipients"] for item in body["data"]["items"])


async def test_admin_filters_and_paginates_escalations(
    client,
    admin_credentials,
    session_factory,
    escalation_data,
):
    async with session_factory() as session:
        await process_sla_escalations(session, now=escalation_data["now"])
    headers = await _headers(client, admin_credentials)
    response = await client.get(
        "/api/v1/sla/breaches?state=ESCALATED&page=1&page_size=1",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total"] == 2
    assert data["total_pages"] == 2
    assert len(data["items"]) == 1
    assert data["items"][0]["state"] == "ESCALATED"
    assert data["items"][0]["current_assignee"] is not None

    invalid = await client.get(
        "/api/v1/sla/breaches?state=UNKNOWN",
        headers=headers,
    )
    assert invalid.status_code == 422
