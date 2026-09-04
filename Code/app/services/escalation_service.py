from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sla import (
    as_utc,
    calculate_effective_due_at,
    calculate_metrics,
    reached_sla_thresholds,
)
from app.models.sla_event import SLAEvent
from app.models.ticket_sla import TicketSLA
from app.models.user import User
from app.repositories import audit_repository, escalation_repository
from app.schemas.common import PageData
from app.schemas.escalation import (
    SLABreachQuery,
    SLAEscalationRunResponse,
    SLAEventResponse,
    SLAEventTicketBrief,
)
from app.schemas.ticket import PriorityBrief, TicketUserBrief


EVENT_COPY = {
    "WARNING": ("SLA sắp quá hạn", "đã đạt ngưỡng cảnh báo"),
    "OVERDUE": ("SLA đã quá hạn", "đã vượt quá deadline"),
    "ESCALATED": ("SLA cần escalation", "đã đạt ngưỡng escalation"),
}


@dataclass(frozen=True)
class EscalationRunResult:
    scanned_runtimes: int
    created_events: int
    created_notifications: int
    skipped_without_recipient: int


def _recipients(record: TicketSLA, admins: list[User]) -> list[User]:
    recipients = {admin.user_id: admin for admin in admins}
    assignment = record.ticket.current_assignment
    if assignment is not None and assignment.assignee.is_active:
        recipients[assignment.assignee.user_id] = assignment.assignee
    return [recipients[user_id] for user_id in sorted(recipients)]


def _notification_copy(
    record: TicketSLA,
    *,
    event_type: str,
    progress_percent: float,
) -> tuple[str, str]:
    title, action = EVENT_COPY[event_type]
    sla_label = "phản hồi" if record.sla_type == "RESPONSE" else "xử lý"
    return (
        f"{title}: {record.ticket.ticket_code}",
        f"SLA {sla_label} của ticket {record.ticket.ticket_code} {action} "
        f"({progress_percent:.2f}%).",
    )


async def process_sla_escalations(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> EscalationRunResult:
    now = as_utc(now or datetime.now(timezone.utc))
    records = await escalation_repository.list_worker_candidates(session)
    admins = await escalation_repository.list_active_admins(session)
    created_events = 0
    created_notifications = 0
    skipped_without_recipient = 0

    try:
        for record in records:
            metrics = calculate_metrics(
                started_at=record.started_at,
                due_at=record.due_at,
                total_paused_seconds=record.total_paused_seconds,
                runtime_status=record.runtime_status,
                now=now,
            )
            thresholds = reached_sla_thresholds(
                progress_percent=metrics.progress_percent,
                remaining_seconds=metrics.remaining_seconds,
                warning_percent=record.policy.warning_percent,
                escalation_percent=record.policy.escalation_percent,
                priority_level=record.ticket.priority.priority_level,
            )
            if not thresholds:
                continue

            recipients = _recipients(record, admins)
            if not recipients:
                skipped_without_recipient += 1
                continue

            for threshold in thresholds:
                event = await escalation_repository.create_event_if_absent(
                    session,
                    ticket_sla_id=record.ticket_sla_id,
                    event_type=threshold.event_type,
                    threshold_percent=threshold.threshold_percent,
                    triggered_at=now,
                )
                if event is None:
                    continue

                created_events += 1
                title, message = _notification_copy(
                    record,
                    event_type=threshold.event_type,
                    progress_percent=metrics.progress_percent or 0,
                )
                recipient_ids = []
                for recipient in recipients:
                    notification_id = (
                        await escalation_repository.create_notification_if_absent(
                            session,
                            recipient_id=recipient.user_id,
                            ticket_id=record.ticket_id,
                            sla_event_id=event.sla_event_id,
                            notification_type=f"SLA_{threshold.event_type}",
                            title=title,
                            message=message,
                            created_at=now,
                        )
                    )
                    if notification_id is not None:
                        created_notifications += 1
                        recipient_ids.append(recipient.user_id)

                await audit_repository.append_audit(
                    session,
                    action_code=f"SLA_{threshold.event_type}_TRIGGERED",
                    entity_type="SLA_EVENT",
                    entity_id=event.sla_event_id,
                    ticket_id=record.ticket_id,
                    new_value={
                        "ticket_sla_id": record.ticket_sla_id,
                        "sla_type": record.sla_type,
                        "cycle_no": record.cycle_no,
                        "event_type": threshold.event_type,
                        "threshold_percent": threshold.threshold_percent,
                        "progress_percent": metrics.progress_percent,
                        "recipient_ids": recipient_ids,
                    },
                    reason="SLA worker phát hiện runtime đạt ngưỡng.",
                )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return EscalationRunResult(
        scanned_runtimes=len(records),
        created_events=created_events,
        created_notifications=created_notifications,
        skipped_without_recipient=skipped_without_recipient,
    )


def _event_response(event: SLAEvent) -> SLAEventResponse:
    record = event.ticket_sla
    ticket = record.ticket
    assignment = ticket.current_assignment
    recipients = sorted(
        (
            notification.recipient
            for notification in event.notifications
            if notification.recipient is not None
        ),
        key=lambda user: user.user_id,
    )
    return SLAEventResponse(
        sla_event_id=event.sla_event_id,
        ticket_sla_id=record.ticket_sla_id,
        sla_type=record.sla_type,
        cycle_no=record.cycle_no,
        ticket=SLAEventTicketBrief(
            ticket_id=ticket.ticket_id,
            ticket_code=ticket.ticket_code,
            title=ticket.title,
            current_status_code=ticket.current_status_code,
            priority=PriorityBrief.model_validate(ticket.priority),
        ),
        due_at=as_utc(record.due_at),
        effective_due_at=calculate_effective_due_at(
            due_at=record.due_at,
            total_paused_seconds=record.total_paused_seconds,
        ),
        threshold_percent=event.threshold_percent,
        state=event.event_type,
        triggered_at=as_utc(event.triggered_at),
        current_assignee=(
            TicketUserBrief.model_validate(assignment.assignee)
            if assignment is not None
            else None
        ),
        recipients=[TicketUserBrief.model_validate(user) for user in recipients],
    )


async def list_sla_events(
    session: AsyncSession,
    *,
    query: SLABreachQuery,
    current_user_id: int,
    role_codes: set[str],
) -> PageData[SLAEventResponse]:
    records, total = await escalation_repository.list_events(
        session,
        query=query,
        current_user_id=current_user_id,
        role_codes=role_codes,
    )
    return PageData[SLAEventResponse](
        items=[_event_response(record) for record in records],
        page=query.page,
        page_size=query.page_size,
        total=total,
        total_pages=ceil(total / query.page_size) if total else 0,
    )


def run_response(result: EscalationRunResult) -> SLAEscalationRunResponse:
    return SLAEscalationRunResponse.model_validate(result)
