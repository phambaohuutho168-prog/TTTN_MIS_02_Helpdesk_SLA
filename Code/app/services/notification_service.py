from datetime import datetime, timezone
from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.notification import Notification
from app.models.ticket import Ticket
from app.repositories import notification_repository
from app.schemas.common import PageData
from app.schemas.notification import (
    BulkUpdateResponse,
    NotificationListQuery,
    NotificationResponse,
)


STATUS_COPY = {
    "ASSIGNED": ("TICKET_ASSIGNED", "Ticket đã được phân công"),
    "IN_PROGRESS": ("TICKET_IN_PROGRESS", "Ticket đang được xử lý"),
    "PENDING_INFO": ("INFO_REQUESTED", "Ticket cần bổ sung thông tin"),
    "RESOLVED": ("TICKET_RESOLVED", "Ticket đã được xử lý"),
    "CLOSED": ("TICKET_CLOSED", "Ticket đã được đóng"),
    "REOPENED": ("TICKET_REOPENED", "Ticket đã được mở lại"),
    "REJECTED": ("TICKET_REJECTED", "Ticket đã bị từ chối"),
}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _response(notification: Notification) -> NotificationResponse:
    created_at = _as_utc(notification.created_at)
    read_at = (
        _as_utc(notification.read_at)
        if notification.read_at is not None
        else None
    )
    return NotificationResponse(
        notification_id=notification.notification_id,
        ticket_id=notification.ticket_id,
        sla_event_id=notification.sla_event_id,
        type=notification.notification_type,
        title=notification.title,
        message=notification.message,
        is_read=notification.is_read,
        deep_link=(
            f"/tickets/{notification.ticket_id}"
            if notification.ticket_id is not None
            else None
        ),
        created_at=created_at,
        read_at=read_at,
        updated_at=read_at or created_at,
    )


async def _notify_many(
    session: AsyncSession,
    *,
    recipient_ids: set[int],
    ticket: Ticket,
    notification_type: str,
    title: str,
    message: str,
    created_at: datetime,
) -> list[Notification]:
    notifications = []
    for recipient_id in sorted(recipient_ids):
        notifications.append(
            await notification_repository.create_notification_record(
                session,
                recipient_id=recipient_id,
                ticket_id=ticket.ticket_id,
                notification_type=notification_type,
                title=title,
                message=message,
                created_at=created_at,
            )
        )
    return notifications


async def notify_assignment(
    session: AsyncSession,
    *,
    ticket: Ticket,
    assignee_id: int,
    is_reassignment: bool,
    created_at: datetime,
) -> Notification:
    action = "Tái phân công" if is_reassignment else "Phân công"
    return await notification_repository.create_notification_record(
        session,
        recipient_id=assignee_id,
        ticket_id=ticket.ticket_id,
        notification_type=(
            "TICKET_REASSIGNED" if is_reassignment else "TICKET_ASSIGNED"
        ),
        title=f"{action} ticket {ticket.ticket_code}",
        message=(
            f"Bạn đã được phân công xử lý ticket {ticket.ticket_code}."
        ),
        created_at=created_at,
    )


async def notify_status_change(
    session: AsyncSession,
    *,
    ticket: Ticket,
    actor_id: int | None,
    from_status_code: str,
    to_status_code: str,
    created_at: datetime,
) -> list[Notification]:
    notification_type, title_prefix = STATUS_COPY.get(
        to_status_code,
        ("TICKET_STATUS_CHANGED", "Trạng thái ticket đã thay đổi"),
    )
    recipient_ids = {ticket.requester_id}
    assignment = ticket.current_assignment
    if assignment is not None and to_status_code != "ASSIGNED":
        recipient_ids.add(assignment.assignee_id)
    if actor_id is not None:
        recipient_ids.discard(actor_id)
    return await _notify_many(
        session,
        recipient_ids=recipient_ids,
        ticket=ticket,
        notification_type=notification_type,
        title=f"{title_prefix}: {ticket.ticket_code}",
        message=(
            f"Ticket {ticket.ticket_code} đã chuyển từ {from_status_code} "
            f"sang {to_status_code}."
        ),
        created_at=created_at,
    )


async def notify_public_reply(
    session: AsyncSession,
    *,
    ticket: Ticket,
    actor_id: int,
    created_at: datetime,
) -> list[Notification]:
    recipient_ids: set[int] = set()
    if actor_id == ticket.requester_id:
        assignment = ticket.current_assignment
        if assignment is not None:
            recipient_ids.add(assignment.assignee_id)
    else:
        recipient_ids.add(ticket.requester_id)
    recipient_ids.discard(actor_id)
    return await _notify_many(
        session,
        recipient_ids=recipient_ids,
        ticket=ticket,
        notification_type="TICKET_REPLY",
        title=f"Phản hồi mới: {ticket.ticket_code}",
        message=f"Ticket {ticket.ticket_code} có phản hồi công khai mới.",
        created_at=created_at,
    )


async def list_notifications(
    session: AsyncSession,
    *,
    current_user_id: int,
    query: NotificationListQuery,
) -> PageData[NotificationResponse]:
    rows, total = await notification_repository.list_notifications(
        session,
        recipient_id=current_user_id,
        query=query,
    )
    return PageData[NotificationResponse](
        items=[_response(row) for row in rows],
        page=query.page,
        page_size=query.page_size,
        total=total,
        total_pages=ceil(total / query.page_size) if total else 0,
    )


async def mark_notification_read(
    session: AsyncSession,
    *,
    notification_id: int,
    current_user_id: int,
    now: datetime | None = None,
) -> NotificationResponse:
    notification = await notification_repository.get_owned_notification_for_update(
        session,
        notification_id=notification_id,
        recipient_id=current_user_id,
    )
    if notification is None:
        raise AppError(
            404,
            "NOTIFICATION_NOT_FOUND",
            "Không tìm thấy thông báo của người dùng hiện tại.",
        )
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = now or datetime.now(timezone.utc)
        await session.commit()
    return _response(notification)


async def mark_all_notifications_read(
    session: AsyncSession,
    *,
    current_user_id: int,
    notification_type: str | None,
    now: datetime | None = None,
) -> BulkUpdateResponse:
    normalized_type = (
        notification_type.strip().upper() if notification_type is not None else None
    )
    if normalized_type == "":
        normalized_type = None
    updated_count = await notification_repository.mark_all_read(
        session,
        recipient_id=current_user_id,
        notification_type=normalized_type,
        read_at=now or datetime.now(timezone.utc),
    )
    await session.commit()
    return BulkUpdateResponse(updated_count=updated_count)
