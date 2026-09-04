from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rbac import RoleCode
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories import (
    audit_repository,
    ticket_repository,
    workflow_repository,
)
from app.schemas.ticket_detail import TicketDetailResponse
from app.schemas.workflow import (
    CloseRequest,
    ProvideInfoRequest,
    RejectRequest,
    ReopenRequest,
    RequestInfoRequest,
    ResolveRequest,
    TransitionReasonRequest,
)
from app.services import sla_service, ticket_detail_service


REOPEN_WINDOW = timedelta(hours=72)


@dataclass(frozen=True)
class WorkflowResult:
    data: TicketDetailResponse | None
    response_code: str
    message: str


SideEffect = Callable[
    [Ticket, datetime],
    Awaitable[dict[str, object] | None],
]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _role_codes(user: User) -> set[str]:
    return set(user.role_codes)


def _assert_processor_or_admin(ticket: Ticket, actor: User) -> None:
    roles = _role_codes(actor)
    if RoleCode.ADMIN.value in roles:
        return
    if RoleCode.PROCESSOR.value not in roles:
        raise AppError(
            403,
            "FORBIDDEN_ACTION",
            "Vai trò hiện tại không được thực hiện hành động workflow này.",
        )
    assignment = ticket.current_assignment
    if assignment is None or assignment.assignee_id != actor.user_id:
        raise AppError(
            409,
            "ASSIGNMENT_REQUIRED",
            "Chỉ người xử lý đang được phân công mới được thực hiện hành động này.",
        )


def _assert_requester_owner(ticket: Ticket, actor: User) -> None:
    if RoleCode.REQUESTER.value not in _role_codes(actor):
        raise AppError(
            403,
            "FORBIDDEN_ACTION",
            "Chỉ người gửi yêu cầu được thực hiện hành động này.",
        )
    if ticket.requester_id != actor.user_id:
        raise AppError(
            403,
            "TICKET_ACCESS_DENIED",
            "Bạn không phải người sở hữu ticket này.",
        )


def _assert_close_permission(
    ticket: Ticket,
    actor: User,
    reason: str | None,
) -> None:
    roles = _role_codes(actor)
    if RoleCode.ADMIN.value in roles:
        if reason is None or len(reason) < 5:
            raise AppError(
                422,
                "CLOSE_REASON_REQUIRED",
                "Admin phải nhập lý do đóng ticket.",
                errors=[
                    {
                        "field": "reason",
                        "message": "Lý do đóng của Admin phải có ít nhất 5 ký tự.",
                    }
                ],
            )
        return
    _assert_requester_owner(ticket, actor)


def _assert_state(ticket: Ticket, source: str, target: str) -> None:
    if ticket.current_status.is_terminal:
        raise AppError(
            409,
            "TICKET_ALREADY_TERMINAL",
            "Ticket đã ở trạng thái kết thúc và không thể chuyển tiếp.",
        )
    if ticket.current_status_code != source:
        raise AppError(
            409,
            "INVALID_STATE_TRANSITION",
            f"Không thể chuyển ticket từ {ticket.current_status_code} sang {target}.",
        )


