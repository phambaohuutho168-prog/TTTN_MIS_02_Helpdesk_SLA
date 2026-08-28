from sqlalchemy import Select, exists, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.category import Category
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_status import TicketStatus
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.ticket import TicketListQuery


TICKET_LOAD_OPTIONS = (
    selectinload(Ticket.category),
    selectinload(Ticket.priority),
    selectinload(Ticket.current_status),
    selectinload(Ticket.requester)
    .selectinload(User.user_roles)
    .selectinload(UserRole.role),
    selectinload(
        Ticket.assignments.and_(TicketAssignment.is_current.is_(True))
    )
    .selectinload(TicketAssignment.assignee)
    .selectinload(User.user_roles)
    .selectinload(UserRole.role),
)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _list_conditions(
    query: TicketListQuery,
    *,
    current_user_id: int,
    role_codes: set[str],
):
    conditions = []
    if "ADMIN" not in role_codes:
        scope_conditions = []
        if "REQUESTER" in role_codes:
            scope_conditions.append(Ticket.requester_id == current_user_id)
        if "PROCESSOR" in role_codes:
            scope_conditions.append(
                exists().where(
                    TicketAssignment.ticket_id == Ticket.ticket_id,
                    TicketAssignment.assignee_id == current_user_id,
                    TicketAssignment.is_current.is_(True),
                )
            )
        conditions.append(or_(*scope_conditions) if scope_conditions else false())

    if query.status:
        conditions.append(Ticket.current_status_code.in_(query.status))
    if query.category_id is not None:
        conditions.append(Ticket.category_id == query.category_id)
    if query.priority_id is not None:
        conditions.append(Ticket.priority_id == query.priority_id)
    if query.requester_id is not None:
        conditions.append(Ticket.requester_id == query.requester_id)
    if query.assignee_id is not None:
        conditions.append(
            exists().where(
                TicketAssignment.ticket_id == Ticket.ticket_id,
                TicketAssignment.assignee_id == query.assignee_id,
                TicketAssignment.is_current.is_(True),
            )
        )
    if query.created_from is not None:
        conditions.append(Ticket.created_at >= query.created_from)
    if query.created_to is not None:
        conditions.append(Ticket.created_at <= query.created_to)
    if query.q:
        pattern = f"%{_escape_like(query.q.lower())}%"
        conditions.append(
            or_(
                func.lower(Ticket.ticket_code).like(pattern, escape="\\"),
                func.lower(Ticket.title).like(pattern, escape="\\"),
            )
        )
    return conditions


def _apply_sort(statement: Select, sort: str) -> Select:
    sort_map = {
        "created_at": Ticket.created_at.asc(),
        "-created_at": Ticket.created_at.desc(),
        "updated_at": Ticket.updated_at.asc(),
        "-updated_at": Ticket.updated_at.desc(),
        "priority_level": Priority.priority_level.asc(),
        "-priority_level": Priority.priority_level.desc(),
    }
    if sort in {"priority_level", "-priority_level"}:
        statement = statement.join(Priority, Ticket.priority_id == Priority.priority_id)
    return statement.order_by(sort_map[sort], Ticket.ticket_id.desc())


async def get_existing_status_codes(
    session: AsyncSession,
    status_codes: list[str],
) -> set[str]:
    result = await session.execute(
        select(TicketStatus.status_code).where(
            TicketStatus.status_code.in_(status_codes)
        )
    )
    return set(result.scalars().all())


async def list_tickets(
    session: AsyncSession,
    *,
    query: TicketListQuery,
    current_user_id: int,
    role_codes: set[str],
) -> tuple[list[Ticket], int]:
    conditions = _list_conditions(
        query,
        current_user_id=current_user_id,
        role_codes=role_codes,
    )
    total = await session.scalar(
        select(func.count(Ticket.ticket_id)).where(*conditions)
    )
    statement = (
        select(Ticket)
        .where(*conditions)
        .options(*TICKET_LOAD_OPTIONS)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
        .execution_options(populate_existing=True)
    )
    statement = _apply_sort(statement, query.sort)
    result = await session.execute(statement)
    return list(result.scalars().all()), int(total or 0)


async def get_category_by_id(
    session: AsyncSession,
    category_id: int,
) -> Category | None:
    return await session.get(Category, category_id)


async def get_priority_by_id(
    session: AsyncSession,
    priority_id: int,
) -> Priority | None:
    return await session.get(Priority, priority_id)


async def get_status_by_code(
    session: AsyncSession,
    status_code: str,
) -> TicketStatus | None:
    return await session.get(TicketStatus, status_code)


async def create_ticket_record(
    session: AsyncSession,
    *,
    ticket_code: str,
    requester_id: int,
    category_id: int,
    priority_id: int,
    title: str,
    description: str,
) -> Ticket:
    ticket = Ticket(
        ticket_code=ticket_code,
        requester_id=requester_id,
        category_id=category_id,
        priority_id=priority_id,
        current_status_code="NEW",
        title=title,
        description=description,
    )
    session.add(ticket)
    await session.flush()
    return ticket


async def get_ticket_by_id(
    session: AsyncSession,
    ticket_id: int,
) -> Ticket | None:
    result = await session.execute(
        select(Ticket)
        .where(Ticket.ticket_id == ticket_id)
        .options(*TICKET_LOAD_OPTIONS)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()
