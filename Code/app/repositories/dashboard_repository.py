from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.priority import Priority
from app.models.rating import Rating
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_resolution import TicketResolution
from app.models.ticket_sla import TicketSLA
from app.models.ticket_status import TicketStatus
from app.models.ticket_status_history import TicketStatusHistory
from app.models.user import User
from app.schemas.dashboard import DashboardQuery


def _current_assignment_scope(user_id: int):
    return exists(
        select(1)
        .select_from(TicketAssignment)
        .where(
            TicketAssignment.ticket_id == Ticket.ticket_id,
            TicketAssignment.assignee_id == user_id,
            TicketAssignment.is_current.is_(True),
        )
    )


def _department_scope(department_id: int):
    return exists(
        select(1)
        .select_from(TicketAssignment)
        .join(User, User.user_id == TicketAssignment.assignee_id)
        .where(
            TicketAssignment.ticket_id == Ticket.ticket_id,
            TicketAssignment.is_current.is_(True),
            User.department_id == department_id,
        )
    )


def ticket_conditions(
    query: DashboardQuery,
    *,
    current_user_id: int,
    role_codes: set[str],
    include_created_period: bool = True,
):
    conditions = []
    if "ADMIN" not in role_codes:
        conditions.append(_current_assignment_scope(current_user_id))
    if include_created_period and query.date_from is not None:
        conditions.append(Ticket.created_at >= query.date_from)
    if include_created_period and query.date_to is not None:
        conditions.append(Ticket.created_at <= query.date_to)
    if query.category_id is not None:
        conditions.append(Ticket.category_id == query.category_id)
    if query.priority_id is not None:
        conditions.append(Ticket.priority_id == query.priority_id)
    if query.department_id is not None:
        conditions.append(_department_scope(query.department_id))
    if query.assignee_id is not None:
        conditions.append(_current_assignment_scope(query.assignee_id))
    return conditions


async def status_counts(
    session: AsyncSession,
    *,
    conditions,
):
    result = await session.execute(
        select(
            Ticket.current_status_code,
            TicketStatus.status_name,
            TicketStatus.is_terminal,
            func.count(Ticket.ticket_id),
        )
        .join(
            TicketStatus,
            TicketStatus.status_code == Ticket.current_status_code,
        )
        .where(*conditions)
        .group_by(
            Ticket.current_status_code,
            TicketStatus.status_name,
            TicketStatus.is_terminal,
        )
    )
    return list(result.all())


async def category_counts(
    session: AsyncSession,
    *,
    conditions,
):
    result = await session.execute(
        select(
            Category.category_id,
            Category.category_name,
            func.count(Ticket.ticket_id),
        )
        .join(Category, Category.category_id == Ticket.category_id)
        .where(*conditions)
        .group_by(Category.category_id, Category.category_name)
    )
    return list(result.all())


async def priority_counts(
    session: AsyncSession,
    *,
    conditions,
):
    result = await session.execute(
        select(
            Priority.priority_id,
            Priority.priority_code,
            Priority.priority_name,
            func.count(Ticket.ticket_id),
        )
        .join(Priority, Priority.priority_id == Ticket.priority_id)
        .where(*conditions)
        .group_by(
            Priority.priority_id,
            Priority.priority_code,
            Priority.priority_name,
        )
    )
    return list(result.all())


async def ticket_duration_rows(
    session: AsyncSession,
    *,
    conditions,
) -> list[tuple[datetime, datetime | None, datetime | None]]:
    latest_resolution = (
        select(
            TicketResolution.ticket_id.label("ticket_id"),
            func.max(TicketResolution.resolved_at).label("resolved_at"),
        )
        .group_by(TicketResolution.ticket_id)
        .subquery()
    )
    result = await session.execute(
        select(
            Ticket.created_at,
            Ticket.first_response_at,
            latest_resolution.c.resolved_at,
        )
        .outerjoin(
            latest_resolution,
            latest_resolution.c.ticket_id == Ticket.ticket_id,
        )
        .where(*conditions)
    )
    return list(result.tuples().all())


async def reopened_ticket_count(
    session: AsyncSession,
    *,
    conditions,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> int:
    event_conditions = [TicketStatusHistory.to_status_code == "REOPENED"]
    if date_from is not None:
        event_conditions.append(TicketStatusHistory.changed_at >= date_from)
    if date_to is not None:
        event_conditions.append(TicketStatusHistory.changed_at <= date_to)
    value = await session.scalar(
        select(func.count(func.distinct(Ticket.ticket_id)))
        .join(
            TicketStatusHistory,
            TicketStatusHistory.ticket_id == Ticket.ticket_id,
        )
        .where(
            *conditions,
            *event_conditions,
        )
    )
    return int(value or 0)


async def rating_scores(
    session: AsyncSession,
    *,
    conditions,
) -> list[int]:
    result = await session.execute(
        select(Rating.score)
        .join(Ticket, Ticket.ticket_id == Rating.ticket_id)
        .where(*conditions)
    )
    return [int(score) for score in result.scalars().all()]


async def sla_result_rows(
    session: AsyncSession,
    *,
    conditions,
) -> list[tuple[int, datetime, str, str]]:
    result = await session.execute(
        select(
            Ticket.ticket_id,
            Ticket.created_at,
            TicketSLA.sla_type,
            TicketSLA.result,
        )
        .join(Ticket, Ticket.ticket_id == TicketSLA.ticket_id)
        .where(
            *conditions,
            TicketSLA.result.in_(("MET", "BREACHED", "NOT_APPLICABLE")),
        )
    )
    return [
        (ticket_id, created_at, sla_type, result_code)
        for ticket_id, created_at, sla_type, result_code in result.tuples().all()
    ]
