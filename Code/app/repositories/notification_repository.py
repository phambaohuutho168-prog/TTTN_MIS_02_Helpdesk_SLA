from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.schemas.notification import NotificationListQuery


async def create_notification_record(
    session: AsyncSession,
    *,
    recipient_id: int,
    ticket_id: int | None,
    notification_type: str,
    title: str,
    message: str,
    created_at: datetime,
    sla_event_id: int | None = None,
) -> Notification:
    notification = Notification(
        recipient_id=recipient_id,
        ticket_id=ticket_id,
        sla_event_id=sla_event_id,
        notification_type=notification_type,
        title=title,
        message=message,
        is_read=False,
        created_at=created_at,
    )
    session.add(notification)
    await session.flush()
    return notification


def _list_conditions(
    query: NotificationListQuery,
    *,
    recipient_id: int,
):
    conditions = [Notification.recipient_id == recipient_id]
    if query.is_read is not None:
        conditions.append(Notification.is_read.is_(query.is_read))
    if query.type is not None:
        conditions.append(Notification.notification_type == query.type)
    return conditions


async def list_notifications(
    session: AsyncSession,
    *,
    recipient_id: int,
    query: NotificationListQuery,
) -> tuple[list[Notification], int]:
    conditions = _list_conditions(query, recipient_id=recipient_id)
    total = await session.scalar(
        select(func.count(Notification.notification_id)).where(*conditions)
    )
    result = await session.execute(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc(), Notification.notification_id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    return list(result.scalars().all()), int(total or 0)


async def get_owned_notification_for_update(
    session: AsyncSession,
    *,
    notification_id: int,
    recipient_id: int,
) -> Notification | None:
    result = await session.execute(
        select(Notification)
        .where(
            Notification.notification_id == notification_id,
            Notification.recipient_id == recipient_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def mark_all_read(
    session: AsyncSession,
    *,
    recipient_id: int,
    notification_type: str | None,
    read_at: datetime,
) -> int:
    conditions = [
        Notification.recipient_id == recipient_id,
        Notification.is_read.is_(False),
    ]
    if notification_type is not None:
        conditions.append(Notification.notification_type == notification_type)
    result = await session.execute(
        update(Notification)
        .where(*conditions)
        .values(is_read=True, read_at=read_at)
    )
    return int(result.rowcount or 0)