async def _transition(
    session: AsyncSession,
    *,
    ticket_id: int,
    actor: User | None,
    authorization: str,
    workflow_code: str,
    action_code: str,
    source: str,
    target: str,
    reason: str | None,
    history_reason: str,
    response_code: str,
    message: str,
    ip_address: str | None,
    side_effect: SideEffect | None = None,
    now: datetime | None = None,
) -> WorkflowResult:
    try:
        ticket = await workflow_repository.get_ticket_for_workflow(
            session,
            ticket_id=ticket_id,
        )
        if ticket is None:
            raise AppError(404, "TICKET_NOT_FOUND", "Không tìm thấy ticket.")

        if authorization == "PROCESSOR_OR_ADMIN":
            if actor is None:
                raise AppError(403, "FORBIDDEN_ACTION", "Thiếu tác nhân workflow.")
            _assert_processor_or_admin(ticket, actor)
        elif authorization == "REQUESTER_OWNER":
            if actor is None:
                raise AppError(403, "FORBIDDEN_ACTION", "Thiếu tác nhân workflow.")
            _assert_requester_owner(ticket, actor)
        elif authorization == "CLOSE":
            if actor is None:
                raise AppError(403, "FORBIDDEN_ACTION", "Thiếu tác nhân workflow.")
            _assert_close_permission(ticket, actor, reason)
        elif authorization == "ADMIN":
            if actor is None or RoleCode.ADMIN.value not in _role_codes(actor):
                raise AppError(403, "FORBIDDEN_ACTION", "Chỉ Admin được từ chối ticket.")
        elif authorization != "SYSTEM":
            raise RuntimeError("Unknown workflow authorization policy")

        _assert_state(ticket, source, target)
        if await ticket_repository.get_status_by_code(session, target) is None:
            raise AppError(
                500,
                "TICKET_STATUS_CONFIGURATION_ERROR",
                f"Hệ thống chưa cấu hình trạng thái {target}.",
            )

        changed_at = now or datetime.now(timezone.utc)
        side_effect_audit: dict[str, object] = {}
        if side_effect is not None:
            side_effect_audit = await side_effect(ticket, changed_at) or {}

        ticket.current_status_code = target
        actor_id = actor.user_id if actor is not None else None
        await ticket_repository.create_status_history_record(
            session,
            ticket_id=ticket.ticket_id,
            from_status_code=source,
            to_status_code=target,
            changed_by=actor_id,
            reason=reason or history_reason,
        )
        await workflow_repository.create_workflow_audit_record(
            session,
            actor_user_id=actor_id,
            ticket_id=ticket.ticket_id,
            action_code=action_code,
            workflow_code=workflow_code,
            from_status_code=source,
            to_status_code=target,
            reason=reason or history_reason,
            ip_address=ip_address,
            new_value_extra={
                **(
                    {
                        "closed_by": actor_id,
                        "closed_at": changed_at.isoformat(),
                    }
                    if target == "CLOSED"
                    else {}
                ),
                **side_effect_audit,
            }
            or None,
        )
        await session.commit()
    except AppError:
        await session.rollback()
        raise
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "WORKFLOW_CONFLICT",
            "Ticket vừa được cập nhật bởi yêu cầu khác. Vui lòng tải lại và thử lại.",
        ) from exc
    except Exception:
        await session.rollback()
        raise

    detail = None
    if actor is not None:
        detail = await ticket_detail_service.get_ticket_detail(
            session,
            ticket_id=ticket_id,
            current_user=actor,
        )
    return WorkflowResult(detail, response_code, message)


async def start_ticket(
    session: AsyncSession,
    *,
    ticket_id: int,
    actor: User,
    payload: TransitionReasonRequest,
    ip_address: str | None,
) -> WorkflowResult:
    return await _transition(
        session,
        ticket_id=ticket_id,
        actor=actor,
        authorization="PROCESSOR_OR_ADMIN",
        workflow_code="WF-01",
        action_code="TICKET_STARTED",
        source="ASSIGNED",
        target="IN_PROGRESS",
        reason=payload.reason,
        history_reason="Bắt đầu xử lý ticket",
        response_code="TICKET_STARTED",
        message="Bắt đầu xử lý ticket thành công.",
        ip_address=ip_address,
    )


async def request_information(
    session: AsyncSession,
    *,
    ticket_id: int,
    actor: User,
    payload: RequestInfoRequest,
    ip_address: str | None,
) -> WorkflowResult:
    async def side_effect(ticket: Ticket, changed_at: datetime) -> None:
        await workflow_repository.create_comment_record(
            session,
            ticket_id=ticket.ticket_id,
            author_id=actor.user_id,
            content=payload.content,
            comment_type="REQUEST_INFO",
        )
        resolution_sla = sla_service.current_resolution_sla(ticket)
        if resolution_sla is None:
            return
        if resolution_sla.runtime_status != "RUNNING":
            raise AppError(
                409,
                "SLA_RUNTIME_CONFLICT",
                "Resolution SLA hiện tại không ở trạng thái RUNNING.",
            )
        sla_service.pause_resolution_runtime(
            resolution_sla,
            paused_at=changed_at,
        )
        await workflow_repository.create_sla_pause_period(
            session,
            ticket_sla_id=resolution_sla.ticket_sla_id,
            paused_at=changed_at,
            reason="Chờ người gửi bổ sung thông tin",
        )

    return await _transition(
        session,
        ticket_id=ticket_id,
        actor=actor,
        authorization="PROCESSOR_OR_ADMIN",
        workflow_code="WF-02",
        action_code="TICKET_INFO_REQUESTED",
        source="IN_PROGRESS",
        target="PENDING_INFO",
        reason=None,
        history_reason="Yêu cầu người gửi bổ sung thông tin",
        response_code="TICKET_INFO_REQUESTED",
        message="Đã yêu cầu bổ sung thông tin.",
        ip_address=ip_address,
        side_effect=side_effect,
    )


