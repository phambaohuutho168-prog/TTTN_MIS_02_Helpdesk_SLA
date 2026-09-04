from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.core.sla import (
    calculate_deadline,
    calculate_metrics,
    calculate_result,
)
from app.models.priority import Priority
from app.models.role import Role
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_status import TicketStatus
from app.models.user import User
from app.models.user_role import UserRole
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _ticket_payload(seeded_users, priority_id):
    return {
        "title": "Kiểm thử SLA engine",
        "description": "Ticket dùng để kiểm tra deadline và các mốc SLA.",
        "category_id": seeded_users["active_category_id"],
        "priority_id": priority_id,
    }


@pytest.fixture
async def sla_data(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        p1 = Priority(
            priority_code="P1",
            priority_level=1,
            priority_name="Khẩn cấp",
            description="Mức ưu tiên cao nhất",
            is_active=True,
        )
        other_requester = User(
            email="sla.other.requester@example.com",
            full_name="SLA Other Requester",
            password_hash=hash_password("CorrectPassword123!"),
            is_active=True,
        )
        session.add_all(
            [
                p1,
                other_requester,
                TicketStatus(status_code="ASSIGNED", status_name="Đã phân công"),
                TicketStatus(status_code="IN_PROGRESS", status_name="Đang xử lý"),
                TicketStatus(status_code="PENDING_INFO", status_name="Chờ bổ sung"),
                TicketStatus(status_code="RESOLVED", status_name="Đã xử lý"),
            ]
        )
        await session.flush()
        requester_role_id = await session.scalar(
            select(Role.role_id).where(Role.role_code == "REQUESTER")
        )
        session.add(
            UserRole(
                user_id=other_requester.user_id,
                role_id=requester_role_id,
            )
        )
        session.add_all(
            [
                SLAPolicy(
                    priority_id=p1.priority_id,
                    version_no=1,
                    response_target_minutes=15,
                    resolution_target_minutes=240,
                    warning_percent=80,
                    escalation_percent=150,
                    effective_from=now - timedelta(days=30),
                    is_active=True,
                ),
                SLAPolicy(
                    priority_id=seeded_users["active_priority_id"],
                    version_no=1,
                    response_target_minutes=60,
                    resolution_target_minutes=1440,
                    warning_percent=80,
                    escalation_percent=150,
                    effective_from=now - timedelta(days=30),
                    is_active=True,
                ),
            ]
        )
        await session.commit()
        return {
            "p1_id": p1.priority_id,
            "other_user_id": other_requester.user_id,
            "other_credentials": {
                "email": other_requester.email,
                "password": "CorrectPassword123!",
            },
        }


def test_deadline_uses_calendar_minutes_and_normalizes_utc():
    started_at = datetime(2026, 9, 4, 8, 30)
    deadline = calculate_deadline(started_at=started_at, target_minutes=90)
    assert deadline == datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        calculate_deadline(started_at=started_at, target_minutes=0)


def test_result_includes_completed_pause_time_and_boundary_is_met():
    due_at = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    effective_due_at = due_at + timedelta(minutes=15)
    assert (
        calculate_result(
            completed_at=effective_due_at,
            due_at=due_at,
            total_paused_seconds=900,
        )
        == "MET"
    )
    assert (
        calculate_result(
            completed_at=effective_due_at + timedelta(seconds=1),
            due_at=due_at,
            total_paused_seconds=900,
        )
        == "BREACHED"
    )


def test_paused_metrics_freeze_elapsed_and_remaining_time():
    started_at = datetime(2026, 9, 4, 8, 0, tzinfo=timezone.utc)
    paused_at = started_at + timedelta(minutes=30)
    metrics = calculate_metrics(
        started_at=started_at,
        due_at=started_at + timedelta(hours=2),
        total_paused_seconds=0,
        runtime_status="PAUSED",
        paused_at=paused_at,
        now=started_at + timedelta(hours=5),
    )
    assert metrics.elapsed_seconds == 1800
    assert metrics.remaining_seconds == 5400
    assert metrics.progress_percent == 25.0


async def test_sla_endpoint_requires_authentication(
    client,
    credentials,
    seeded_users,
    sla_data,
):
    created = await client.post(
        "/api/v1/tickets",
        json=_ticket_payload(seeded_users, sla_data["p1_id"]),
        headers=await _headers(client, credentials),
    )
    ticket_id = created.json()["data"]["ticket_id"]
    response = await client.get(f"/api/v1/tickets/{ticket_id}/sla")
    assert response.status_code == 401


async def test_deadlines_follow_the_selected_priority_rule(
    client,
    credentials,
    seeded_users,
    sla_data,
):
    headers = await _headers(client, credentials)
    results = {}
    for code, priority_id in (
        ("P1", sla_data["p1_id"]),
        ("P3", seeded_users["active_priority_id"]),
    ):
        created = await client.post(
            "/api/v1/tickets",
            json=_ticket_payload(seeded_users, priority_id),
            headers=headers,
        )
        assert created.status_code == 201, created.text
        ticket_id = created.json()["data"]["ticket_id"]
        response = await client.get(
            f"/api/v1/tickets/{ticket_id}/sla",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        results[code] = response.json()["data"]

    assert results["P1"]["response_sla"]["target_minutes"] == 15
    assert results["P1"]["resolution_cycles"][0]["target_minutes"] == 240
    assert results["P3"]["response_sla"]["target_minutes"] == 60
    assert results["P3"]["resolution_cycles"][0]["target_minutes"] == 1440
    for result in results.values():
        response_sla = result["response_sla"]
        started_at = datetime.fromisoformat(response_sla["started_at"])
        base_due_at = datetime.fromisoformat(response_sla["base_due_at"])
        assert base_due_at - started_at == timedelta(
            minutes=response_sla["target_minutes"]
        )
        assert response_sla["due_at"] == response_sla["base_due_at"]
        assert response_sla["effective_due_at"] == response_sla["base_due_at"]
        assert response_sla["policy_version"] == 1


async def test_requester_cannot_read_another_requesters_sla(
    client,
    credentials,
    seeded_users,
    sla_data,
):
    created = await client.post(
        "/api/v1/tickets",
        json=_ticket_payload(seeded_users, sla_data["p1_id"]),
        headers=await _headers(client, sla_data["other_credentials"]),
    )
    ticket_id = created.json()["data"]["ticket_id"]
    response = await client.get(
        f"/api/v1/tickets/{ticket_id}/sla",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "TICKET_ACCESS_DENIED"


async def test_latest_effective_policy_version_is_snapshotted(
    client,
    credentials,
    seeded_users,
    sla_data,
    session_factory,
):
    async with session_factory() as session:
        session.add(
            SLAPolicy(
                priority_id=sla_data["p1_id"],
                version_no=2,
                response_target_minutes=10,
                resolution_target_minutes=180,
                warning_percent=70,
                escalation_percent=120,
                effective_from=datetime.now(timezone.utc) - timedelta(days=1),
                is_active=True,
            )
        )
        await session.commit()

    headers = await _headers(client, credentials)
    created = await client.post(
        "/api/v1/tickets",
        json=_ticket_payload(seeded_users, sla_data["p1_id"]),
        headers=headers,
    )
    ticket_id = created.json()["data"]["ticket_id"]
    data = (
        await client.get(f"/api/v1/tickets/{ticket_id}/sla", headers=headers)
    ).json()["data"]
    assert data["response_sla"]["policy_version"] == 2
    assert data["response_sla"]["target_minutes"] == 10
    assert data["resolution_cycles"][0]["target_minutes"] == 180


async def test_first_response_and_resolution_milestones_are_persisted(
    client,
    credentials,
    admin_credentials,
    processor_credentials,
    seeded_users,
    sla_data,
):
    requester_headers = await _headers(client, credentials)
    created = await client.post(
        "/api/v1/tickets",
        json=_ticket_payload(seeded_users, sla_data["p1_id"]),
        headers=requester_headers,
    )
    ticket_id = created.json()["data"]["ticket_id"]
    assigned = await client.put(
        f"/api/v1/tickets/{ticket_id}/assignment",
        json={
            "assignee_id": seeded_users["processor_user_id"],
            "reason": "Kiểm thử mốc SLA",
        },
        headers=await _headers(client, admin_credentials),
    )
    assert assigned.status_code == 200, assigned.text
    processor_headers = await _headers(client, processor_credentials)
    started = await client.post(
        f"/api/v1/tickets/{ticket_id}/start",
        json={"reason": "Bắt đầu xử lý"},
        headers=processor_headers,
    )
    assert started.status_code == 200, started.text
    replied = await client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        json={
            "content": "Đã tiếp nhận và đang kiểm tra yêu cầu.",
            "visibility": "PUBLIC",
            "comment_type": "REPLY",
        },
        headers=processor_headers,
    )
    assert replied.status_code == 201, replied.text
    resolved = await client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        json={"resolution_note": "Đã xử lý thành công yêu cầu kiểm thử."},
        headers=processor_headers,
    )
    assert resolved.status_code == 200, resolved.text

    response = await client.get(
        f"/api/v1/tickets/{ticket_id}/sla",
        headers=requester_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    response_sla = data["response_sla"]
    resolution_sla = data["resolution_cycles"][0]
    assert data["first_response_at"] == response_sla["completed_at"]
    assert response_sla["runtime_status"] == "COMPLETED"
    assert response_sla["result"] == "MET"
    assert resolution_sla["runtime_status"] == "COMPLETED"
    assert resolution_sla["completed_at"] is not None
    assert resolution_sla["result"] == "MET"


async def test_ticket_without_runtime_returns_configuration_aware_404(
    client,
    credentials,
    seeded_users,
    sla_data,
    session_factory,
):
    async with session_factory() as session:
        ticket = Ticket(
            ticket_code="TK-20260904-NO-SLA-000001",
            requester_id=seeded_users["active_user_id"],
            category_id=seeded_users["active_category_id"],
            priority_id=seeded_users["active_priority_id"],
            current_status_code="NEW",
            title="Ticket chưa có SLA",
            description="Dữ liệu lịch sử chưa được tạo SLA runtime.",
        )
        session.add(ticket)
        await session.commit()
        ticket_id = ticket.ticket_id

    response = await client.get(
        f"/api/v1/tickets/{ticket_id}/sla",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "SLA_RUNTIME_NOT_FOUND"
