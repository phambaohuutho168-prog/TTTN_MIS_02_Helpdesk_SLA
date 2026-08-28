from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rbac import RoleCode
from app.models.ticket_assignment import TicketAssignment
from app.models.user import User
from app.repositories import ticket_repository, user_repository
from app.schemas.assignment import AssignmentRequest
from app.schemas.ticket import TicketUserBrief
from app.schemas.ticket_detail import AssignmentResponse


@dataclass(frozen=True)
class AssignmentResult:
    data: AssignmentResponse
    response_code: str
    message: str


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


def _assert_valid_assignee(assignee: User | None) -> User:
    if assignee is None:
        raise AppError(
            422,
            "ASSIGNEE_INVALID",
            "Người được phân công không tồn tại hoặc không có vai trò PROCESSOR.",
            errors=[{"field": "assignee_id", "message": "Người xử lý không hợp lệ."}],
        )
    if not assignee.is_active:
        raise AppError(
            409,
            "ASSIGNEE_INACTIVE",
            "Không thể phân công cho tài khoản đã ngừng hoạt động.",
        )
    if RoleCode.PROCESSOR.value not in assignee.role_codes:
        raise AppError(
            422,
            "ASSIGNEE_INVALID",
            "Người được phân công phải có vai trò PROCESSOR đang hoạt động.",
            errors=[{"field": "assignee_id", "message": "Tài khoản không có vai trò PROCESSOR."}],
        )
    return assignee


async def assign_ticket(
    session: AsyncSession,
    *,
    ticket_id: int,
    actor: User,
    payload: AssignmentRequest,
    ip_address: str | None,
) -> AssignmentResult:
    """Assign or reassign a ticket atomically.

    Authorization is enforced by the route dependency. This service still
    validates all business invariants before mutating any row.
    """

    assignee = _assert_valid_assignee(
        await user_repository.get_user_by_id(session, payload.assignee_id)
    )
    ticket = await ticket_repository.get_ticket_for_assignment(
        session,
        ticket_id=ticket_id,
    )
    if ticket is None:
        raise AppError(404, "TICKET_NOT_FOUND", "Không tìm thấy ticket.")
    if ticket.current_status.is_terminal:
        raise AppError(
            409,
            "TICKET_ALREADY_TERMINAL",
            "Không thể phân công ticket đã ở trạng thái kết thúc.",
        )

    current = ticket.current_assignment
    now = datetime.now(timezone.utc)
    initial_assignment = current is None

    if initial_assignment and ticket.current_status_code != "NEW":
        raise AppError(
            409,
            "ASSIGNMENT_STATE_CONFLICT",
            "Chỉ ticket NEW chưa có người xử lý mới được phân công lần đầu.",
        )
    if (
        initial_assignment
        and await ticket_repository.get_status_by_code(session, "ASSIGNED") is None
    ):
        raise AppError(
            500,
            "TICKET_STATUS_CONFIGURATION_ERROR",
            "Hệ thống chưa cấu hình trạng thái ASSIGNED.",
        )
    if current is not None and current.assignee_id == assignee.user_id:
        raise AppError(
            409,
            "ASSIGNMENT_UNCHANGED",
            "Ticket đã được phân công cho người xử lý này.",
        )
    if current is not None and payload.reason is None:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Tái phân công phải có lý do.",
            errors=[{"field": "reason", "message": "Cần nhập lý do tái phân công."}],
        )

    try:
        old_value = {
            "assignment_id": current.assignment_id if current is not None else None,
            "assignee_id": current.assignee_id if current is not None else None,
            "status_code": ticket.current_status_code,
        }
        if current is not None:
            await ticket_repository.close_current_assignment(
                session,
                assignment=current,
                ended_at=now,
            )

        assignment = await ticket_repository.create_assignment_record(
            session,
            ticket_id=ticket.ticket_id,
            assignee_id=assignee.user_id,
            assigned_by=actor.user_id,
            assigned_at=now,
            reason=payload.reason,
        )

        if initial_assignment:
            ticket.current_status_code = "ASSIGNED"
            await ticket_repository.create_status_history_record(
                session,
                ticket_id=ticket.ticket_id,
                from_status_code="NEW",
                to_status_code="ASSIGNED",
                changed_by=actor.user_id,
                reason=payload.reason or "Phân công người xử lý",
            )

        await ticket_repository.create_assignment_audit_record(
            session,
            actor_user_id=actor.user_id,
            ticket_id=ticket.ticket_id,
            assignment_id=assignment.assignment_id,
            action_code=("TICKET_ASSIGNED" if initial_assignment else "TICKET_REASSIGNED"),
            old_value=old_value,
            new_value={
                "assignment_id": assignment.assignment_id,
                "assignee_id": assignment.assignee_id,
                "status_code": ticket.current_status_code,
            },
            reason=payload.reason,
            ip_address=ip_address,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "ASSIGNMENT_CONFLICT",
            "Dữ liệu phân công vừa thay đổi. Vui lòng tải lại ticket và thử lại.",
        ) from exc

    saved = await ticket_repository.get_assignment_by_id(
        session,
        assignment.assignment_id,
    )
    if saved is None:
        raise AppError(
            500,
            "INTERNAL_SERVER_ERROR",
            "Không thể tải phân công vừa lưu.",
        )
    return AssignmentResult(
        data=_assignment_response(saved),
        response_code=("TICKET_ASSIGNED" if initial_assignment else "TICKET_REASSIGNED"),
        message=(
            "Phân công người xử lý thành công."
            if initial_assignment
            else "Tái phân công người xử lý thành công."
        ),
    )