async def provide_information(
    session: AsyncSession,
    *,
    ticket_id: int,
    actor: User,
    payload: ProvideInfoRequest,
    ip_address: str | None,
) -> WorkflowResult:
    async def side_effect(ticket: Ticket, changed_at: datetime) -> None:
        await workflow_repository.create_comment_record(
            session,
            ticket_id=ticket.ticket_id,
            author_id=actor.user_id,
            content=payload.content,
            comment_type="REPLY",
        )
        resolution_sla = sla_service.current_resolution_sla(ticket)
        if resolution_sla is None:
            return
        if resolution_sla.runtime_status != "PAUSED" or resolution_sla.paused_at is None:
            raise AppError(
                409,
                "SLA_RUNTIME_CONFLICT",
                "Resolution SLA hiện tại không ở trạng thái PAUSED.",
            )
        open_pause = next(
            (
                period
                for period in reversed(
                    getattr(resolution_sla, "_workflow_pause_periods", [])
                )
                if period.resumed_at is None
            ),
            None,
        )
        if open_pause is None:
            raise AppError(
                409,
                "SLA_RUNTIME_CONFLICT",
                "Không tìm thấy khoảng tạm dừng SLA đang mở.",
            )
        sla_service.resume_resolution_runtime(
            resolution_sla,
            pause_period=open_pause,
            resumed_at=changed_at,
        )

    return await _transition(
        session,
        ticket_id=ticket_id,
        actor=actor,
        authorization="REQUESTER_OWNER",
        workflow_code="WF-03",
        action_code="TICKET_INFO_PROVIDED",
        source="PENDING_INFO",
        target="IN_PROGRESS",
        reason=None,
        history_reason="Người gửi đã bổ sung thông tin",
        response_code="TICKET_INFO_PROVIDED",
        message="Bổ sung thông tin thành công.",
        ip_address=ip_address,
        side_effect=side_effect,
    )


async def resolve_ticket(
    session: AsyncSession,
    *,
    ticket_id: int,
    actor: User,
    payload: ResolveRequest,
    ip_address: str | None,
) -> WorkflowResult:
    async def side_effect(ticket: Ticket, changed_at: datetime) -> None:
        resolution_sla = sla_service.current_resolution_sla(ticket)
        if resolution_sla is not None and resolution_sla.runtime_status != "RUNNING":
            raise AppError(
                409,
                "SLA_RUNTIME_CONFLICT",
                "Không thể hoàn tất Resolution SLA khi SLA không RUNNING.",
            )
        cycle_no = (
            resolution_sla.cycle_no
            if resolution_sla is not None
            else sla_service.latest_resolution_cycle(ticket) + 1
        )
        await workflow_repository.create_resolution_record(
            session,
            ticket_id=ticket.ticket_id,
            resolved_by=actor.user_id,
            cycle_no=cycle_no,
            resolution_note=payload.resolution_note,
            resolved_at=changed_at,
        )
        if resolution_sla is not None:
            sla_service.complete_runtime(
                resolution_sla,
                completed_at=changed_at,
            )

    return await _transition(
        session,
        ticket_id=ticket_id,
        actor=actor,
        authorization="PROCESSOR_OR_ADMIN",
        workflow_code="WF-04",
        action_code="TICKET_RESOLVED",
        source="IN_PROGRESS",
        target="RESOLVED",
        reason=None,
        history_reason="Hoàn tất xử lý ticket",
        response_code="TICKET_RESOLVED",
        message="Giải quyết ticket thành công.",
        ip_address=ip_address,
        side_effect=side_effect,
    )


