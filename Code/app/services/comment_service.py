from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.rbac import RoleCode
from app.models.comment import Comment
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories import comment_repository
from app.schemas.attachment import AttachmentResponse
from app.schemas.comment import CommentCreateRequest, CommentUpdateRequest
from app.schemas.ticket import TicketUserBrief
from app.schemas.ticket_detail import CommentResponse


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_admin(user: User) -> bool:
    return RoleCode.ADMIN.value in user.role_codes


def _is_current_processor(ticket: Ticket, user: User) -> bool:
    assignment = ticket.current_assignment
    return (
        RoleCode.PROCESSOR.value in user.role_codes
        and assignment is not None
        and assignment.assignee_id == user.user_id
    )


def _is_requester_owner(ticket: Ticket, user: User) -> bool:
    return (
        RoleCode.REQUESTER.value in user.role_codes
        and ticket.requester_id == user.user_id
    )


def _assert_ticket_scope(ticket: Ticket, user: User) -> None:
    if _is_admin(user) or _is_current_processor(ticket, user) or _is_requester_owner(ticket, user):
        return
    raise AppError(
        403,
        "TICKET_ACCESS_DENIED",
        "Bạn không thuộc phạm vi sở hữu hoặc phân công hiện tại của ticket.",
    )


def _assert_comment_kind(
    ticket: Ticket,
    actor: User,
    payload: CommentCreateRequest,
) -> None:
    is_handler = _is_admin(actor) or _is_current_processor(ticket, actor)
    if payload.visibility == "INTERNAL" and not is_handler:
        raise AppError(
            403,
            "INTERNAL_COMMENT_FORBIDDEN",
            "Requester không được tạo trao đổi nội bộ.",
        )
    allowed_pair = (
        payload.visibility == "PUBLIC" and payload.comment_type == "REPLY"
    ) or (
        payload.visibility == "INTERNAL"
        and payload.comment_type == "SYSTEM_NOTE"
        and is_handler
    )
    if not allowed_pair:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "COM-02 chỉ nhận PUBLIC/REPLY hoặc INTERNAL/SYSTEM_NOTE.",
            errors=[
                {
                    "field": "comment_type",
                    "message": (
                        "REQUEST_INFO phải thực hiện qua WF-02 "
                        "để đồng bộ trạng thái."
                    ),
                }
            ],
        )


def _response(comment: Comment) -> CommentResponse:
    return CommentResponse(
        comment_id=comment.comment_id,
        ticket_id=comment.ticket_id,
        author=TicketUserBrief.model_validate(comment.author),
        content=comment.content,
        visibility=comment.visibility,
        comment_type=comment.comment_type,
        attachments=[
            AttachmentResponse.model_validate(attachment)
            for attachment in comment.attachments
        ],
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


async def create_comment(
    session: AsyncSession,
    *,
    ticket_id: int,
    actor: User,
    payload: CommentCreateRequest,
    ip_address: str | None,
) -> CommentResponse:
    ticket = await comment_repository.get_ticket_for_comment_write(
        session,
        ticket_id=ticket_id,
    )
    if ticket is None:
        raise AppError(404, "TICKET_NOT_FOUND", "Không tìm thấy ticket.")
    _assert_ticket_scope(ticket, actor)
    if ticket.current_status.is_terminal:
        raise AppError(
            409,
            "TICKET_ALREADY_TERMINAL",
            "Ticket đã kết thúc nên không nhận thêm trao đổi.",
        )
    _assert_comment_kind(ticket, actor, payload)

    now = datetime.now(timezone.utc)
    try:
        comment = await comment_repository.create_comment_record(
            session,
            ticket_id=ticket.ticket_id,
            author_id=actor.user_id,
            content=payload.content,
            visibility=payload.visibility,
            comment_type=payload.comment_type,
            created_at=now,
        )
        if (
            payload.visibility == "PUBLIC"
            and payload.comment_type == "REPLY"
            and _is_current_processor(ticket, actor)
            and ticket.first_response_at is None
        ):
            ticket.first_response_at = now
            comment_repository.complete_response_sla(ticket, completed_at=now)
        await comment_repository.create_comment_audit_record(
            session,
            actor_user_id=actor.user_id,
            ticket_id=ticket.ticket_id,
            comment_id=comment.comment_id,
            action_code="COMMENT_CREATED",
            old_value=None,
            new_value={
                "content": comment.content,
                "visibility": comment.visibility,
                "comment_type": comment.comment_type,
            },
            ip_address=ip_address,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "COMMENT_CONFLICT",
            "Dữ liệu trao đổi vừa thay đổi. Vui lòng tải lại và thử lại.",
        ) from exc

    saved = await comment_repository.get_comment_by_id(session, comment.comment_id)
    if saved is None:
        raise AppError(500, "INTERNAL_SERVER_ERROR", "Không thể tải trao đổi vừa lưu.")
    return _response(saved)


async def update_comment(
    session: AsyncSession,
    *,
    comment_id: int,
    actor: User,
    payload: CommentUpdateRequest,
    ip_address: str | None,
) -> CommentResponse:
    comment = await comment_repository.get_comment_for_update(
        session,
        comment_id=comment_id,
    )
    if comment is None:
        raise AppError(404, "COMMENT_NOT_FOUND", "Không tìm thấy trao đổi.")
    ticket = comment.ticket
    _assert_ticket_scope(ticket, actor)
    now = datetime.now(timezone.utc)
    editable_until = _as_utc(comment.created_at) + timedelta(
        minutes=settings.COMMENT_EDIT_WINDOW_MINUTES
    )
    is_admin = _is_admin(actor)
    if (
        ticket.current_status.is_terminal
        or (not is_admin and comment.author_id != actor.user_id)
        or (not is_admin and now > editable_until)
    ):
        raise AppError(
            409,
            "COMMENT_NOT_EDITABLE",
            (
                "Trao đổi đã quá hạn sửa, không thuộc tác giả "
                "hoặc ticket đã kết thúc."
            ),
        )
    if payload.content == comment.content:
        raise AppError(
            409,
            "COMMENT_NOT_EDITABLE",
            "Nội dung mới không thay đổi so với nội dung hiện tại.",
        )

    old_content = comment.content
    try:
        comment.content = payload.content
        comment.updated_at = now
        await comment_repository.create_comment_audit_record(
            session,
            actor_user_id=actor.user_id,
            ticket_id=ticket.ticket_id,
            comment_id=comment.comment_id,
            action_code="COMMENT_UPDATED",
            old_value={"content": old_content},
            new_value={"content": comment.content},
            ip_address=ip_address,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "COMMENT_CONFLICT",
            "Dữ liệu trao đổi vừa thay đổi. Vui lòng tải lại và thử lại.",
        ) from exc

    saved = await comment_repository.get_comment_by_id(session, comment.comment_id)
    if saved is None:
        raise AppError(500, "INTERNAL_SERVER_ERROR", "Không thể tải trao đổi vừa sửa.")
    return _response(saved)
