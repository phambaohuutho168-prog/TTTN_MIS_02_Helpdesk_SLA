from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import floor


@dataclass(frozen=True)
class SLAMetrics:
    base_due_at: datetime
    due_at: datetime
    elapsed_seconds: int | None
    remaining_seconds: int | None
    progress_percent: float | None


@dataclass(frozen=True)
class SLAStatusPresentation:
    code: str
    label: str
    tone: str
    css_class: str


SLA_STATUS_PRESENTATIONS = {
    "ON_TRACK": SLAStatusPresentation(
        code="ON_TRACK",
        label="Còn hạn",
        tone="INFO",
        css_class="sla-status--on-track",
    ),
    "NEAR_DUE": SLAStatusPresentation(
        code="NEAR_DUE",
        label="Sắp quá hạn",
        tone="WARNING",
        css_class="sla-status--near-due",
    ),
    "OVERDUE": SLAStatusPresentation(
        code="OVERDUE",
        label="Quá hạn",
        tone="DANGER",
        css_class="sla-status--overdue",
    ),
    "MET": SLAStatusPresentation(
        code="MET",
        label="Đúng SLA",
        tone="SUCCESS",
        css_class="sla-status--met",
    ),
    "NOT_APPLICABLE": SLAStatusPresentation(
        code="NOT_APPLICABLE",
        label="Không áp dụng",
        tone="MUTED",
        css_class="sla-status--not-applicable",
    ),
}

SLA_STATUS_SEVERITY = {
    "NOT_APPLICABLE": 0,
    "MET": 1,
    "ON_TRACK": 2,
    "NEAR_DUE": 3,
    "OVERDUE": 4,
}


def as_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime for DB and API calculations."""

    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def calculate_deadline(*, started_at: datetime, target_minutes: int) -> datetime:
    """Calculate a calendar-time SLA deadline from an immutable policy target."""

    if target_minutes <= 0:
        raise ValueError("SLA target_minutes must be greater than zero")
    return as_utc(started_at) + timedelta(minutes=target_minutes)


def calculate_effective_due_at(
    *,
    due_at: datetime,
    total_paused_seconds: int,
) -> datetime:
    """Extend the base deadline by completed Resolution SLA pause time."""

    if total_paused_seconds < 0:
        raise ValueError("SLA total_paused_seconds cannot be negative")
    return as_utc(due_at) + timedelta(seconds=total_paused_seconds)


def calculate_result(
    *,
    completed_at: datetime,
    due_at: datetime,
    total_paused_seconds: int = 0,
) -> str:
    effective_due_at = calculate_effective_due_at(
        due_at=due_at,
        total_paused_seconds=total_paused_seconds,
    )
    return "MET" if as_utc(completed_at) <= effective_due_at else "BREACHED"


def classify_sla_status(
    *,
    runtime_status: str,
    result: str | None,
    remaining_seconds: int | None,
    progress_percent: float | None,
    warning_percent: int,
) -> SLAStatusPresentation:
    """Map one SLA runtime to a stable API/UI presentation state."""

    if not 1 <= warning_percent <= 99:
        raise ValueError("SLA warning_percent must be between 1 and 99")
    if runtime_status == "NOT_APPLICABLE" or result == "NOT_APPLICABLE":
        code = "NOT_APPLICABLE"
    elif result == "MET":
        code = "MET"
    elif result == "BREACHED" or (
        remaining_seconds is not None and remaining_seconds < 0
    ):
        code = "OVERDUE"
    elif progress_percent is not None and progress_percent >= warning_percent:
        code = "NEAR_DUE"
    else:
        code = "ON_TRACK"
    return SLA_STATUS_PRESENTATIONS[code]


def overall_sla_status(
    statuses: list[SLAStatusPresentation],
) -> SLAStatusPresentation | None:
    if not statuses:
        return None
    return max(statuses, key=lambda status: SLA_STATUS_SEVERITY[status.code])


def calculate_metrics(
    *,
    started_at: datetime,
    due_at: datetime,
    total_paused_seconds: int,
    runtime_status: str,
    now: datetime,
    completed_at: datetime | None = None,
    paused_at: datetime | None = None,
) -> SLAMetrics:
    base_due_at = as_utc(due_at)
    effective_due_at = calculate_effective_due_at(
        due_at=base_due_at,
        total_paused_seconds=total_paused_seconds,
    )
    if runtime_status == "NOT_APPLICABLE":
        return SLAMetrics(
            base_due_at=base_due_at,
            due_at=effective_due_at,
            elapsed_seconds=None,
            remaining_seconds=None,
            progress_percent=None,
        )

    if completed_at is not None:
        anchor = as_utc(completed_at)
    elif runtime_status == "PAUSED" and paused_at is not None:
        anchor = as_utc(paused_at)
    else:
        anchor = as_utc(now)

    started = as_utc(started_at)
    elapsed_seconds = max(
        0,
        int((anchor - started).total_seconds()) - total_paused_seconds,
    )
    target_seconds = max(1, int((base_due_at - started).total_seconds()))
    remaining_seconds = floor((effective_due_at - anchor).total_seconds())
    return SLAMetrics(
        base_due_at=base_due_at,
        due_at=effective_due_at,
        elapsed_seconds=elapsed_seconds,
        remaining_seconds=remaining_seconds,
        progress_percent=round(elapsed_seconds * 100 / target_seconds, 2),
    )
