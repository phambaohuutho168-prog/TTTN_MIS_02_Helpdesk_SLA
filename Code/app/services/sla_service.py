from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.sla import (
    SLA_STATUS_PRESENTATIONS,
    as_utc,
    calculate_deadline,
    calculate_effective_due_at,
    calculate_metrics,
    calculate_result,
    classify_sla_status,
    overall_sla_status,
)
from app.models.sla_pause_period import SLAPausePeriod
from app.models.ticket import Ticket
from app.models.ticket_sla import TicketSLA
from app.repositories import ticket_repository
from app.schemas.sla import (
    SLAStatusResponse,
    TicketSLAItemResponse,
    TicketSLAResponse,
    TicketSLASummaryResponse,
)
from app.schemas.ticket import PriorityBrief


def _target_minutes(record: TicketSLA) -> int:
    if record.sla_type == "RESPONSE":
        return record.policy.response_target_minutes
    return record.policy.resolution_target_minutes


def _status_response(status) -> SLAStatusResponse:
    return SLAStatusResponse(
        code=status.code,
        label=status.label,
        tone=status.tone,
        css_class=status.css_class,
    )


def current_resolution_sla(ticket: Ticket) -> TicketSLA | None:
    records = [
        record
        for record in ticket.sla_records
        if record.sla_type == "RESOLUTION"
        and record.runtime_status in {"RUNNING", "PAUSED"}
    ]
    return max(records, key=lambda record: record.cycle_no, default=None)


def latest_resolution_cycle(ticket: Ticket) -> int:
    candidates = [
        record.cycle_no
        for record in ticket.sla_records
        if record.sla_type == "RESOLUTION"
    ]
    candidates.extend(resolution.cycle_no for resolution in ticket.resolutions)
    return max(candidates, default=0)


async def create_initial_runtimes(
    session: AsyncSession,
    *,
    ticket: Ticket,
    started_at: datetime,
) -> list[TicketSLA]:
    started_at = as_utc(started_at)
    policy = await ticket_repository.get_effective_sla_policy(
        session,
        priority_id=ticket.priority_id,
        effective_at=started_at,
    )
    if policy is None:
        return []

    records = []
    for sla_type, target_minutes in (
        ("RESPONSE", policy.response_target_minutes),
        ("RESOLUTION", policy.resolution_target_minutes),
    ):
        record = await ticket_repository.create_ticket_sla_record(
            session,
            ticket_id=ticket.ticket_id,
            sla_policy_id=policy.sla_policy_id,
            sla_type=sla_type,
            cycle_no=1,
            started_at=started_at,
            due_at=calculate_deadline(
                started_at=started_at,
                target_minutes=target_minutes,
            ),
        )
        records.append(record)
    return records


async def create_resolution_cycle(
    session: AsyncSession,
    *,
    ticket: Ticket,
    started_at: datetime,
) -> TicketSLA:
    started_at = as_utc(started_at)
    policy = await ticket_repository.get_effective_sla_policy(
        session,
        priority_id=ticket.priority_id,
        effective_at=started_at,
    )
    if policy is None:
        raise AppError(
            500,
            "SLA_POLICY_CONFIGURATION_ERROR",
            "Không tìm thấy SLA policy hiệu lực cho mức ưu tiên của ticket.",
        )
    record = await ticket_repository.create_ticket_sla_record(
        session,
        ticket_id=ticket.ticket_id,
        sla_policy_id=policy.sla_policy_id,
        sla_type="RESOLUTION",
        cycle_no=latest_resolution_cycle(ticket) + 1,
        started_at=started_at,
        due_at=calculate_deadline(
            started_at=started_at,
            target_minutes=policy.resolution_target_minutes,
        ),
    )
    return record


def complete_first_response(
    ticket: Ticket,
    *,
    completed_at: datetime,
) -> TicketSLA | None:
    if ticket.first_response_at is not None:
        return None
    completed_at = as_utc(completed_at)
    ticket.first_response_at = completed_at
    candidates = [
        record
        for record in ticket.sla_records
        if record.sla_type == "RESPONSE" and record.runtime_status == "RUNNING"
    ]
    record = max(candidates, key=lambda item: item.cycle_no, default=None)
    if record is not None:
        complete_runtime(record, completed_at=completed_at)
    return record


def pause_resolution_runtime(record: TicketSLA, *, paused_at: datetime) -> None:
    record.runtime_status = "PAUSED"
    record.paused_at = as_utc(paused_at)
    record.updated_at = as_utc(paused_at)


