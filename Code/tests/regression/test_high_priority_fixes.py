"""CV055 regression coverage for the three high-priority KPI defects."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.ticket import Ticket
from app.models.ticket_resolution import TicketResolution
from app.models.ticket_status import TicketStatus
from app.models.ticket_status_history import TicketStatusHistory
from app.repositories import dashboard_repository
from app.services.dashboard_service import _overall_sla_results, _sla_summary


pytestmark = pytest.mark.release_candidate


@pytest.fixture
async def cv055_regression_data(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    created_at = now - timedelta(days=40)
    async with session_factory() as session:
        session.add_all(
            [
                TicketStatus(
                    status_code="CLOSED",
                    status_name="Đã đóng",
                    is_terminal=True,
                ),
                TicketStatus(
                    status_code="REOPENED",
                    status_name="Đã mở lại",
                ),
            ]
        )
        ticket = Ticket(
            ticket_code="TK-CV055-HIGH-001",
            requester_id=seeded_users["active_user_id"],
            category_id=seeded_users["active_category_id"],
            priority_id=seeded_users["active_priority_id"],
            current_status_code="CLOSED",
            title="CV055 KPI regression",
            description="Ticket cũ được resolve, đóng và mở lại ở các mốc khác nhau.",
            first_response_at=created_at + timedelta(minutes=30),
            closed_at=created_at + timedelta(minutes=300),
            closed_by=seeded_users["active_user_id"],
            created_at=created_at,
            updated_at=now,
        )
        session.add(ticket)
        await session.flush()
        resolved_at = created_at + timedelta(minutes=120)
        reopened_at = now - timedelta(days=2)
        session.add_all(
            [
                TicketResolution(
                    ticket_id=ticket.ticket_id,
                    resolved_by=seeded_users["processor_user_id"],
                    cycle_no=1,
                    resolution_note="Đã xử lý trong 120 phút.",
                    resolved_at=resolved_at,
                ),
                TicketStatusHistory(
                    ticket_id=ticket.ticket_id,
                    from_status_code="CLOSED",
                    to_status_code="REOPENED",
                    changed_by=seeded_users["active_user_id"],
                    reason="Mở lại trong kỳ dù ticket được tạo từ kỳ trước.",
                    changed_at=reopened_at,
                ),
            ]
        )
        await session.commit()
    return {
        "ticket_id": ticket.ticket_id,
        "created_at": created_at,
        "resolved_at": resolved_at,
        "closed_at": ticket.closed_at,
        "now": now,
    }


def test_high_001_overall_sla_is_calculated_once_per_ticket():
    created = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = [
        (1, created, "RESPONSE", "MET"),
        (1, created, "RESOLUTION", "MET"),
        (2, created, "RESPONSE", "BREACHED"),
        (2, created, "RESOLUTION", "MET"),
        (3, created, "RESPONSE", "MET"),
    ]

    overall_rows = _overall_sla_results(rows)
    summary = _sla_summary([result for _created, result in overall_rows])

    assert overall_rows == [(created, "MET"), (created, "BREACHED")]
    assert summary.model_dump() == {
        "met": 1,
        "breached": 1,
        "total": 2,
        "compliance_rate": 50.0,
    }


async def test_high_002_resolution_duration_uses_resolved_at_not_closed_at(
    session_factory,
    cv055_regression_data,
):
    async with session_factory() as session:
        rows = await dashboard_repository.ticket_duration_rows(
            session,
            conditions=[Ticket.ticket_id == cv055_regression_data["ticket_id"]],
        )

    assert len(rows) == 1
    created_at, first_response_at, resolved_at = rows[0]
    assert (first_response_at - created_at).total_seconds() / 60 == 30
    assert (resolved_at - created_at).total_seconds() / 60 == 120
    assert resolved_at != cv055_regression_data["closed_at"].replace(tzinfo=None)
    assert cv055_regression_data["resolved_at"] != cv055_regression_data["closed_at"]


async def test_high_003_reopen_period_uses_event_time_not_ticket_created_time(
    session_factory,
    cv055_regression_data,
):
    async with session_factory() as session:
        count = await dashboard_repository.reopened_ticket_count(
            session,
            conditions=[],
            date_from=cv055_regression_data["now"] - timedelta(days=10),
            date_to=cv055_regression_data["now"],
        )

    assert cv055_regression_data["created_at"] < cv055_regression_data["now"] - timedelta(days=10)
    assert count == 1
