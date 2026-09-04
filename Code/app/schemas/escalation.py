from datetime import datetime, timezone
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)

from app.schemas.ticket import PriorityBrief, TicketUserBrief


SLAEventType = Literal["WARNING", "OVERDUE", "ESCALATED"]
SLAType = Literal["RESPONSE", "RESOLUTION"]


class SLABreachQuery(BaseModel):
    state: list[SLAEventType] | None = None
    sla_type: SLAType | None = None
    ticket_id: PositiveInt | None = None
    triggered_from: datetime | None = None
    triggered_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("state", mode="before")
    @classmethod
    def normalize_states(cls, value):
        if value is None:
            return None
        values = [value] if isinstance(value, str) else value
        normalized = []
        for item in values:
            normalized.extend(
                part.strip().upper()
                for part in str(item).split(",")
                if part.strip()
            )
        return list(dict.fromkeys(normalized)) or None

    @field_validator("triggered_from", "triggered_to")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Thời gian phải kèm múi giờ ISO 8601")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_time_range(self):
        if (
            self.triggered_from is not None
            and self.triggered_to is not None
            and self.triggered_from > self.triggered_to
        ):
            raise ValueError("triggered_from phải nhỏ hơn hoặc bằng triggered_to")
        return self


class SLAEventTicketBrief(BaseModel):
    ticket_id: int
    ticket_code: str
    title: str
    current_status_code: str
    priority: PriorityBrief


class SLAEventResponse(BaseModel):
    sla_event_id: int
    ticket_sla_id: int
    sla_type: SLAType
    cycle_no: int
    ticket: SLAEventTicketBrief
    due_at: datetime
    effective_due_at: datetime
    threshold_percent: int
    state: SLAEventType
    triggered_at: datetime
    current_assignee: TicketUserBrief | None
    recipients: list[TicketUserBrief]


class SLAEscalationRunResponse(BaseModel):
    scanned_runtimes: int
    created_events: int
    created_notifications: int
    skipped_without_recipient: int

    model_config = ConfigDict(from_attributes=True)
