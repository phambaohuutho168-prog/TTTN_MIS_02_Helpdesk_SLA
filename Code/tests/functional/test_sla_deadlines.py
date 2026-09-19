"""CV048 - SLA Test cho ticket sắp hạn và quá hạn.

Kiểm tra xuyên suốt deadline, WARNING, OVERDUE, ESCALATED, notification,
audit log và kết quả BREACHED của SLA phản hồi.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.notification import Notification
from app.models.sla_event import SLAEvent
from app.models.sla_policy import SLAPolicy
from app.models.ticket_sla import TicketSLA
from app.models.ticket_status import TicketStatus
from app.services.escalation_service import process_sla_escalations
from tests.conftest import login_client


async def _auth_headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def cv048_runtime_configuration(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        session.add(
            TicketStatus(
                status_code="ASSIGNED",
                status_name="Đã phân công",
                is_terminal=False,
            )
        )
        session.add(
            SLAPolicy(
                priority_id=seeded_users["active_priority_id"],
                version_no=1,
                response_target_minutes=100,
                resolution_target_minutes=200,
                warning_percent=80,
                escalation_percent=150,
                effective_from=now - timedelta(days=1),
                is_active=True,
            )
        )
        await session.commit()
    return now


async def _create_and_assign_ticket(
    client,
    *,
    requester_headers,
    admin_headers,
    seeded_users,
    title,
):
    created = await client.post(
        "/api/v1/tickets",
        headers=requester_headers,
        json={
            "title": title,
            "description": "Ticket dùng để kiểm thử deadline và escalation SLA.",
            "category_id": seeded_users["active_category_id"],
            "priority_id": seeded_users["active_priority_id"],
        },
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["data"]["ticket_id"]

    assigned = await client.put(
        f"/api/v1/tickets/{ticket_id}/assignment",
        headers=admin_headers,
        json={
            "assignee_id": seeded_users["processor_user_id"],
            "reason": "Phân công kiểm thử CV048",
        },
    )
    assert assigned.status_code == 200, assigned.text
    return ticket_id


async def test_cv048_near_due_overdue_escalation_and_breach(
    client,
    credentials,
    admin_credentials,
    processor_credentials,
    seeded_users,
    session_factory,
    cv048_runtime_configuration,
):
    test_now = cv048_runtime_configuration
    requester_headers = await _auth_headers(client, credentials)
    admin_headers = await _auth_headers(client, admin_credentials)
    processor_headers = await _auth_headers(client, processor_credentials)

    near_due_ticket_id = await _create_and_assign_ticket(
        client,
        requester_headers=requester_headers,
        admin_headers=admin_headers,
        seeded_users=seeded_users,
        title="CV048 - Ticket sắp hết SLA phản hồi",
    )
    overdue_ticket_id = await _create_and_assign_ticket(
        client,
        requester_headers=requester_headers,
        admin_headers=admin_headers,
        seeded_users=seeded_users,
        title="CV048 - Ticket đã quá SLA phản hồi",
    )

    # SLA-FT-01 - Đặt runtime tại 85% và 160% của target 100 phút.
    async with session_factory() as session:
        runtimes = list(
            (
                await session.execute(
                    select(TicketSLA).where(
                        TicketSLA.ticket_id.in_(
                            [near_due_ticket_id, overdue_ticket_id]
                        ),
                        TicketSLA.sla_type == "RESPONSE",
                    )
                )
            )
            .scalars()
            .all()
        )
        by_ticket = {runtime.ticket_id: runtime for runtime in runtimes}
        near_due_runtime = by_ticket[near_due_ticket_id]
        overdue_runtime = by_ticket[overdue_ticket_id]

        near_due_runtime.started_at = test_now - timedelta(minutes=85)
        near_due_runtime.due_at = near_due_runtime.started_at + timedelta(minutes=100)
        overdue_runtime.started_at = test_now - timedelta(minutes=160)
        overdue_runtime.due_at = overdue_runtime.started_at + timedelta(minutes=100)
        await session.commit()

        assert near_due_runtime.due_at - near_due_runtime.started_at == timedelta(
            minutes=100
        )
        assert overdue_runtime.due_at - overdue_runtime.started_at == timedelta(
            minutes=100
        )

    # SLA-FT-02 - Worker ghi WARNING cho ticket 85%; ticket 160% có đủ 3 mốc.
    async with session_factory() as session:
        first_run = await process_sla_escalations(session, now=test_now)
    assert first_run.scanned_runtimes == 4
    assert first_run.created_events == 4
    assert first_run.created_notifications == 8
    assert first_run.skipped_without_recipient == 0

    async with session_factory() as session:
        event_rows = list(
            (
                await session.execute(
                    select(SLAEvent, TicketSLA.ticket_id)
                    .join(
                        TicketSLA,
                        TicketSLA.ticket_sla_id == SLAEvent.ticket_sla_id,
                    )
                    .where(
                        TicketSLA.ticket_id.in_(
                            [near_due_ticket_id, overdue_ticket_id]
                        )
                    )
                )
            ).all()
        )
        events_by_ticket = {}
        for event, ticket_id in event_rows:
            events_by_ticket.setdefault(ticket_id, set()).add(
                (event.event_type, event.threshold_percent)
            )

        notification_rows = list(
            (
                await session.execute(
                    select(
                        Notification.ticket_id,
                        Notification.notification_type,
                        Notification.recipient_id,
                    ).where(
                        Notification.ticket_id.in_(
                            [near_due_ticket_id, overdue_ticket_id]
                        )
                    )
                )
            ).all()
        )

    assert events_by_ticket[near_due_ticket_id] == {("WARNING", 80)}
    assert events_by_ticket[overdue_ticket_id] == {
        ("WARNING", 80),
        ("OVERDUE", 100),
        ("ESCALATED", 150),
    }

    expected_recipients = {
        seeded_users["processor_user_id"],
        seeded_users["admin_user_id"],
    }
    for ticket_id, expected_types in (
        (near_due_ticket_id, {"SLA_WARNING"}),
        (
            overdue_ticket_id,
            {"SLA_WARNING", "SLA_OVERDUE", "SLA_ESCALATED"},
        ),
    ):
        ticket_notifications = [
            row
            for row in notification_rows
            if row.ticket_id == ticket_id
            and row.notification_type.startswith("SLA_")
        ]
        assert {row.notification_type for row in ticket_notifications} == expected_types
        for notification_type in expected_types:
            assert {
                row.recipient_id
                for row in ticket_notifications
                if row.notification_type == notification_type
            } == expected_recipients

    # SLA-FT-03 - API hiển thị đúng Sắp quá hạn và Quá hạn.
    near_due_status = await client.get(
        f"/api/v1/tickets/{near_due_ticket_id}/sla",
        headers=requester_headers,
    )
    overdue_status = await client.get(
        f"/api/v1/tickets/{overdue_ticket_id}/sla",
        headers=requester_headers,
    )
    assert near_due_status.status_code == 200, near_due_status.text
    assert overdue_status.status_code == 200, overdue_status.text
    assert (
        near_due_status.json()["data"]["response_sla"]["status"]["code"]
        == "NEAR_DUE"
    )
    assert (
        overdue_status.json()["data"]["response_sla"]["status"]["code"]
        == "OVERDUE"
    )

    # SLA-FT-04 - Danh sách escalation trả đúng event của ticket quá hạn.
    breaches = await client.get(
        f"/api/v1/sla/breaches?ticket_id={overdue_ticket_id}&sla_type=RESPONSE&page_size=20",
        headers=admin_headers,
    )
    assert breaches.status_code == 200, breaches.text
    assert breaches.json()["data"]["total"] == 3
    assert {item["state"] for item in breaches.json()["data"]["items"]} == {
        "WARNING",
        "OVERDUE",
        "ESCALATED",
    }

    # SLA-FT-05 - Worker chạy lại không tạo event/notification trùng.
    async with session_factory() as session:
        second_run = await process_sla_escalations(
            session,
            now=test_now + timedelta(minutes=1),
        )
    assert second_run.created_events == 0
    assert second_run.created_notifications == 0

    # SLA-FT-06 - Phản hồi sau deadline hoàn tất SLA với kết quả BREACHED.
    replied = await client.post(
        f"/api/v1/tickets/{overdue_ticket_id}/comments",
        headers=processor_headers,
        json={
            "content": "Đã tiếp nhận ticket sau thời hạn phản hồi SLA.",
            "visibility": "PUBLIC",
            "comment_type": "REPLY",
        },
    )
    assert replied.status_code == 201, replied.text

    completed_sla = await client.get(
        f"/api/v1/tickets/{overdue_ticket_id}/sla",
        headers=requester_headers,
    )
    completed_response = completed_sla.json()["data"]["response_sla"]
    assert completed_response["runtime_status"] == "COMPLETED"
    assert completed_response["result"] == "BREACHED"
    assert completed_response["status"]["code"] == "OVERDUE"
    assert completed_response["completed_at"] is not None

    # SLA-FT-07 - Audit lưu đủ cảnh báo, quá hạn, escalation và hoàn tất SLA.
    async with session_factory() as session:
        audit_codes = set(
            (
                await session.execute(
                    select(AuditLog.action_code).where(
                        AuditLog.ticket_id == overdue_ticket_id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert {
        "SLA_WARNING_TRIGGERED",
        "SLA_OVERDUE_TRIGGERED",
        "SLA_ESCALATED_TRIGGERED",
        "SLA_COMPLETED",
    } <= audit_codes
