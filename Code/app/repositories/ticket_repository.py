from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.category import Category
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.ticket_status import TicketStatus


TICKET_LOAD_OPTIONS = (
    selectinload(Ticket.category),
    selectinload(Ticket.priority),
    selectinload(Ticket.current_status),
)


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
