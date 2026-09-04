from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rating import Rating
from app.models.ticket import Ticket
from app.models.user import User
from app.models.user_role import UserRole


RATING_LOAD_OPTIONS = (
    selectinload(Rating.rater)
    .selectinload(User.user_roles)
    .selectinload(UserRole.role),
)


async def get_ticket_for_rating(
    session: AsyncSession,
    *,
    ticket_id: int,
) -> Ticket | None:
    """Lock the ticket so competing submissions serialize on PostgreSQL."""

    result = await session.execute(
        select(Ticket)
        .where(Ticket.ticket_id == ticket_id)
        .options(
            selectinload(Ticket.current_status),
            selectinload(Ticket.rating),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def create_rating_record(
    session: AsyncSession,
    *,
    ticket_id: int,
    rated_by: int,
    score: int,
    comment: str | None,
    created_at: datetime,
) -> Rating:
    rating = Rating(
        ticket_id=ticket_id,
        rated_by=rated_by,
        score=score,
        comment=comment,
        created_at=created_at,
    )
    session.add(rating)
    await session.flush()
    return rating


async def get_rating_by_id(
    session: AsyncSession,
    rating_id: int,
) -> Rating | None:
    result = await session.execute(
        select(Rating)
        .where(Rating.rating_id == rating_id)
        .options(*RATING_LOAD_OPTIONS)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def get_rating_by_ticket_id(
    session: AsyncSession,
    ticket_id: int,
) -> Rating | None:
    result = await session.execute(
        select(Rating)
        .where(Rating.ticket_id == ticket_id)
        .options(*RATING_LOAD_OPTIONS)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()
