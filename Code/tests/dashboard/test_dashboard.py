from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.category import Category
from app.models.department import Department
from app.models.priority import Priority
from app.models.rating import Rating
from app.models.role import Role
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_sla import TicketSLA
from app.models.ticket_status import TicketStatus
from app.models.ticket_status_history import TicketStatusHistory
from app.models.user import User
from app.models.user_role import UserRole
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def dashboard_data(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        session.add_all(
            [
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
                TicketStatus(
                    status_code="REJECTED",
                    status_name="Đã từ chối",
                    is_terminal=True,
                ),
                TicketStatus(
                    status_code="REOPENED",
                    status_name="Đã mở lại",
                    is_terminal=False,
                ),
            ]
        )
        operations = Department(
            department_name="Infrastructure Operations",
            description="Bộ phận vận hành hạ tầng",
            is_active=True,
        )
        hardware = Category(
            category_name="Phần cứng CV043",
            description="Danh mục kiểm thử dashboard",
            is_active=True,
        )
        high_priority = Priority(
            priority_code="P2",
            priority_level=2,
            priority_name="Cao",
            description="Mức ưu tiên kiểm thử dashboard",
            is_active=True,
        )
        session.add_all([operations, hardware, high_priority])
        await session.flush()

        other_processor = User(
            email="dashboard.processor@example.com",
            full_name="Dashboard Other Processor",
            password_hash=hash_password("CorrectPassword123!"),
            department_id=operations.department_id,
            is_active=True,
        )
        session.add(other_processor)
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

        policies = {
            "p3": SLAPolicy(
                priority_id=seeded_users["active_priority_id"],
                version_no=1,
                response_target_minutes=60,
                resolution_target_minutes=240,
                warning_percent=80,
                escalation_percent=150,
                effective_from=now - timedelta(days=90),
                is_active=True,
            ),
            "p2": SLAPolicy(
                priority_id=high_priority.priority_id,
                version_no=1,
                response_target_minutes=60,
                resolution_target_minutes=240,
                warning_percent=80,
                escalation_percent=150,
                effective_from=now - timedelta(days=90),
                is_active=True,
            ),
        }
        session.add_all(policies.values())
        await session.flush()

        def make_ticket(
            key: str,
            *,
            days_ago: int,
            status_code: str,
            category_id: int,
            priority_id: int,
            response_minutes: int | None = None,
            resolution_minutes: int | None = None,
        ) -> Ticket:
            created_at = now - timedelta(days=days_ago)
            return Ticket(
                ticket_code=f"TK-CV043-{key}",
                requester_id=seeded_users["active_user_id"],
                category_id=category_id,
                priority_id=priority_id,
                current_status_code=status_code,
                title=f"Dashboard {key}",
                description="Ticket kiểm thử KPI dashboard.",
                first_response_at=(
                    created_at + timedelta(minutes=response_minutes)
                    if response_minutes is not None
                    else None
                ),
                closed_at=(
                    created_at + timedelta(minutes=resolution_minutes)
                    if resolution_minutes is not None
                    else None
                ),
                closed_by=(
                    seeded_users["admin_user_id"]
                    if resolution_minutes is not None
                    else None
                ),
                created_at=created_at,
                updated_at=now,
            )

        tickets = {
            "open": make_ticket(
                "OPEN",
                days_ago=4,
                status_code="IN_PROGRESS",
                category_id=seeded_users["active_category_id"],
                priority_id=seeded_users["active_priority_id"],
                response_minutes=30,
            ),
            "met": make_ticket(
                "MET",
                days_ago=3,
                status_code="CLOSED",
                category_id=seeded_users["active_category_id"],
                priority_id=seeded_users["active_priority_id"],
                response_minutes=60,
                resolution_minutes=180,
            ),
            "breached": make_ticket(
                "BREACHED",
                days_ago=2,
                status_code="CLOSED",
                category_id=hardware.category_id,
                priority_id=high_priority.priority_id,
                response_minutes=120,
                resolution_minutes=300,
            ),
            "rejected": make_ticket(
                "REJECTED",
                days_ago=1,
                status_code="REJECTED",
                category_id=hardware.category_id,
                priority_id=high_priority.priority_id,
            ),
            "old": make_ticket(
                "OLD",
                days_ago=40,
                status_code="CLOSED",
                category_id=seeded_users["active_category_id"],
                priority_id=seeded_users["active_priority_id"],
                response_minutes=10,
                resolution_minutes=100,
            ),
        }
        session.add_all(tickets.values())
        await session.flush()

        session.add_all(
            [
                TicketAssignment(
                    ticket_id=tickets[key].ticket_id,
                    assignee_id=assignee_id,
                    assigned_by=seeded_users["admin_user_id"],
                    assigned_at=tickets[key].created_at,
                    is_current=True,
                    reason="Phân công kiểm thử dashboard.",
                )
                for key, assignee_id in (
                    ("open", seeded_users["processor_user_id"]),
                    ("met", seeded_users["processor_user_id"]),
                    ("breached", other_processor.user_id),
                    ("old", seeded_users["processor_user_id"]),
                )
            ]
        )
        session.add(
            TicketStatusHistory(
                ticket_id=tickets["met"].ticket_id,
                from_status_code="CLOSED",
                to_status_code="REOPENED",
                changed_by=seeded_users["active_user_id"],
                reason="Mở lại để kiểm thử KPI.",
                changed_at=tickets["met"].created_at + timedelta(hours=1),
            )
        )
        session.add_all(
            [
                Rating(
                    ticket_id=tickets["met"].ticket_id,
                    rated_by=seeded_users["active_user_id"],
                    score=5,
                    created_at=now,
                ),
                Rating(
                    ticket_id=tickets["breached"].ticket_id,
                    rated_by=seeded_users["active_user_id"],
                    score=3,
                    created_at=now,
                ),
                Rating(
                    ticket_id=tickets["old"].ticket_id,
                    rated_by=seeded_users["active_user_id"],
                    score=1,
                    created_at=now - timedelta(days=39),
                ),
            ]
        )

        def sla_record(
            ticket_key: str,
            sla_type: str,
            result: str | None,
            *,
            completed_minutes: int | None,
        ) -> TicketSLA:
            ticket = tickets[ticket_key]
            policy = policies["p2" if ticket_key in {"breached", "rejected"} else "p3"]
            runtime_status = (
                "RUNNING"
                if result is None
                else (
                    "NOT_APPLICABLE"
                    if result == "NOT_APPLICABLE"
                    else "COMPLETED"
                )
            )
            return TicketSLA(
                ticket_id=ticket.ticket_id,
                sla_policy_id=policy.sla_policy_id,
                sla_type=sla_type,
                cycle_no=1,
                started_at=ticket.created_at,
                due_at=ticket.created_at
                + timedelta(minutes=60 if sla_type == "RESPONSE" else 240),
                completed_at=(
                    ticket.created_at + timedelta(minutes=completed_minutes)
                    if completed_minutes is not None
                    else None
                ),
                runtime_status=runtime_status,
                result=result,
                created_at=ticket.created_at,
                updated_at=now,
            )

        session.add_all(
            [
                sla_record("open", "RESPONSE", "MET", completed_minutes=30),
                sla_record("open", "RESOLUTION", None, completed_minutes=None),
                sla_record("met", "RESPONSE", "MET", completed_minutes=60),
                sla_record("met", "RESOLUTION", "MET", completed_minutes=180),
                sla_record(
                    "breached",
                    "RESPONSE",
                    "BREACHED",
                    completed_minutes=120,
                ),
                sla_record(
                    "breached",
                    "RESOLUTION",
                    "BREACHED",
                    completed_minutes=300,
                ),
                sla_record(
                    "rejected",
                    "RESPONSE",
                    "NOT_APPLICABLE",
                    completed_minutes=5,
                ),
                sla_record(
                    "rejected",
                    "RESOLUTION",
                    "NOT_APPLICABLE",
                    completed_minutes=5,
                ),
                sla_record("old", "RESPONSE", "MET", completed_minutes=10),
                sla_record("old", "RESOLUTION", "MET", completed_minutes=100),
            ]
        )
        await session.commit()
        return {
            "now": now,
            "hardware_id": hardware.category_id,
            "p2_id": high_priority.priority_id,
            "operations_id": operations.department_id,
        }


def _recent_period(dashboard_data):
    now = dashboard_data["now"]
    return {
        "from": (now - timedelta(days=10)).isoformat(),
        "to": now.isoformat(),
    }


@pytest.mark.parametrize(
    "path",
    ["/api/v1/dashboard/overview", "/api/v1/dashboard/sla-performance"],
)
async def test_dashboard_requires_authentication(client, dashboard_data, path):
    response = await client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    ["/api/v1/dashboard/overview", "/api/v1/dashboard/sla-performance"],
)
async def test_requester_cannot_view_dashboard(
    client,
    credentials,
    dashboard_data,
    path,
):
    response = await client.get(
        path,
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACTION"


async def test_admin_overview_returns_required_kpis(
    client,
    admin_credentials,
    dashboard_data,
):
    response = await client.get(
        "/api/v1/dashboard/overview",
        params=_recent_period(dashboard_data),
        headers=await _headers(client, admin_credentials),
    )
    assert response.status_code == 200, response.text
    assert response.json()["code"] == "DASHBOARD_OVERVIEW_RETRIEVED"
    data = response.json()["data"]
    assert data["ticket_counts"] == {
        "total": 4,
        "open": 1,
        "closed": 2,
        "rejected": 1,
        "reopened": 1,
    }
    assert data["average_first_response_minutes"] == 70.0
    assert data["first_response_sample_size"] == 3
    assert data["average_resolution_minutes"] == 240.0
    assert data["resolution_sample_size"] == 2
    assert data["sla_compliance"] == {
        "met": 3,
        "breached": 2,
        "total": 5,
        "compliance_rate": 60.0,
    }
    assert data["satisfaction"]["rated_tickets"] == 2
    assert data["satisfaction"]["average_score"] == 4.0
    assert data["satisfaction"]["by_score"] == [
        {"score": 1, "count": 0},
        {"score": 2, "count": 0},
        {"score": 3, "count": 1},
        {"score": 4, "count": 0},
        {"score": 5, "count": 1},
    ]


async def test_overview_breakdowns_are_counted_and_sorted(
    client,
    admin_credentials,
    dashboard_data,
):
    response = await client.get(
        "/api/v1/dashboard/overview",
        params=_recent_period(dashboard_data),
        headers=await _headers(client, admin_credentials),
    )
    data = response.json()["data"]
    assert [(item["status_code"], item["count"]) for item in data["by_status"]] == [
        ("CLOSED", 2),
        ("IN_PROGRESS", 1),
        ("REJECTED", 1),
    ]
    assert [item["count"] for item in data["by_category"]] == [2, 2]
    assert [item["count"] for item in data["by_priority"]] == [2, 2]


async def test_processor_dashboard_is_limited_to_current_assignments(
    client,
    processor_credentials,
    dashboard_data,
):
    response = await client.get(
        "/api/v1/dashboard/overview",
        params=_recent_period(dashboard_data),
        headers=await _headers(client, processor_credentials),
    )
    data = response.json()["data"]
    assert data["ticket_counts"]["total"] == 2
    assert data["ticket_counts"]["open"] == 1
    assert data["ticket_counts"]["closed"] == 1
    assert data["sla_compliance"]["compliance_rate"] == 100.0
    assert data["satisfaction"]["average_score"] == 5.0


async def test_category_and_priority_filters_are_combined(
    client,
    admin_credentials,
    dashboard_data,
):
    params = {
        **_recent_period(dashboard_data),
        "category_id": dashboard_data["hardware_id"],
        "priority_id": dashboard_data["p2_id"],
    }
    response = await client.get(
        "/api/v1/dashboard/overview",
        params=params,
        headers=await _headers(client, admin_credentials),
    )
    data = response.json()["data"]
    assert data["ticket_counts"]["total"] == 2
    assert data["ticket_counts"]["closed"] == 1
    assert data["ticket_counts"]["rejected"] == 1
    assert data["sla_compliance"]["compliance_rate"] == 0.0


async def test_department_filter_uses_current_assignee_department(
    client,
    admin_credentials,
    seeded_users,
    dashboard_data,
):
    response = await client.get(
        "/api/v1/dashboard/overview",
        params={
            **_recent_period(dashboard_data),
            "department_id": seeded_users["department_id"],
        },
        headers=await _headers(client, admin_credentials),
    )
    data = response.json()["data"]
    assert data["ticket_counts"]["total"] == 2
    assert data["ticket_counts"]["reopened"] == 1


async def test_admin_can_filter_by_current_assignee(
    client,
    admin_credentials,
    seeded_users,
    dashboard_data,
):
    response = await client.get(
        "/api/v1/dashboard/overview",
        params={
            **_recent_period(dashboard_data),
            "assignee_id": seeded_users["processor_user_id"],
        },
        headers=await _headers(client, admin_credentials),
    )
    data = response.json()["data"]
    assert data["ticket_counts"]["total"] == 2
    assert data["sla_compliance"]["compliance_rate"] == 100.0


async def test_time_filter_excludes_old_tickets(
    client,
    admin_credentials,
    dashboard_data,
):
    recent = await client.get(
        "/api/v1/dashboard/overview",
        params=_recent_period(dashboard_data),
        headers=await _headers(client, admin_credentials),
    )
    all_time = await client.get(
        "/api/v1/dashboard/overview",
        headers=await _headers(client, admin_credentials),
    )
    assert recent.json()["data"]["ticket_counts"]["total"] == 4
    assert all_time.json()["data"]["ticket_counts"]["total"] == 5
    assert all_time.json()["data"]["satisfaction"]["rated_tickets"] == 3


async def test_sla_performance_splits_types_and_excludes_not_applicable(
    client,
    admin_credentials,
    dashboard_data,
):
    response = await client.get(
        "/api/v1/dashboard/sla-performance",
        params=_recent_period(dashboard_data),
        headers=await _headers(client, admin_credentials),
    )
    assert response.status_code == 200, response.text
    assert response.json()["code"] == "SLA_PERFORMANCE_RETRIEVED"
    data = response.json()["data"]
    assert data["response"] == {
        "met": 2,
        "breached": 1,
        "total": 3,
        "compliance_rate": 66.67,
    }
    assert data["resolution"] == {
        "met": 1,
        "breached": 1,
        "total": 2,
        "compliance_rate": 50.0,
    }
    assert data["overall"]["compliance_rate"] == 60.0
    assert data["excluded_not_applicable"] == 2
    assert sum(item["total"] for item in data["trend"]) == 5


async def test_processor_sla_performance_is_scoped(
    client,
    processor_credentials,
    dashboard_data,
):
    response = await client.get(
        "/api/v1/dashboard/sla-performance",
        params=_recent_period(dashboard_data),
        headers=await _headers(client, processor_credentials),
    )
    data = response.json()["data"]
    assert data["overall"] == {
        "met": 3,
        "breached": 0,
        "total": 3,
        "compliance_rate": 100.0,
    }
    assert data["excluded_not_applicable"] == 0


async def test_empty_period_returns_zero_counts_and_null_rates(
    client,
    admin_credentials,
    dashboard_data,
):
    future = dashboard_data["now"] + timedelta(days=30)
    response = await client.get(
        "/api/v1/dashboard/overview",
        params={"from": future.isoformat()},
        headers=await _headers(client, admin_credentials),
    )
    data = response.json()["data"]
    assert data["ticket_counts"]["total"] == 0
    assert data["average_first_response_minutes"] is None
    assert data["average_resolution_minutes"] is None
    assert data["sla_compliance"]["compliance_rate"] is None
    assert data["satisfaction"]["average_score"] is None


async def test_dashboard_rejects_invalid_time_range(
    client,
    admin_credentials,
    dashboard_data,
):
    now = dashboard_data["now"]
    response = await client.get(
        "/api/v1/dashboard/overview",
        params={
            "from": now.isoformat(),
            "to": (now - timedelta(days=1)).isoformat(),
        },
        headers=await _headers(client, admin_credentials),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_dashboard_requires_timezone_and_positive_filter_ids(
    client,
    admin_credentials,
    dashboard_data,
):
    headers = await _headers(client, admin_credentials)
    naive_time = await client.get(
        "/api/v1/dashboard/overview",
        params={"from": "2026-09-04T08:00:00"},
        headers=headers,
    )
    invalid_id = await client.get(
        "/api/v1/dashboard/overview",
        params={"category_id": 0},
        headers=headers,
    )
    assert naive_time.status_code == 422
    assert invalid_id.status_code == 422