def resume_resolution_runtime(
    record: TicketSLA,
    *,
    pause_period: SLAPausePeriod,
    resumed_at: datetime,
) -> int:
    resumed_at = as_utc(resumed_at)
    duration_seconds = max(
        0,
        int((resumed_at - as_utc(pause_period.paused_at)).total_seconds()),
    )
    pause_period.resumed_at = resumed_at
    pause_period.duration_seconds = duration_seconds
    record.total_paused_seconds += duration_seconds
    record.paused_at = None
    record.runtime_status = "RUNNING"
    record.updated_at = resumed_at
    return duration_seconds


def complete_runtime(record: TicketSLA, *, completed_at: datetime) -> None:
    completed_at = as_utc(completed_at)
    record.completed_at = completed_at
    record.paused_at = None
    record.runtime_status = "COMPLETED"
    record.result = calculate_result(
        completed_at=completed_at,
        due_at=record.due_at,
        total_paused_seconds=record.total_paused_seconds,
    )
    record.updated_at = completed_at


def mark_not_applicable(record: TicketSLA, *, completed_at: datetime) -> None:
    completed_at = as_utc(completed_at)
    record.completed_at = completed_at
    record.paused_at = None
    record.runtime_status = "NOT_APPLICABLE"
    record.result = "NOT_APPLICABLE"
    record.updated_at = completed_at


def build_sla_item(
    record: TicketSLA,
    *,
    now: datetime | None = None,
) -> TicketSLAItemResponse:
    now = as_utc(now or datetime.now(timezone.utc))
    metrics = calculate_metrics(
        started_at=record.started_at,
        due_at=record.due_at,
        total_paused_seconds=record.total_paused_seconds,
        runtime_status=record.runtime_status,
        completed_at=record.completed_at,
        paused_at=record.paused_at,
        now=now,
    )
    status = classify_sla_status(
        runtime_status=record.runtime_status,
        result=record.result,
        remaining_seconds=metrics.remaining_seconds,
        progress_percent=metrics.progress_percent,
        warning_percent=record.policy.warning_percent,
    )
    return TicketSLAItemResponse(
        ticket_sla_id=record.ticket_sla_id,
        sla_policy_id=record.sla_policy_id,
        policy_version=record.policy.version_no,
        sla_type=record.sla_type,
        cycle_no=record.cycle_no,
        target_minutes=_target_minutes(record),
        warning_percent=record.policy.warning_percent,
        escalation_percent=record.policy.escalation_percent,
        started_at=as_utc(record.started_at),
        base_due_at=metrics.base_due_at,
        due_at=metrics.base_due_at,
        effective_due_at=metrics.due_at,
        completed_at=(
            as_utc(record.completed_at) if record.completed_at is not None else None
        ),
        paused_at=(as_utc(record.paused_at) if record.paused_at is not None else None),
        total_paused_seconds=record.total_paused_seconds,
        runtime_status=record.runtime_status,
        result=record.result,
        elapsed_seconds=metrics.elapsed_seconds,
        remaining_seconds=metrics.remaining_seconds,
        progress_percent=metrics.progress_percent,
        status=_status_response(status),
    )


def build_sla_summary(
    ticket: Ticket,
    *,
    now: datetime | None = None,
) -> TicketSLASummaryResponse:
    now = now or datetime.now(timezone.utc)
    response_sla = next(
        (record for record in ticket.sla_records if record.sla_type == "RESPONSE"),
        None,
    )
    resolution_slas = sorted(
        (
            record
            for record in ticket.sla_records
            if record.sla_type == "RESOLUTION"
        ),
        key=lambda record: record.cycle_no,
    )
    response_item = (
        build_sla_item(response_sla, now=now) if response_sla is not None else None
    )
    resolution_items = [
        build_sla_item(record, now=now) for record in resolution_slas
    ]
    items = ([response_item] if response_item is not None else []) + resolution_items
    overall = overall_sla_status(
        [
            SLA_STATUS_PRESENTATIONS[item.status.code]
            for item in items
        ]
    )
    return TicketSLASummaryResponse(
        response_sla=response_item,
        resolution_cycles=resolution_items,
        overall_status=(_status_response(overall) if overall is not None else None),
    )


def build_ticket_sla_response(
    ticket: Ticket,
    *,
    now: datetime | None = None,
) -> TicketSLAResponse:
    summary = build_sla_summary(ticket, now=now)
    if summary.overall_status is None:
        raise AppError(
            404,
            "SLA_RUNTIME_NOT_FOUND",
            "Ticket chưa có SLA runtime phù hợp.",
        )
    return TicketSLAResponse(
        ticket_id=ticket.ticket_id,
        ticket_code=ticket.ticket_code,
        priority=PriorityBrief.model_validate(ticket.priority),
        first_response_at=(
            as_utc(ticket.first_response_at)
            if ticket.first_response_at is not None
            else None
        ),
        response_sla=summary.response_sla,
        resolution_cycles=summary.resolution_cycles,
        overall_status=summary.overall_status,
    )
