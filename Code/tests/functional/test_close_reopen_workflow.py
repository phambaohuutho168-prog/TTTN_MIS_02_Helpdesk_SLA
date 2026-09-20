"""CV049 - Workflow Test cho đóng và mở lại ticket.

Kiểm tra các trường hợp mở lại bị chặn và luồng hợp lệ cập nhật trạng thái,
resolution SLA cycle, status history và audit log.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_resolution import TicketResolution
from app.models.ticket_sla import TicketSLA
from app.models.ticket_status import TicketStatus
from app.models.ticket_status_history import TicketStatusHistory
from tests.conftest import login_client


async def _auth_headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def cv049_runtime_configuration(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        session.add_all(
            [
                TicketStatus(status_code="ASSIGNED", status_name="Đã phân công"),
                TicketStatus(status_code="IN_PROGRESS", status_name="Đang xử lý"),
                TicketStatus(status_code="RESOLVED", status_name="Đã xử lý"),
                TicketStatus(status_code="REOPENED", status_name="Đã mở lại"),
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
                    warning_percent=80,
                    escalation_percent=150,
                    effective_from=now - timedelta(days=1),
                    is_active=True,
                ),
            ]
        )
        await session.commit()


async def _prepare_resolved_ticket(
    client,
    *,
    requester_headers,
    admin_headers,
    processor_headers,
    seeded_users,
    title,
):
    created = await client.post(
        "/api/v1/tickets",
        headers=requester_headers,
        json={
            "title": title,
            "description": "Ticket dùng để kiểm thử đóng và mở lại trong CV049.",
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
            "reason": "Phân công Processor kiểm thử CV049",
        },
    )
    assert assigned.status_code == 200, assigned.text

    started = await client.post(
        f"/api/v1/tickets/{ticket_id}/start",
        headers=processor_headers,
        json={"reason": "Bắt đầu xử lý ticket CV049"},
    )
    assert started.status_code == 200, started.text

    replied = await client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers=processor_headers,
        json={
            "content": "Đã tiếp nhận và kiểm tra yêu cầu của người dùng.",
            "visibility": "PUBLIC",
            "comment_type": "REPLY",
        },
    )
    assert replied.status_code == 201, replied.text

    resolved = await client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        headers=processor_headers,
        json={
            "resolution_note": "Đã khắc phục sự cố và xác nhận chức năng hoạt động."
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["data"]["status"]["status_code"] == "RESOLVED"
    return ticket_id


async def _mutation_counts(session_factory, ticket_id):
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

@pytest.mark.business_rule
async def test_cv049_close_and_reopen_workflow(
    client,
    credentials,
    admin_credentials,
    processor_credentials,
    seeded_users,
    session_factory,
    cv049_runtime_configuration,
):
    requester_headers = await _auth_headers(client, credentials)
    admin_headers = await _auth_headers(client, admin_credentials)
    processor_headers = await _auth_headers(client, processor_credentials)

    # WF-FT-01 - Đóng ticket RESOLVED hợp lệ.
    closed_ticket_id = await _prepare_resolved_ticket(
        client,
        requester_headers=requester_headers,
        admin_headers=admin_headers,
        processor_headers=processor_headers,
        seeded_users=seeded_users,
        title="CV049 - Ticket được xác nhận đóng",
    )
    closed = await client.post(
        f"/api/v1/tickets/{closed_ticket_id}/close",
        headers=requester_headers,
        json={"reason": "Đã kiểm tra kết quả và đồng ý đóng ticket"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["code"] == "TICKET_CLOSED"
    assert closed.json()["data"]["status"]["status_code"] == "CLOSED"
    assert closed.json()["data"]["closed_by"]["user_id"] == seeded_users[
        "active_user_id"
    ]
    assert closed.json()["data"]["closed_at"] is not None

    # WF-FT-02 - Ticket CLOSED là terminal, mở lại phải bị chặn và không phát sinh dữ liệu.
    closed_counts_before = await _mutation_counts(session_factory, closed_ticket_id)
    reopen_closed = await client.post(
        f"/api/v1/tickets/{closed_ticket_id}/reopen",
        headers=requester_headers,
        json={"reason": "Thử mở lại ticket đã được đóng hoàn toàn."},
    )
    assert reopen_closed.status_code == 409
    assert reopen_closed.json()["code"] == "TICKET_ALREADY_TERMINAL"
    assert await _mutation_counts(session_factory, closed_ticket_id) == closed_counts_before

    # WF-FT-03 - Ticket RESOLVED quá 72 giờ bị chặn atomically.
    expired_ticket_id = await _prepare_resolved_ticket(
        client,
        requester_headers=requester_headers,
        admin_headers=admin_headers,
        processor_headers=processor_headers,
        seeded_users=seeded_users,
        title="CV049 - Ticket đã hết thời hạn mở lại",
    )
    async with session_factory() as session:
        resolution = await session.scalar(
            select(TicketResolution).where(
                TicketResolution.ticket_id == expired_ticket_id,
                TicketResolution.cycle_no == 1,
            )
        )
        resolution.resolved_at = datetime.now(timezone.utc) - timedelta(hours=73)
        await session.commit()

    expired_counts_before = await _mutation_counts(session_factory, expired_ticket_id)
    reopen_expired = await client.post(
        f"/api/v1/tickets/{expired_ticket_id}/reopen",
        headers=requester_headers,
        json={"reason": "Sự cố tái diễn nhưng đã quá cửa sổ 72 giờ."},
    )
    assert reopen_expired.status_code == 409
    assert reopen_expired.json()["code"] == "REOPEN_WINDOW_EXPIRED"
    assert await _mutation_counts(session_factory, expired_ticket_id) == expired_counts_before
    async with session_factory() as session:
        expired_ticket = await session.get(Ticket, expired_ticket_id)
        assert expired_ticket.current_status_code == "RESOLVED"

    # WF-FT-04 - Requester mở lại ticket RESOLVED còn trong 72 giờ.
    valid_ticket_id = await _prepare_resolved_ticket(
        client,
        requester_headers=requester_headers,
        admin_headers=admin_headers,
        processor_headers=processor_headers,
        seeded_users=seeded_users,
        title="CV049 - Ticket hợp lệ để mở lại",
    )
    reopen_reason = "Sự cố tái diễn sau khi đã áp dụng cách xử lý trước."
    reopened = await client.post(
        f"/api/v1/tickets/{valid_ticket_id}/reopen",
        headers=requester_headers,
        json={"reason": reopen_reason},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["code"] == "TICKET_REOPENED"
    assert reopened.json()["data"]["status"]["status_code"] == "REOPENED"

    # Chu kỳ SLA hoàn tất trước đó phải được giữ nguyên cho tới khi resume.
    async with session_factory() as session:
        before_resume = list(
            (
                await session.execute(
                    select(TicketSLA)
                    .where(
                        TicketSLA.ticket_id == valid_ticket_id,
                        TicketSLA.sla_type == "RESOLUTION",
                    )
                    .order_by(TicketSLA.cycle_no)
                )
            )
            .scalars()
            .all()
        )
    assert [record.cycle_no for record in before_resume] == [1]
    assert before_resume[0].runtime_status == "COMPLETED"

    # WF-FT-05 - Processor resume tạo resolution SLA cycle 2 và chuyển IN_PROGRESS.
    resumed = await client.post(
        f"/api/v1/tickets/{valid_ticket_id}/resume",
        headers=processor_headers,
        json={"reason": "Tiếp nhận xử lý lại ticket đã được mở."},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["code"] == "TICKET_RESUMED"
    assert resumed.json()["data"]["status"]["status_code"] == "IN_PROGRESS"

    async with session_factory() as session:
        resolution_slas = list(
            (
                await session.execute(
                    select(TicketSLA)
                    .where(
                        TicketSLA.ticket_id == valid_ticket_id,
                        TicketSLA.sla_type == "RESOLUTION",
                    )
                    .order_by(TicketSLA.cycle_no)
                )
            )
            .scalars()
            .all()
        )
        histories = list(
            (
                await session.execute(
                    select(TicketStatusHistory)
                    .where(TicketStatusHistory.ticket_id == valid_ticket_id)
                    .order_by(TicketStatusHistory.history_id)
                )
            )
            .scalars()
            .all()
        )
        audits = list(
            (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.ticket_id == valid_ticket_id)
                    .order_by(AuditLog.audit_id)
                )
            )
            .scalars()
            .all()
        )

    assert [record.cycle_no for record in resolution_slas] == [1, 2]
    assert resolution_slas[0].runtime_status == "COMPLETED"
    assert resolution_slas[1].runtime_status == "RUNNING"
    assert resolution_slas[1].due_at - resolution_slas[1].started_at == timedelta(
        minutes=240
    )
    assert [history.to_status_code for history in histories] == [
        "NEW",
        "ASSIGNED",
        "IN_PROGRESS",
        "RESOLVED",
        "REOPENED",
        "IN_PROGRESS",
    ]

    audit_by_action = {audit.action_code: audit for audit in audits}
    assert {
        "TICKET_REOPENED",
        "SLA_RUNTIME_CREATED",
        "TICKET_RESUMED",
    } <= set(audit_by_action)
    reopen_audit = audit_by_action["TICKET_REOPENED"]
    sla_audit = audit_by_action["SLA_RUNTIME_CREATED"]
    resume_audit = audit_by_action["TICKET_RESUMED"]
    assert reopen_audit.reason == reopen_reason
    assert reopen_audit.new_value_json["source_resolution_cycle"] == 1
    assert reopen_audit.new_value_json["next_resolution_cycle"] == 2
    assert (
        reopen_audit.new_value_json["sla_action"]
        == "PRESERVE_COMPLETED_CYCLES_UNTIL_RESUME"
    )
    assert sla_audit.entity_id == resolution_slas[1].ticket_sla_id
    assert sla_audit.new_value_json["cycle_no"] == 2
    assert resume_audit.new_value_json["resolution_cycle"] == 2
    assert resume_audit.new_value_json["ticket_sla_id"] == resolution_slas[
        1
    ].ticket_sla_id
