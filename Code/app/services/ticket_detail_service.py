from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rbac import RoleCode
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.user import User
from app.repositories import ticket_repository
from app.schemas.attachment import AttachmentResponse
from app.schemas.common import PageData
from app.schemas.ticket import (
    CategoryBrief,
    PriorityBrief,
    TicketStatusBrief,
    TicketUserBrief,
)
from app.schemas.ticket_detail import (
    AssignmentResponse,
    CommentResponse,
    StatusHistoryResponse,
    TicketDetailResponse,
    TicketResolutionResponse,
    TicketTimelineQuery,
)
from app.services import sla_service


def _role_codes(user: User) -> set[str]:
    return set(user.role_codes)


def _is_admin(user: User) -> bool:
    return RoleCode.ADMIN.value in _role_codes(user)


def _is_current_processor(ticket: Ticket, user: User) -> bool:
    return (
        RoleCode.PROCESSOR.value in _role_codes(user)
        and ticket.current_assignment is not None
        and ticket.current_assignment.assignee_id == user.user_id
    )


def _assert_ticket_scope(ticket: Ticket, user: User) -> None:
    if _is_admin(user):
        return
    if (
        RoleCode.REQUESTER.value in _role_codes(user)
        and ticket.requester_id == user.user_id
    ):
        return
    if _is_current_processor(ticket, user):
        return
    raise AppError(
        403,
        "TICKET_ACCESS_DENIED",
        "Bạn không thuộc phạm vi sở hữu hoặc phân công hiện tại của ticket.",
    )


async def _load_scoped_ticket(
    session: AsyncSession,
    *,
    ticket_id: int,
    current_user: User,
) -> Ticket:
    ticket = await ticket_repository.get_ticket_detail_by_id(session, ticket_id)
    if ticket is None:
        raise AppError(404, "TICKET_NOT_FOUND", "Không tìm thấy ticket.")
    _assert_ticket_scope(ticket, current_user)
    return ticket


async def load_scoped_ticket(
    session: AsyncSession,
    *,
    ticket_id: int,
    current_user: User,
) -> Ticket:
    """Load a ticket with all detail relations and enforce its access scope."""

    return await _load_scoped_ticket(
        session,
        ticket_id=ticket_id,
        current_user=current_user,
    )


def _assignment_response(assignment: TicketAssignment) -> AssignmentResponse:
    return AssignmentResponse(
        assignment_id=assignment.assignment_id,
        ticket_id=assignment.ticket_id,
        assignee=TicketUserBrief.model_validate(assignment.assignee),
        assigned_by=TicketUserBrief.model_validate(assignment.assigner),
        assigned_at=assignment.assigned_at,
        ended_at=assignment.ended_at,
        is_current=assignment.is_current,
        reason=assignment.reason,
    )


def _permissions(ticket: Ticket, user: User) -> list[str]:
    permissions = [
        "VIEW_DETAIL",
        "VIEW_ATTACHMENTS",
        "VIEW_STATUS_HISTORY",
    ]
    if not ticket.current_status.is_terminal:
        permissions.extend(["ADD_COMMENT", "UPLOAD_ATTACHMENT"])
    if _is_admin(user) or _is_current_processor(ticket, user):
        permissions.extend(["VIEW_INTERNAL_COMMENTS", "VIEW_ASSIGNMENT_HISTORY"])
    if _is_admin(user):
        permissions.append("ADMINISTER_TICKET")
    return permissions


