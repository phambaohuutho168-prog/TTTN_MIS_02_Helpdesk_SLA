from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories import dashboard_repository
from app.schemas.dashboard import (
    CategoryCount,
    DashboardOverviewResponse,
    DashboardPeriod,
    DashboardQuery,
    PriorityCount,
    RatingScoreCount,
    SatisfactionSummary,
    SLAResultSummary,
    SLAPerformanceResponse,
    SLATrendItem,
    StatusCount,
    TicketCounts,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _average_minutes(
    rows: list[tuple[datetime, datetime | None, datetime | None]],
    *,
    timestamp_index: int,
) -> tuple[float | None, int]:
    durations = []
    for row in rows:
        completed_at = row[timestamp_index]
        if completed_at is not None:
            durations.append(
                max(
                    0.0,
                    (_as_utc(completed_at) - _as_utc(row[0])).total_seconds(),
                )
                / 60
            )
    if not durations:
        return None, 0
    return round(sum(durations) / len(durations), 2), len(durations)


def _sla_summary(result_codes: list[str]) -> SLAResultSummary:
    counts = Counter(result_codes)
    met = counts["MET"]
    breached = counts["BREACHED"]
    total = met + breached
    return SLAResultSummary(
        met=met,
        breached=breached,
        total=total,
        compliance_rate=(round(met * 100 / total, 2) if total else None),
    )


def _overall_sla_results(
    rows: list[tuple[int, datetime, str, str]],
) -> list[tuple[datetime, str]]:
    """Return one overall result per ticket that completed both SLA types."""
    grouped: dict[int, dict[str, object]] = {}
    for ticket_id, created_at, sla_type, result_code in rows:
        if result_code not in {"MET", "BREACHED"}:
            continue
        ticket = grouped.setdefault(
            ticket_id,
            {"created_at": created_at, "RESPONSE": [], "RESOLUTION": []},
        )
        ticket[sla_type].append(result_code)

    results = []
    for ticket in grouped.values():
        response_codes = ticket["RESPONSE"]
        resolution_codes = ticket["RESOLUTION"]
        if not response_codes or not resolution_codes:
            continue
        all_codes = [*response_codes, *resolution_codes]
        overall = "MET" if all(code == "MET" for code in all_codes) else "BREACHED"
        results.append((ticket["created_at"], overall))
    return results


def _period(query: DashboardQuery) -> DashboardPeriod:
    return DashboardPeriod(
        date_from=query.date_from,
        date_to=query.date_to,
    )


async def get_dashboard_overview(
    session: AsyncSession,
    *,
    current_user: User,
    query: DashboardQuery,
) -> DashboardOverviewResponse:
    conditions = dashboard_repository.ticket_conditions(
        query,
        current_user_id=current_user.user_id,
        role_codes=set(current_user.role_codes),
    )
    reopened_conditions = dashboard_repository.ticket_conditions(
        query,
        current_user_id=current_user.user_id,
        role_codes=set(current_user.role_codes),
        include_created_period=False,
    )
    status_rows = await dashboard_repository.status_counts(
        session,
        conditions=conditions,
    )
    category_rows = await dashboard_repository.category_counts(
        session,
        conditions=conditions,
    )
    priority_rows = await dashboard_repository.priority_counts(
        session,
        conditions=conditions,
    )
    duration_rows = await dashboard_repository.ticket_duration_rows(
        session,
        conditions=conditions,
    )
    reopened = await dashboard_repository.reopened_ticket_count(
        session,
        conditions=reopened_conditions,
        date_from=query.date_from,
        date_to=query.date_to,
    )
    scores = await dashboard_repository.rating_scores(
        session,
        conditions=conditions,
    )
    sla_rows = await dashboard_repository.sla_result_rows(
        session,
        conditions=conditions,
    )
    overall_sla_rows = _overall_sla_results(sla_rows)

    by_status = [
        StatusCount(
            status_code=status_code,
            status_name=status_name,
            count=count,
        )
        for status_code, status_name, _is_terminal, count in status_rows
    ]
    by_status.sort(key=lambda item: (-item.count, item.status_code))
    status_counts = {
        status_code: count
        for status_code, _status_name, _is_terminal, count in status_rows
    }
    total = sum(status_counts.values())
    closed = status_counts.get("CLOSED", 0)
    rejected = status_counts.get("REJECTED", 0)
    open_count = sum(
        count
        for _status_code, _status_name, is_terminal, count in status_rows
        if not is_terminal
    )
    first_response_average, first_response_samples = _average_minutes(
        duration_rows,
        timestamp_index=1,
    )
    resolution_average, resolution_samples = _average_minutes(
        duration_rows,
        timestamp_index=2,
    )
    score_counts = Counter(scores)

    return DashboardOverviewResponse(
        period=_period(query),
        ticket_counts=TicketCounts(
            total=total,
            open=open_count,
            closed=closed,
            rejected=rejected,
            reopened=reopened,
        ),
        by_status=by_status,
        by_category=sorted(
            [
                CategoryCount(
                    category_id=category_id,
                    category_name=category_name,
                    count=count,
                )
                for category_id, category_name, count in category_rows
            ],
            key=lambda item: (-item.count, item.category_id),
        ),
        by_priority=sorted(
            [
                PriorityCount(
                    priority_id=priority_id,
                    priority_code=priority_code,
                    priority_name=priority_name,
                    count=count,
                )
                for priority_id, priority_code, priority_name, count in priority_rows
            ],
            key=lambda item: (-item.count, item.priority_id),
        ),
        average_first_response_minutes=first_response_average,
        first_response_sample_size=first_response_samples,
        average_resolution_minutes=resolution_average,
        resolution_sample_size=resolution_samples,
        sla_compliance=_sla_summary([result for _created, result in overall_sla_rows]),
        satisfaction=SatisfactionSummary(
            rated_tickets=len(scores),
            average_score=(round(sum(scores) / len(scores), 2) if scores else None),
            by_score=[
                RatingScoreCount(score=score, count=score_counts.get(score, 0))
                for score in range(1, 6)
            ],
        ),
    )


async def get_sla_performance(
    session: AsyncSession,
    *,
    current_user: User,
    query: DashboardQuery,
) -> SLAPerformanceResponse:
    conditions = dashboard_repository.ticket_conditions(
        query,
        current_user_id=current_user.user_id,
        role_codes=set(current_user.role_codes),
    )
    rows = await dashboard_repository.sla_result_rows(
        session,
        conditions=conditions,
    )
    eligible = [row for row in rows if row[3] in {"MET", "BREACHED"}]
    response_codes = [row[3] for row in eligible if row[2] == "RESPONSE"]
    resolution_codes = [row[3] for row in eligible if row[2] == "RESOLUTION"]
    overall_rows = _overall_sla_results(rows)
    trend_codes: dict = defaultdict(list)
    for created_at, result_code in overall_rows:
        trend_codes[_as_utc(created_at).date()].append(result_code)
    trend = []
    for day in sorted(trend_codes):
        summary = _sla_summary(trend_codes[day])
        trend.append(
            SLATrendItem(
                date=day,
                met=summary.met,
                breached=summary.breached,
                total=summary.total,
                compliance_rate=summary.compliance_rate,
            )
        )
    return SLAPerformanceResponse(
        period=_period(query),
        response=_sla_summary(response_codes),
        resolution=_sla_summary(resolution_codes),
        overall=_sla_summary([result_code for _created, result_code in overall_rows]),
        excluded_not_applicable=sum(
            1 for _ticket_id, _created, _sla_type, result_code in rows
            if result_code == "NOT_APPLICABLE"
        ),
        trend=trend,
    )
