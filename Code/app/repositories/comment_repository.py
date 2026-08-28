from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attachment import Attachment
from app.models.audit_log import AuditLog
from app.models.comment import Comment
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_sla import TicketSLA
from app.models.user import User
from app.models.user_role import UserRole


COMMENT_LOAD_OPTIONS = (
    selectinload(Comment.author)
    .selectinload(User.user_roles)
    .selectinload(UserRole.role),
    selectinload(Comment.attachments).selectinload(Attachment.uploader),
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def get_ticket_for_comment_write(
    session: AsyncSession,
    *,
    ticket_id: int,
) -> Ticket | None:
    result = await session.execute(
        select(Ticket)
        .where(Ticket.ticket_id == ticket_id)
        .options(
            selectinload(Ticket.current_status),
            selectinload(Ticket.assignments)
            .selectinload(TicketAssignment.assignee)
            .selectinload(User.user_roles)
            .selectinload(UserRole.role),
            selectinload(Ticket.sla_records),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def create_comment_record(
    session: AsyncSession,
    *,
    ticket_id: int,
    author_id: int,
    content: str,
    visibility: str,
    comment_type: str,
    created_at: datetime,
) -> Comment:
    comment = Comment(
        ticket_id=ticket_id,
        author_id=author_id,
        content=content,
        visibility=visibility,
        comment_type=comment_type,
        created_at=created_at,
    )
    session.add(comment)
    await session.flush()
    return comment


async def get_comment_by_id(
    session: AsyncSession,
    comment_id: int,
) -> Comment | None:
    result = await session.execute(
        select(Comment)
        .where(Comment.comment_id == comment_id)
        .options(*COMMENT_LOAD_OPTIONS)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def get_comment_for_update(
    session: AsyncSession,
    *,
    comment_id: int,
) -> Comment | None:
    result = await session.execute(
        select(Comment)
        .where(Comment.comment_id == comment_id)
        .options(
            *COMMENT_LOAD_OPTIONS,
            selectinload(Comment.ticket).selectinload(Ticket.current_status),
            selectinload(Comment.ticket)
            .selectinload(Ticket.assignments)
            .selectinload(TicketAssignment.assignee),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def create_comment_audit_record(
    session: AsyncSession,
    *,
    actor_user_id: int,
    ticket_id: int,
    comment_id: int,
    action_code: str,
    old_value: dict | None,
    new_value: dict,
    ip_address: str | None,
) -> AuditLog:
    audit = AuditLog(
        actor_user_id=actor_user_id,
        ticket_id=ticket_id,
        action_code=action_code,
        entity_type="COMMENT",
        entity_id=comment_id,
        old_value_json=old_value,
        new_value_json=new_value,
        ip_address=ip_address,
    )
    session.add(audit)
    await session.flush()
    return audit


def complete_response_sla(
    ticket: Ticket,
    *,
    completed_at: datetime,
) -> TicketSLA | None:
    candidates = [
        record
        for record in ticket.sla_records
        if record.sla_type == "RESPONSE" and record.runtime_status == "RUNNING"
    ]
    record = max(candidates, key=lambda item: item.cycle_no, default=None)
    if record is None:
        return None
    record.completed_at = completed_at
    record.runtime_status = "COMPLETED"
    record.result = "MET" if completed_at <= _as_utc(record.due_at) else "BREACHED"
    record.updated_at = completed_at
    return record
