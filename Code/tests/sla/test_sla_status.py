from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.sla import (
    SLA_STATUS_PRESENTATIONS,
    classify_sla_status,
    overall_sla_status,
)
from app.models.sla_policy import SLAPolicy
from app.models.ticket_sla import TicketSLA
from tests.conftest import login_client


@pytest.mark.parametrize(
    ("runtime_status", "result", "remaining", "progress", "expected"),
    [
        ("RUNNING", None, 1200, 79.99, "ON_TRACK"),
        ("RUNNING", None, 1200, 80.0, "NEAR_DUE"),
        ("RUNNING", None, 0, 100.0, "NEAR_DUE"),
        ("RUNNING", None, -1, 100.01, "OVERDUE"),
        ("COMPLETED", "MET", 300, 95.0, "MET"),
        ("COMPLETED", "BREACHED", -300, 105.0, "OVERDUE"),
        ("NOT_APPLICABLE", "NOT_APPLICABLE", None, None, "NOT_APPLICABLE"),
    ],
)
def test_sla_status_rules(
    runtime_status,
    result,
    remaining,
    progress,
    expected,
):
    status = classify_sla_status(
        runtime_status=runtime_status,
        result=result,
        remaining_seconds=remaining,
        progress_percent=progress,
        warning_percent=80,
    )
    assert status.code == expected


def test_paused_runtime_keeps_its_deadline_health_status():
    status = classify_sla_status(
        runtime_status="PAUSED",
        result=None,
        remaining_seconds=600,
        progress_percent=85,
        warning_percent=80,
    )
    assert status.code == "NEAR_DUE"
    assert status.label == "Sắp quá hạn"


def test_overall_status_uses_the_most_urgent_runtime():
    status = overall_sla_status(
        [
            SLA_STATUS_PRESENTATIONS["MET"],
            SLA_STATUS_PRESENTATIONS["ON_TRACK"],
            SLA_STATUS_PRESENTATIONS["NEAR_DUE"],
        ]
    )
    assert status is not None
    assert status.code == "NEAR_DUE"


def test_warning_threshold_must_match_policy_domain():
    with pytest.raises(ValueError):
        classify_sla_status(
            runtime_status="RUNNING",
            result=None,
            remaining_seconds=60,
            progress_percent=50,
            warning_percent=100,
        )


@pytest.fixture
async def status_policy(session_factory, seeded_users):
    async with session_factory() as session:
        session.add(
            SLAPolicy(
                priority_id=seeded_users["active_priority_id"],
                version_no=1,
                response_target_minutes=60,
                resolution_target_minutes=1440,
                warning_percent=80,
                escalation_percent=150,
                effective_from=datetime.now(timezone.utc) - timedelta(days=1),
                is_active=True,
            )
        )
        await session.commit()


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_sla_status_is_available_in_sla_and_ticket_detail_apis(
    client,
    credentials,
    seeded_users,
    status_policy,
):
    headers = await _headers(client, credentials)
    created = await client.post(
        "/api/v1/tickets",
        json={
            "title": "Hiển thị trạng thái SLA",
            "description": "Kiểm tra trạng thái SLA nhất quán giữa các API.",
            "category_id": seeded_users["active_category_id"],
            "priority_id": seeded_users["active_priority_id"],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["data"]["ticket_id"]

    sla_response = await client.get(
        f"/api/v1/tickets/{ticket_id}/sla",
        headers=headers,
    )
    detail_response = await client.get(
        f"/api/v1/tickets/{ticket_id}",
        headers=headers,
    )
    assert sla_response.status_code == 200, sla_response.text
    assert detail_response.status_code == 200, detail_response.text

    sla_data = sla_response.json()["data"]
    detail_summary = detail_response.json()["data"]["sla_summary"]
    expected = {
        "code": "ON_TRACK",
        "label": "Còn hạn",
        "tone": "INFO",
        "css_class": "sla-status--on-track",
    }
    assert sla_data["response_sla"]["status"] == expected
    assert sla_data["overall_status"] == expected
    assert detail_summary["response_sla"]["status"] == expected
    assert detail_summary["overall_status"] == expected


async def test_sla_api_changes_from_near_due_to_overdue_and_met(
    client,
    credentials,
    seeded_users,
    status_policy,
    session_factory,
):
    headers = await _headers(client, credentials)
    created = await client.post(
        "/api/v1/tickets",
        json={
            "title": "SLA thay đổi trạng thái",
            "description": "Kiểm tra trạng thái hiển thị theo dòng thời gian.",
            "category_id": seeded_users["active_category_id"],
            "priority_id": seeded_users["active_priority_id"],
        },
        headers=headers,
    )
    ticket_id = created.json()["data"]["ticket_id"]

    async def update_response_sla(state):
        now = datetime.now(timezone.utc)
        async with session_factory() as session:
            record = await session.scalar(
                select(TicketSLA).where(
                    TicketSLA.ticket_id == ticket_id,
                    TicketSLA.sla_type == "RESPONSE",
                )
            )
            record.started_at = now - timedelta(minutes=state["elapsed_minutes"])
            record.due_at = record.started_at + timedelta(minutes=60)
            record.runtime_status = state["runtime_status"]
            record.result = state["result"]
            record.completed_at = (
                now
                if state["runtime_status"] == "COMPLETED"
                else None
            )
            await session.commit()

    for state, expected in (
        (
            {"elapsed_minutes": 54, "runtime_status": "RUNNING", "result": None},
            "NEAR_DUE",
        ),
        (
            {"elapsed_minutes": 61, "runtime_status": "RUNNING", "result": None},
            "OVERDUE",
        ),
        (
            {"elapsed_minutes": 54, "runtime_status": "COMPLETED", "result": "MET"},
            "MET",
        ),
    ):
        await update_response_sla(state)
        response = await client.get(
            f"/api/v1/tickets/{ticket_id}/sla",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["response_sla"]["status"]["code"] == expected


async def test_home_ui_renders_four_required_sla_badges(client):
    response = await client.get("/")
    assert response.status_code == 200
    html = response.text
    for code, label in (
        ("ON_TRACK", "Còn hạn"),
        ("NEAR_DUE", "Sắp quá hạn"),
        ("OVERDUE", "Quá hạn"),
        ("MET", "Đúng SLA"),
    ):
        assert f'data-sla-status="{code}"' in html
        assert label in html

    css = (await client.get("/static/style.css")).text
    for css_class in (
        "sla-status--on-track",
        "sla-status--near-due",
        "sla-status--overdue",
        "sla-status--met",
    ):
        assert f".{css_class}" in css
