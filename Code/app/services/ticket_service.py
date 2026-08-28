from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.user import User
from app.repositories import ticket_repository
from app.schemas.ticket import TicketCreateRequest, TicketDetail


def generate_ticket_code() -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid4().hex[:12].upper()
    return f"TK-{date_part}-{random_part}"


async def create_ticket(
    session: AsyncSession,
    *,
    requester: User,
    payload: TicketCreateRequest,
) -> TicketDetail:
    category = await ticket_repository.get_category_by_id(
        session,
        payload.category_id,
    )
    if category is None:
        raise AppError(404, "CATEGORY_NOT_FOUND", "Không tìm thấy danh mục.")
    if not category.is_active:
        raise AppError(409, "CATEGORY_INACTIVE", "Danh mục đã ngừng sử dụng.")

    priority = await ticket_repository.get_priority_by_id(
        session,
        payload.priority_id,
    )
    if priority is None:
        raise AppError(404, "PRIORITY_NOT_FOUND", "Không tìm thấy mức ưu tiên.")
    if not priority.is_active:
        raise AppError(409, "PRIORITY_INACTIVE", "Mức ưu tiên đã ngừng sử dụng.")

    if await ticket_repository.get_status_by_code(session, "NEW") is None:
        raise AppError(
            500,
            "TICKET_STATUS_CONFIGURATION_ERROR",
            "Hệ thống chưa cấu hình trạng thái NEW.",
        )

    try:
        ticket = await ticket_repository.create_ticket_record(
            session,
            ticket_code=generate_ticket_code(),
            requester_id=requester.user_id,
            category_id=payload.category_id,
            priority_id=payload.priority_id,
            title=payload.title,
            description=payload.description,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "TICKET_CODE_CONFLICT",
            "Không thể sinh mã ticket duy nhất. Vui lòng thử lại.",
        ) from exc

    created = await ticket_repository.get_ticket_by_id(session, ticket.ticket_id)
    if created is None:
        raise AppError(
            500,
            "INTERNAL_SERVER_ERROR",
            "Không thể tải ticket vừa tạo.",
        )
    return TicketDetail.model_validate(created)
