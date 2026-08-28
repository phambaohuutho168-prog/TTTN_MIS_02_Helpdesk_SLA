from datetime import datetime, timezone
from math import ceil
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rbac import RoleCode
from app.models.user import User
from app.repositories import ticket_repository
from app.schemas.common import PageData
from app.schemas.ticket import (
    CategoryBrief,
    PriorityBrief,
    TicketCreateRequest,
    TicketDetail,
    TicketListQuery,
    TicketStatusBrief,
    TicketSummaryResponse,
    TicketUserBrief,
)


def generate_ticket_code() -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = uuid4().hex[:12].upper()
    return f"TK-{date_part}-{random_part}"


def _build_ticket_summary(ticket) -> TicketSummaryResponse:
    current_assignment = ticket.current_assignment
    current_assignee = (
        TicketUserBrief.model_validate(current_assignment.assignee)
        if current_assignment is not None and current_assignment.assignee is not None
        else None
    )
    return TicketSummaryResponse(
        ticket_id=ticket.ticket_id,
        ticket_code=ticket.ticket_code,
        title=ticket.title,
        category=CategoryBrief.model_validate(ticket.category),
        priority=PriorityBrief.model_validate(ticket.priority),
        status=TicketStatusBrief.model_validate(ticket.current_status),
        requester=TicketUserBrief.model_validate(ticket.requester),
        current_assignee=current_assignee,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


async def list_tickets(
    session: AsyncSession,
    *,
    current_user: User,
    query: TicketListQuery,
) -> PageData[TicketSummaryResponse]:
    role_codes = set(current_user.role_codes)
    is_admin = RoleCode.ADMIN.value in role_codes
    is_processor = RoleCode.PROCESSOR.value in role_codes

    if query.requester_id is not None and not is_admin:
        raise AppError(
            403,
            "FORBIDDEN_ACTION",
            "Chỉ Admin được lọc ticket theo requester_id.",
        )
    if query.assignee_id is not None and not (is_admin or is_processor):
        raise AppError(
            403,
            "FORBIDDEN_ACTION",
            "Vai trò hiện tại không được lọc theo assignee_id.",
        )

    if query.status:
        existing = await ticket_repository.get_existing_status_codes(
            session,
            query.status,
        )
        invalid = sorted(set(query.status) - existing)
        if invalid:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "Bộ lọc trạng thái chứa mã không hợp lệ.",
                errors=[
                    {
                        "field": "status",
                        "message": f"Mã trạng thái không tồn tại: {', '.join(invalid)}",
                    }
                ],
            )

    tickets, total = await ticket_repository.list_tickets(
        session,
        query=query,
        current_user_id=current_user.user_id,
        role_codes=role_codes,
    )
    return PageData[TicketSummaryResponse](
        items=[_build_ticket_summary(ticket) for ticket in tickets],
        page=query.page,
        page_size=query.page_size,
        total=total,
        total_pages=ceil(total / query.page_size) if total else 0,
    )


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
