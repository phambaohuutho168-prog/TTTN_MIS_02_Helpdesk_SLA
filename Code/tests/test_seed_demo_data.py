from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.category import Category
from app.models.priority import Priority
from app.models.rating import Rating
from app.models.role import Role
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_resolution import TicketResolution
from app.models.ticket_sla import TicketSLA
from app.models.ticket_status import TicketStatus
from app.models.ticket_status_history import TicketStatusHistory
from app.models.user import User
from app.models.user_role import UserRole
from app.services.sla_service import build_sla_summary
from scripts import seed_demo_data
from scripts.seed_demo_data import DEMO_SCENARIOS, seed_demo_dataset
from scripts.seed_initial_data import (
    CATEGORY_SEEDS,
    PRIORITY_SEEDS,
    ROLE_SEEDS,
    SLA_POLICY_SEEDS,
    STATUS_SEEDS,
)


DEMO_NOW = datetime(2026, 9, 5, 7, 0, tzinfo=timezone.utc)
ADMIN_EMAIL = "admin.demo.seed@example.com"
DEMO_PASSWORD = "LocalDemoPassword123!"


async def _seed_reference_rows(session):
    roles = {}
    for role_code, role_name, description in ROLE_SEEDS:
        role = Role(
            role_code=role_code,
            role_name=role_name,
            description=description,
            is_active=True,
        )
        session.add(role)
        roles[role_code] = role
    categories = [
        Category(category_name=name, description=description, is_active=True)
        for name, description in CATEGORY_SEEDS
    ]
    priorities = [
        Priority(
            priority_code=code,
            priority_level=level,
            priority_name=name,
            description=description,
            is_active=True,
        )
        for code, level, name, description in PRIORITY_SEEDS
    ]
    statuses = [
        TicketStatus(
            status_code=code,
            status_name=name,
            is_terminal=is_terminal,
            description=description,
        )
        for code, name, is_terminal, description in STATUS_SEEDS
    ]
    session.add_all(categories + priorities + statuses)
    await session.flush()

    priority_by_code = {priority.priority_code: priority for priority in priorities}
    for code, response_minutes, resolution_minutes in SLA_POLICY_SEEDS:
        session.add(
            SLAPolicy(
                priority_id=priority_by_code[code].priority_id,
                version_no=1,
                response_target_minutes=response_minutes,
                resolution_target_minutes=resolution_minutes,
                warning_percent=80,
                escalation_percent=150,
                effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                is_active=True,
            )
        )
    admin = User(
        email=ADMIN_EMAIL,
        full_name="Admin Demo Seed",
        password_hash="not-used-in-this-test",
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    session.add(
        UserRole(
            user_id=admin.user_id,
            role_id=roles["ADMIN"].role_id,
        )
    )
    await session.commit()


@pytest.fixture
async def demo_database(session_factory, monkeypatch):
    monkeypatch.setattr(
        seed_demo_data,
        "hash_password",
        lambda value: f"test-hash:{value}",
    )
    async with session_factory() as session:
        await _seed_reference_rows(session)
        result = await seed_demo_dataset(
            session,
            admin_email=ADMIN_EMAIL,
            demo_password=DEMO_PASSWORD,
            now=DEMO_NOW,
        )
        await session.commit()
    return {"factory": session_factory, "result": result}


async def test_seed_creates_all_required_demo_scenarios(demo_database):
    async with demo_database["factory"]() as session:
        rows = (
            await session.execute(
                select(Ticket.ticket_code, Ticket.current_status_code).where(
                    Ticket.ticket_code.like("DEMO-%")
                )
            )
        ).all()
    assert demo_database["result"] == {"created": 6, "skipped": 0, "total": 6}
    assert dict(rows) == {
        "DEMO-NORMAL-001": "IN_PROGRESS",
        "DEMO-NEAR-DUE-001": "IN_PROGRESS",
        "DEMO-OVERDUE-001": "IN_PROGRESS",
        "DEMO-CLOSED-001": "CLOSED",
        "DEMO-REOPENED-001": "REOPENED",
        "DEMO-REJECTED-001": "REJECTED",
    }


async def test_seed_sla_records_cover_normal_near_due_overdue_and_met(demo_database):
    async with demo_database["factory"]() as session:
        tickets = (
            await session.scalars(
                select(Ticket)
                .where(Ticket.ticket_code.like("DEMO-%"))
                .options(
                    selectinload(Ticket.sla_records).selectinload(TicketSLA.policy)
                )
            )
        ).all()
    actual = {
        ticket.ticket_code: build_sla_summary(ticket, now=DEMO_NOW).overall_status.code
        for ticket in tickets
    }
    assert actual == {
        "DEMO-NORMAL-001": "ON_TRACK",
        "DEMO-NEAR-DUE-001": "NEAR_DUE",
        "DEMO-OVERDUE-001": "OVERDUE",
        "DEMO-CLOSED-001": "MET",
        "DEMO-REOPENED-001": "ON_TRACK",
        "DEMO-REJECTED-001": "NOT_APPLICABLE",
    }


async def test_near_due_and_overdue_deadlines_are_relative_to_seed_time(demo_database):
    async with demo_database["factory"]() as session:
        rows = (
            await session.execute(
                select(Ticket.ticket_code, TicketSLA.due_at)
                .join(TicketSLA, TicketSLA.ticket_id == Ticket.ticket_id)
                .where(
                    Ticket.ticket_code.in_(
                        ("DEMO-NEAR-DUE-001", "DEMO-OVERDUE-001")
                    ),
                    TicketSLA.sla_type == "RESOLUTION",
                    TicketSLA.cycle_no == 1,
                )
            )
        ).all()
    due_by_code = {
        code: due_at.replace(tzinfo=due_at.tzinfo or timezone.utc)
        for code, due_at in rows
    }
    assert (due_by_code["DEMO-NEAR-DUE-001"] - DEMO_NOW).total_seconds() == 4 * 3600
    assert (due_by_code["DEMO-OVERDUE-001"] - DEMO_NOW).total_seconds() == -2 * 3600


async def test_closed_reopened_and_rejected_business_evidence_is_coherent(demo_database):
    async with demo_database["factory"]() as session:
        tickets = {
            item.ticket_code: item
            for item in (
                await session.scalars(
                    select(Ticket).where(Ticket.ticket_code.like("DEMO-%"))
                )
            ).all()
        }
        reopened_history = (
            await session.scalars(
                select(TicketStatusHistory.to_status_code)
                .where(
                    TicketStatusHistory.ticket_id
                    == tickets["DEMO-REOPENED-001"].ticket_id
                )
                .order_by(TicketStatusHistory.changed_at)
            )
        ).all()
        resolution_count = await session.scalar(
            select(func.count(TicketResolution.resolution_id)).where(
                TicketResolution.ticket_id.in_(
                    (
                        tickets["DEMO-CLOSED-001"].ticket_id,
                        tickets["DEMO-REOPENED-001"].ticket_id,
                    )
                )
            )
        )
        rating = await session.scalar(
            select(Rating).where(
                Rating.ticket_id == tickets["DEMO-CLOSED-001"].ticket_id
            )
        )
    assert reopened_history[-2:] == ["CLOSED", "REOPENED"]
    assert resolution_count == 2
    assert rating.score == 5
    assert tickets["DEMO-CLOSED-001"].closed_at is not None
    assert tickets["DEMO-REOPENED-001"].closed_at is None
    assert tickets["DEMO-REJECTED-001"].rejection_reason


async def test_processor_is_assigned_to_every_non_rejected_demo_ticket(demo_database):
    async with demo_database["factory"]() as session:
        current_assignments = await session.scalar(
            select(func.count(TicketAssignment.assignment_id)).where(
                TicketAssignment.is_current.is_(True)
            )
        )
        processor = await session.scalar(
            select(User).where(User.email == seed_demo_data.DEMO_PROCESSOR_EMAIL)
        )
        requester = await session.scalar(
            select(User).where(User.email == seed_demo_data.DEMO_REQUESTER_EMAIL)
        )
    assert current_assignments == 5
    assert processor.department_id is not None
    assert requester.department_id is None


async def test_demo_seed_is_idempotent(demo_database):
    async with demo_database["factory"]() as session:
        second_result = await seed_demo_dataset(
            session,
            admin_email=ADMIN_EMAIL,
            demo_password=DEMO_PASSWORD,
            now=DEMO_NOW,
        )
        await session.commit()
        ticket_count = await session.scalar(
            select(func.count(Ticket.ticket_id)).where(Ticket.ticket_code.like("DEMO-%"))
        )
    assert second_result == {"created": 0, "skipped": len(DEMO_SCENARIOS), "total": 6}
    assert ticket_count == 6