async def close_ticket(
    session: AsyncSession,
    *,
    ticket_id: int,
    actor: User,
    payload: CloseRequest,
    ip_address: str | None,
) -> WorkflowResult:
    async def side_effect(ticket: Ticket, changed_at: datetime) -> None:
        await _set_close_metadata(
            ticket,
            changed_at,
            closed_by=actor.user_id,
        )

    return await _transition(
        session,
        ticket_id=ticket_id,
        actor=actor,
        authorization="CLOSE",
        workflow_code="WF-05",
        action_code="TICKET_CLOSED",
        source="RESOLVED",
        target="CLOSED",
        reason=payload.reason,
        history_reason="Người gửi xác nhận đóng ticket",
        response_code="TICKET_CLOSED",
        message="Đóng ticket thành công.",
        ip_address=ip_address,
        side_effect=side_effect,
    )


async def reopen_ticket(
    session: AsyncSession,
    *,
    ticket_id: int,
    actor: User,
    payload: ReopenRequest,
    ip_address: str | None,
    now: datetime | None = None,
) -> WorkflowResult:
    async def side_effect(
        ticket: Ticket,
        changed_at: datetime,
    ) -> dict[str, object]:
        latest_resolution = max(
            ticket.resolutions,
            key=lambda resolution: resolution.cycle_no,
            default=None,
        )
        if latest_resolution is None:
            raise AppError(
                409,
                "RESOLUTION_RECORD_MISSING",
                "Ticket RESOLVED chưa có bản ghi kết quả xử lý.",
            )
        if (
            _as_utc(changed_at)
            > _as_utc(latest_resolution.resolved_at) + REOPEN_WINDOW
        ):
            raise AppError(
                409,
                "REOPEN_WINDOW_EXPIRED",
                "Đã quá thời hạn mở lại ticket trong vòng 72 giờ.",
            )
        reopen_deadline = _as_utc(latest_resolution.resolved_at) + REOPEN_WINDOW
        return {
            "reopened_by": actor.user_id,
            "reopened_at": _as_utc(changed_at).isoformat(),
            "source_resolution_cycle": latest_resolution.cycle_no,
            "source_resolved_at": _as_utc(latest_resolution.resolved_at).isoformat(),
            "reopen_window_expires_at": reopen_deadline.isoformat(),
            "sla_action": "PRESERVE_COMPLETED_CYCLES_UNTIL_RESUME",
            "next_resolution_cycle": sla_service.latest_resolution_cycle(ticket) + 1,
        }

    return await _transition(
        session,
        ticket_id=ticket_id,
        actor=actor,
        authorization="REQUESTER_OWNER",
        workflow_code="WF-06",
        action_code="TICKET_REOPENED",
        source="RESOLVED",
        target="REOPENED",
        reason=payload.reason,
        history_reason=payload.reason,
        response_code="TICKET_REOPENED",
        message="Mở lại ticket thành công.",
        ip_address=ip_address,
        side_effect=side_effect,
        now=now,
    )


