from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.user import User
from app.models.user_role import UserRole


ATTACHMENT_LOAD_OPTIONS = (
    selectinload(Attachment.ticket).selectinload(Ticket.current_status),
    selectinload(Attachment.ticket)
    .selectinload(
        Ticket.assignments.and_(TicketAssignment.is_current.is_(True))
    )
    .selectinload(TicketAssignment.assignee)
    .selectinload(User.user_roles)
    .selectinload(UserRole.role),
    selectinload(Attachment.comment),
)


async def get_comment_by_id(
    session: AsyncSession,
    comment_id: int,
) -> Comment | None:
    return await session.get(Comment, comment_id)


async def create_attachment_record(
    session: AsyncSession,
    *,
    ticket_id: int,
    comment_id: int | None,
    uploaded_by: int,
    file_name: str,
    storage_path: str,
    mime_type: str,
    file_size: int,
) -> Attachment:
    attachment = Attachment(
        ticket_id=ticket_id,
        comment_id=comment_id,
        uploaded_by=uploaded_by,
        file_name=file_name,
        storage_path=storage_path,
        mime_type=mime_type,
        file_size=file_size,
    )
    session.add(attachment)
    await session.flush()
    return attachment


async def get_attachment_by_id(
    session: AsyncSession,
    attachment_id: int,
) -> Attachment | None:
    result = await session.execute(
        select(Attachment)
        .where(Attachment.attachment_id == attachment_id)
        .options(*ATTACHMENT_LOAD_OPTIONS)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def delete_attachment_record(
    session: AsyncSession,
    attachment: Attachment,
) -> None:
    await session.delete(attachment)
