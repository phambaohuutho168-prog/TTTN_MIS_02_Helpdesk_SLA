from datetime import date, datetime, timezone

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)


class DashboardQuery(BaseModel):
    date_from: datetime | None = Field(default=None, alias="from")
    date_to: datetime | None = Field(default=None, alias="to")
    category_id: PositiveInt | None = None
    priority_id: PositiveInt | None = None
    department_id: PositiveInt | None = None
    assignee_id: PositiveInt | None = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("date_from", "date_to")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Thời gian phải kèm múi giờ ISO 8601")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_range(self):
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError("from phải nhỏ hơn hoặc bằng to")
        return self


class DashboardPeriod(BaseModel):
    date_from: datetime | None = Field(serialization_alias="from")
    date_to: datetime | None = Field(serialization_alias="to")


class TicketCounts(BaseModel):
    total: int = Field(ge=0)
    open: int = Field(ge=0)
    closed: int = Field(ge=0)
    rejected: int = Field(ge=0)
    reopened: int = Field(ge=0)


class StatusCount(BaseModel):
    status_code: str
    status_name: str
    count: int = Field(ge=0)


class CategoryCount(BaseModel):
    category_id: int
    category_name: str
    count: int = Field(ge=0)


class PriorityCount(BaseModel):
    priority_id: int
    priority_code: str
    priority_name: str
    count: int = Field(ge=0)


class SLAResultSummary(BaseModel):
    met: int = Field(ge=0)
    breached: int = Field(ge=0)
    total: int = Field(ge=0)
    compliance_rate: float | None = Field(default=None, ge=0, le=100)


class RatingScoreCount(BaseModel):
    score: int = Field(ge=1, le=5)
    count: int = Field(ge=0)


class SatisfactionSummary(BaseModel):
    rated_tickets: int = Field(ge=0)
    average_score: float | None = Field(default=None, ge=1, le=5)
    by_score: list[RatingScoreCount]


class DashboardOverviewResponse(BaseModel):
    period: DashboardPeriod
    ticket_counts: TicketCounts
    by_status: list[StatusCount]
    by_category: list[CategoryCount]
    by_priority: list[PriorityCount]
    average_first_response_minutes: float | None = Field(default=None, ge=0)
    first_response_sample_size: int = Field(ge=0)
    average_resolution_minutes: float | None = Field(default=None, ge=0)
    resolution_sample_size: int = Field(ge=0)
    sla_compliance: SLAResultSummary
    satisfaction: SatisfactionSummary


class SLATrendItem(BaseModel):
    date: date
    met: int = Field(ge=0)
    breached: int = Field(ge=0)
    total: int = Field(ge=0)
    compliance_rate: float | None = Field(default=None, ge=0, le=100)


class SLAPerformanceResponse(BaseModel):
    period: DashboardPeriod
    response: SLAResultSummary
    resolution: SLAResultSummary
    overall: SLAResultSummary
    excluded_not_applicable: int = Field(ge=0)
    trend: list[SLATrendItem]