async def resume_reopened_ticket(
    session: AsyncSession,
    *,
    ticket_id: int,
    actor: User,
    payload: TransitionReasonRequest,
    ip_address: str | None,
) -> WorkflowResult:
    async def side_effect(
        ticket: Ticket,
        changed_at: datetime,
    ) -> dict[str, object]:
        previous_cycle = sla_service.latest_resolution_cycle(ticket)
        record = await sla_service.create_resolution_cycle(
            session,
            ticket=ticket,
            started_at=changed_at,
        )
        await audit_repository.append_audit(
            session,
            actor_user_id=actor.user_id,
            ticket_id=ticket.ticket_id,
            action_code="SLA_RUNTIME_CREATED",
            entity_type="TICKET_SLA",
            entity_id=record.ticket_sla_id,
            old_value={"previous_resolution_cycle": previous_cycle},
            new_value={
                "sla_type": record.sla_type,
                "cycle_no": record.cycle_no,
                "runtime_status": record.runtime_status,
                "started_at": record.started_at,
                "due_at": record.due_at,
                "sla_policy_id": record.sla_policy_id,
            },
            reason=payload.reason,
            ip_address=ip_address,
        )
        return {
            "sla_action": "CREATE_RESOLUTION_CYCLE",
            "ticket_sla_id": record.ticket_sla_id,
            "resolution_cycle": record.cycle_no,
            "sla_started_at": _as_utc(record.started_at).isoformat(),
            "sla_due_at": _as_utc(record.due_at).isoformat(),
        }

    return await _transition(
        session,
        ticket_id=ticket_id,
        actor=actor,
        authorization="PROCESSOR_OR_ADMIN",
        workflow_code="WF-07",
        action_code="TICKET_RESUMED",
        source="REOPENED",
        target="IN_PROGRESS",
        reason=payload.reason,
        history_reason="Tiếp tục xử lý ticket đã mở lại",
        response_code="TICKET_RESUMED",
        message="Tiếp tục xử lý ticket thành công.",
        ip_address=ip_address,
        side_effect=side_effect,
    )


async def reject_ticket(
    session: AsyncSession,
    *,
    ticket_id: int,
    actor: User,
    payload: RejectRequest,
    ip_address: str | None,
) -> WorkflowResult:
    async def side_effect(ticket: Ticket, changed_at: datetime) -> None:
        ticket.rejected_at = changed_at
        ticket.rejection_reason = payload.reason
        for record in ticket.sla_records:
            if record.runtime_status not in {"RUNNING", "PAUSED"}:
                continue
            sla_service.mark_not_applicable(record, completed_at=changed_at)

    return await _transition(
        session,
        ticket_id=ticket_id,
        actor=actor,
        authorization="ADMIN",
        workflow_code="WF-08",
        action_code="TICKET_REJECTED",
        source="NEW",
        target="REJECTED",
        reason=payload.reason,
        history_reason=payload.reason,
        response_code="TICKET_REJECTED",
        message="Từ chối ticket thành công.",
        ip_address=ip_address,
        side_effect=side_effect,
    )


async def auto_close_expired_tickets(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    """Idempotently close RESOLVED tickets whose 72-hour window expired."""

    changed_at = now or datetime.now(timezone.utc)
    ticket_ids = await workflow_repository.list_expired_resolved_ticket_ids(
        session,
        resolved_before=changed_at - REOPEN_WINDOW,
    )
    closed = 0
    for ticket_id in ticket_ids:
        try:
            await _transition(
                session,
                ticket_id=ticket_id,
                actor=None,
                authorization="SYSTEM",
                workflow_code="WF-05",
                action_code="TICKET_AUTO_CLOSED",
                source="RESOLVED",
                target="CLOSED",
                reason="SYSTEM_AUTO_CLOSE",
                history_reason="SYSTEM_AUTO_CLOSE",
                response_code="TICKET_CLOSED",
                message="Đóng ticket tự động thành công.",
                ip_address=None,
                side_effect=lambda ticket, at: _set_close_metadata(
                    ticket,
                    at,
                    closed_by=None,
                ),
                now=changed_at,
            )
            closed += 1
        except AppError as exc:
            if exc.code not in {"INVALID_STATE_TRANSITION", "TICKET_ALREADY_TERMINAL"}:
                raise
    return closed


async def _set_close_metadata(
    ticket: Ticket,
    changed_at: datetime,
    *,
    closed_by: int | None,
) -> None:
    latest_resolution = max(
        ticket.resolutions,
        key=lambda resolution: resolution.cycle_no,
        default=None,
    )
    if (
        latest_resolution is None
        or not latest_resolution.resolution_note.strip()
    ):
        raise AppError(
            409,
            "RESOLUTION_RECORD_MISSING",
            "Ticket chỉ được đóng sau khi đã ghi nhận cách xử lý.",
        )
    ticket.closed_at = changed_at
    ticket.closed_by = closed_by
