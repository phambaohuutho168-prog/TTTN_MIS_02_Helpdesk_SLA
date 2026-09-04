from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit_log import AuditLog
from app.models.comment import Comment
from app.models.sla_pause_period import SLAPausePeriod
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_resolution import TicketResolution
from app.models.ticket_sla import TicketSLA
from app.models.user import User
from app.models.user_role import UserRole


async def get_ticket_for_workflow(
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
            selectinload(Ticket.resolutions),
            selectinload(Ticket.sla_records).selectinload(TicketSLA.policy),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    ticket = result.scalar_one_or_none()
    if ticket is not None:
        sla_ids = [record.ticket_sla_id for record in ticket.sla_records]
        if sla_ids:
            pause_result = await session.execute(
                select(SLAPausePeriod)
                .where(SLAPausePeriod.ticket_sla_id.in_(sla_ids))
                .order_by(
                    SLAPausePeriod.paused_at,
                    SLAPausePeriod.pause_id,
                )
            )
            pauses_by_sla: dict[int, list[SLAPausePeriod]] = {}
            for pause in pause_result.scalars():
                pauses_by_sla.setdefault(pause.ticket_sla_id, []).append(pause)
            for record in ticket.sla_records:
                record._workflow_pause_periods = pauses_by_sla.get(
                    record.ticket_sla_id,
                    [],
                )
    return ticket


async def create_workflow_audit_record(
    session: AsyncSession,
    *,
    actor_user_id: int | None,
    ticket_id: int,
    action_code: str,
    workflow_code: str,
    from_status_code: str,
    to_status_code: str,
    reason: str | None,
    ip_address: str | None,
    new_value_extra: dict | None = None,
) -> AuditLog:
    new_value = {
        "status_code": to_status_code,
        "workflow_code": workflow_code,
    }
    if new_value_extra:
        new_value.update(new_value_extra)
    audit = AuditLog(
        actor_user_id=actor_user_id,
        ticket_id=ticket_id,
        action_code=action_code,
        entity_type="TICKET",
        entity_id=ticket_id,
        old_value_json={"status_code": from_status_code},
        new_value_json=new_value,
        reason=reason,
        ip_address=ip_address,
    )
    session.add(audit)
    await session.flush()
    return audit


async def create_comment_record(
    session: AsyncSession,
    *,
    ticket_id: int,
    author_id: int,
    content: str,
    comment_type: str,
) -> Comment:
    comment = Comment(
        ticket_id=ticket_id,
        author_id=author_id,
        content=content,
        visibility="PUBLIC",
        comment_type=comment_type,
    )
    session.add(comment)
    await session.flush()
    return comment


async def create_resolution_record(
    session: AsyncSession,
    *,
    ticket_id: int,
    resolved_by: int,
    cycle_no: int,
    resolution_note: str,
    resolved_at: datetime,
) -> TicketResolution:
    resolution = TicketResolution(
        ticket_id=ticket_id,
        resolved_by=resolved_by,
        cycle_no=cycle_no,
        resolution_note=resolution_note,
        resolved_at=resolved_at,
    )
    session.add(resolution)
    await session.flush()
    return resolution


async def create_sla_pause_period(
    session: AsyncSession,
    *,
    ticket_sla_id: int,
    paused_at: datetime,
    reason: str,
) -> SLAPausePeriod:
    pause = SLAPausePeriod(
        ticket_sla_id=ticket_sla_id,
        paused_at=paused_at,
        reason=reason,
    )
    session.add(pause)
    await session.flush()
    return pause


async def list_expired_resolved_ticket_ids(
    session: AsyncSession,
    *,
    resolved_before: datetime,
) -> list[int]:
    latest_resolution = (
        select(func.max(TicketResolution.resolved_at))
        .where(TicketResolution.ticket_id == Ticket.ticket_id)
        .correlate(Ticket)
        .scalar_subquery()
    )
    result = await session.execute(
        select(Ticket.ticket_id)
        .where(
            Ticket.current_status_code == "RESOLVED",
            latest_resolution.is_not(None),
            latest_resolution <= resolved_before,
        )
        .order_by(Ticket.ticket_id)
    )
    return list(result.scalars().all())
