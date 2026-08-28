from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.priority import Priority
from app.models.ticket_status import TicketStatus


async def list_categories(
    session: AsyncSession,
    *,
    q: str | None,
    is_active: bool | None,
) -> list[Category]:
    statement = select(Category)
    if q:
        statement = statement.where(
            func.lower(Category.category_name).contains(q.strip().lower())
        )
    if is_active is not None:
        statement = statement.where(Category.is_active.is_(is_active))
    result = await session.execute(
        statement.order_by(func.lower(Category.category_name), Category.category_id)
    )
    return list(result.scalars().all())


async def get_category_by_id(
    session: AsyncSession,
    category_id: int,
) -> Category | None:
    return await session.get(Category, category_id)


async def get_category_by_name(
    session: AsyncSession,
    category_name: str,
) -> Category | None:
    result = await session.execute(
        select(Category).where(
            func.lower(Category.category_name) == category_name.strip().lower()
        )
    )
    return result.scalar_one_or_none()


async def create_category_record(
    session: AsyncSession,
    *,
    category_name: str,
    description: str | None,
    is_active: bool,
) -> Category:
    category = Category(
        category_name=category_name,
        description=description,
        is_active=is_active,
    )
    session.add(category)
    await session.flush()
    return category


async def list_priorities(
    session: AsyncSession,
    *,
    q: str | None,
    is_active: bool | None,
) -> list[Priority]:
    statement = select(Priority)
    if q:
        pattern = f"%{q.strip().lower()}%"
        statement = statement.where(
            func.lower(Priority.priority_code).like(pattern)
            | func.lower(Priority.priority_name).like(pattern)
        )
    if is_active is not None:
        statement = statement.where(Priority.is_active.is_(is_active))
    result = await session.execute(
        statement.order_by(Priority.priority_level, Priority.priority_id)
    )
    return list(result.scalars().all())


async def get_priority_by_id(
    session: AsyncSession,
    priority_id: int,
) -> Priority | None:
    return await session.get(Priority, priority_id)


async def get_priority_by_code(
    session: AsyncSession,
    priority_code: str,
) -> Priority | None:
    result = await session.execute(
        select(Priority).where(Priority.priority_code == priority_code.upper())
    )
    return result.scalar_one_or_none()


async def get_priority_by_level(
    session: AsyncSession,
    priority_level: int,
) -> Priority | None:
    result = await session.execute(
        select(Priority).where(Priority.priority_level == priority_level)
    )
    return result.scalar_one_or_none()


async def create_priority_record(
    session: AsyncSession,
    *,
    priority_code: str,
    priority_level: int,
    priority_name: str,
    description: str | None,
    is_active: bool,
) -> Priority:
    priority = Priority(
        priority_code=priority_code,
        priority_level=priority_level,
        priority_name=priority_name,
        description=description,
        is_active=is_active,
    )
    session.add(priority)
    await session.flush()
    return priority


async def list_ticket_statuses(session: AsyncSession) -> list[TicketStatus]:
    result = await session.execute(
        select(TicketStatus).order_by(TicketStatus.status_code)
    )
    return list(result.scalars().all())