async def get_ticket_detail(
    session: AsyncSession,
    *,
    ticket_id: int,
    current_user: User,
) -> TicketDetailResponse:
    ticket = await _load_scoped_ticket(
        session,
        ticket_id=ticket_id,
        current_user=current_user,
    )
    current_assignment = ticket.current_assignment
    current_assignment_response = (
        _assignment_response(current_assignment)
        if current_assignment is not None
        else None
    )
    return TicketDetailResponse(
        ticket_id=ticket.ticket_id,
        ticket_code=ticket.ticket_code,
        title=ticket.title,
        description=ticket.description,
        category=CategoryBrief.model_validate(ticket.category),
        priority=PriorityBrief.model_validate(ticket.priority),
        status=TicketStatusBrief.model_validate(ticket.current_status),
        requester=TicketUserBrief.model_validate(ticket.requester),
        current_assignee=(
            TicketUserBrief.model_validate(current_assignment.assignee)
            if current_assignment is not None
            else None
        ),
        current_assignment=current_assignment_response,
        attachments=[
            AttachmentResponse.model_validate(attachment)
            for attachment in ticket.attachments
            if attachment.comment_id is None
        ],
        resolutions=[
            TicketResolutionResponse(
                resolution_id=resolution.resolution_id,
                ticket_id=resolution.ticket_id,
                resolved_by=TicketUserBrief.model_validate(resolution.resolver),
                cycle_no=resolution.cycle_no,
                resolution_note=resolution.resolution_note,
                resolved_at=resolution.resolved_at,
            )
            for resolution in ticket.resolutions
        ],
        first_response_at=ticket.first_response_at,
        closed_at=ticket.closed_at,
        closed_by=(
            TicketUserBrief.model_validate(ticket.closer)
            if ticket.closer is not None
            else None
        ),
        rejected_at=ticket.rejected_at,
        rejection_reason=ticket.rejection_reason,
        permissions=_permissions(ticket, current_user),
        sla_summary=sla_service.build_sla_summary(ticket),
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


async def list_status_history(
    session: AsyncSession,
    *,
    ticket_id: int,
    current_user: User,
    query: TicketTimelineQuery,
) -> PageData[StatusHistoryResponse]:
    await _load_scoped_ticket(
        session,
        ticket_id=ticket_id,
        current_user=current_user,
    )
    rows, total = await ticket_repository.list_status_history(
        session,
        ticket_id=ticket_id,
        page=query.page,
        page_size=query.page_size,
    )
    return PageData[StatusHistoryResponse](
        items=[
            StatusHistoryResponse(
                history_id=row.history_id,
                ticket_id=row.ticket_id,
                from_status_code=row.from_status_code,
                to_status_code=row.to_status_code,
                changed_by=(
                    TicketUserBrief.model_validate(row.actor)
                    if row.actor is not None
                    else None
                ),
                reason=row.reason,
                changed_at=row.changed_at,
            )
            for row in rows
        ],
        page=query.page,
        page_size=query.page_size,
        total=total,
        total_pages=ceil(total / query.page_size) if total else 0,
    )


async def list_comments(
    session: AsyncSession,
    *,
    ticket_id: int,
    current_user: User,
    query: TicketTimelineQuery,
) -> PageData[CommentResponse]:
    await _load_scoped_ticket(
        session,
        ticket_id=ticket_id,
        current_user=current_user,
    )
    role_codes = _role_codes(current_user)
    include_internal = bool(
        role_codes.intersection({RoleCode.PROCESSOR.value, RoleCode.ADMIN.value})
    )
    rows, total = await ticket_repository.list_comments(
        session,
        ticket_id=ticket_id,
        include_internal=include_internal,
        page=query.page,
        page_size=query.page_size,
    )
    return PageData[CommentResponse](
        items=[
            CommentResponse(
                comment_id=row.comment_id,
                ticket_id=row.ticket_id,
                author=TicketUserBrief.model_validate(row.author),
                content=row.content,
                visibility=row.visibility,
                comment_type=row.comment_type,
                attachments=[
                    AttachmentResponse.model_validate(attachment)
                    for attachment in row.attachments
                ],
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ],
        page=query.page,
        page_size=query.page_size,
        total=total,
        total_pages=ceil(total / query.page_size) if total else 0,
    )


async def list_assignments(
    session: AsyncSession,
    *,
    ticket_id: int,
    current_user: User,
    query: TicketTimelineQuery,
) -> PageData[AssignmentResponse]:
    ticket = await _load_scoped_ticket(
        session,
        ticket_id=ticket_id,
        current_user=current_user,
    )
    if not (_is_admin(current_user) or _is_current_processor(ticket, current_user)):
        raise AppError(
            403,
            "TICKET_ACCESS_DENIED",
            "Requester chỉ được xem phân công hiện tại trong chi tiết ticket.",
        )
    rows, total = await ticket_repository.list_assignments(
        session,
        ticket_id=ticket_id,
        page=query.page,
        page_size=query.page_size,
    )
    return PageData[AssignmentResponse](
        items=[_assignment_response(row) for row in rows],
        page=query.page,
        page_size=query.page_size,
        total=total,
        total_pages=ceil(total / query.page_size) if total else 0,
    )
