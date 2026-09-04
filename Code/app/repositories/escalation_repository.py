from datetime import datetime

from sqlalchemy import exists, false, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notification import Notification
from app.models.role import Role
from app.models.sla_event import SLAEvent
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_sla import TicketSLA
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.escalation import SLABreachQuery


def _event_insert(session: AsyncSession):
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        return insert(SLAEvent)
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        return insert(SLAEvent)
    return None


def _notification_insert(session: AsyncSession):
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        return insert(Notification)
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        return insert(Notification)
    return None


async def list_worker_candidates(session: AsyncSession) -> list[TicketSLA]:
    result = await session.execute(
        select(TicketSLA)
        .where(TicketSLA.runtime_status == "RUNNING")
        .options(
            selectinload(TicketSLA.policy),
            selectinload(TicketSLA.ticket).selectinload(Ticket.priority),
            selectinload(TicketSLA.ticket)
            .selectinload(
                Ticket.assignments.and_(TicketAssignment.is_current.is_(True))
            )
            .selectinload(TicketAssignment.assignee),
        )
        .order_by(TicketSLA.due_at, TicketSLA.ticket_sla_id)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars().all())


async def list_active_admins(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User)
        .join(UserRole, UserRole.user_id == User.user_id)
        .join(Role, Role.role_id == UserRole.role_id)
        .where(
            User.is_active.is_(True),
            Role.role_code == "ADMIN",
            Role.is_active.is_(True),
        )
        .order_by(User.user_id)
    )
    return list(result.scalars().unique().all())


async def create_event_if_absent(
    session: AsyncSession,
    *,
    ticket_sla_id: int,
    event_type: str,
    threshold_percent: int,
    triggered_at: datetime,
) -> SLAEvent | None:
    insert_statement = _event_insert(session)
    values = {
        "ticket_sla_id": ticket_sla_id,
        "event_type": event_type,
        "threshold_percent": threshold_percent,
        "triggered_at": triggered_at,
    }
    if insert_statement is not None:
        result = await session.execute(
            insert_statement.values(**values)
            .on_conflict_do_nothing(
                index_elements=["ticket_sla_id", "event_type"]
            )
            .returning(SLAEvent.sla_event_id)
        )
        event_id = result.scalar_one_or_none()
        return await session.get(SLAEvent, event_id) if event_id is not None else None

    try:
        async with session.begin_nested():
            event = SLAEvent(**values)
            session.add(event)
            await session.flush()
        return event
    except IntegrityError:
        return None


async def create_notification_if_absent(
    session: AsyncSession,
    *,
    recipient_id: int,
    ticket_id: int,
    sla_event_id: int,
    notification_type: str,
    title: str,
    message: str,
    created_at: datetime,
) -> int | None:
    insert_statement = _notification_insert(session)
    values = {
        "recipient_id": recipient_id,
        "ticket_id": ticket_id,
        "sla_event_id": sla_event_id,
        "notification_type": notification_type,
        "title": title,
        "message": message,
        "is_read": False,
        "created_at": created_at,
    }
    if insert_statement is not None:
        result = await session.execute(
            insert_statement.values(**values)
            .on_conflict_do_nothing(
                index_elements=[
                    "recipient_id",
                    "sla_event_id",
                    "notification_type",
                ]
            )
            .returning(Notification.notification_id)
        )
        return result.scalar_one_or_none()

    try:
        async with session.begin_nested():
            notification = Notification(**values)
            session.add(notification)
            await session.flush()
        return notification.notification_id
    except IntegrityError:
        return None


def _list_conditions(
    query: SLABreachQuery,
    *,
    current_user_id: int,
    role_codes: set[str],
):
    conditions = []
    if "ADMIN" not in role_codes:
        if "PROCESSOR" in role_codes:
            conditions.append(
                exists().where(
                    TicketAssignment.ticket_id == Ticket.ticket_id,
                    TicketAssignment.assignee_id == current_user_id,
                    TicketAssignment.is_current.is_(True),
                )
            )
        else:
            conditions.append(false())
    if query.state:
        conditions.append(SLAEvent.event_type.in_(query.state))
    if query.sla_type is not None:
        conditions.append(TicketSLA.sla_type == query.sla_type)
    if query.ticket_id is not None:
        conditions.append(Ticket.ticket_id == query.ticket_id)
    if query.triggered_from is not None:
        conditions.append(SLAEvent.triggered_at >= query.triggered_from)
    if query.triggered_to is not None:
        conditions.append(SLAEvent.triggered_at <= query.triggered_to)
    return conditions


async def list_events(
    session: AsyncSession,
    *,
    query: SLABreachQuery,
    current_user_id: int,
    role_codes: set[str],
) -> tuple[list[SLAEvent], int]:
    conditions = _list_conditions(
        query,
        current_user_id=current_user_id,
        role_codes=role_codes,
    )
    joins = (
        select(SLAEvent)
        .join(TicketSLA, TicketSLA.ticket_sla_id == SLAEvent.ticket_sla_id)
        .join(Ticket, Ticket.ticket_id == TicketSLA.ticket_id)
    )
    total = await session.scalar(
        select(func.count(SLAEvent.sla_event_id))
        .join(TicketSLA, TicketSLA.ticket_sla_id == SLAEvent.ticket_sla_id)
        .join(Ticket, Ticket.ticket_id == TicketSLA.ticket_id)
        .where(*conditions)
    )
    result = await session.execute(
        joins.where(*conditions)
        .options(
            selectinload(SLAEvent.ticket_sla)
            .selectinload(TicketSLA.ticket)
            .selectinload(Ticket.priority),
            selectinload(SLAEvent.ticket_sla)
            .selectinload(TicketSLA.ticket)
            .selectinload(
                Ticket.assignments.and_(TicketAssignment.is_current.is_(True))
            )
            .selectinload(TicketAssignment.assignee),
            selectinload(SLAEvent.notifications).selectinload(
                Notification.recipient
            ),
        )
        .order_by(SLAEvent.triggered_at.desc(), SLAEvent.sla_event_id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars().unique().all()), int(total or 0)
