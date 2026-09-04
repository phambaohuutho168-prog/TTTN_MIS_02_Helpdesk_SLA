from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class SLAMetrics:
    base_due_at: datetime
    due_at: datetime
    elapsed_seconds: int | None
    remaining_seconds: int | None
    progress_percent: float | None


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
    remaining_seconds = int((effective_due_at - anchor).total_seconds())
    return SLAMetrics(
        base_due_at=base_due_at,
        due_at=effective_due_at,
        elapsed_seconds=elapsed_seconds,
        remaining_seconds=remaining_seconds,
        progress_percent=round(elapsed_seconds * 100 / target_seconds, 2),
    )
