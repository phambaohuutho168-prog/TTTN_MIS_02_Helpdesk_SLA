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


TicketSort = Literal[
    "created_at",
    "-created_at",
    "priority_level",
    "-priority_level",
    "updated_at",
    "-updated_at",
]


class TicketListQuery(BaseModel):
    status: list[str] | None = None
    category_id: PositiveInt | None = None
    priority_id: PositiveInt | None = None
    requester_id: PositiveInt | None = None
    assignee_id: PositiveInt | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    q: str | None = Field(default=None, max_length=100)
    sort: TicketSort = "-created_at"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("status", mode="before")
    @classmethod
    def normalize_statuses(cls, value):
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
        if not normalized:
            return None
        return list(dict.fromkeys(normalized))

    @field_validator("created_from", "created_to")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Thời gian phải kèm múi giờ ISO 8601")
        return value.astimezone(timezone.utc)

    @field_validator("q")
    @classmethod
    def normalize_search(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @model_validator(mode="after")
    def validate_time_range(self):
        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from > self.created_to
        ):
            raise ValueError("created_from phải nhỏ hơn hoặc bằng created_to")
        return self


class TicketCreateRequest(BaseModel):
    title: str = Field(min_length=5, max_length=255)
    description: str = Field(min_length=10, max_length=10_000)
    category_id: PositiveInt
    priority_id: PositiveInt

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "description")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Nội dung không được để trống")
        return normalized


class CategoryBrief(BaseModel):
    category_id: int
    category_name: str

    model_config = ConfigDict(from_attributes=True)


class PriorityBrief(BaseModel):
    priority_id: int
    priority_code: str
    priority_level: int
    priority_name: str

    model_config = ConfigDict(from_attributes=True)


class TicketStatusBrief(BaseModel):
    status_code: str
    status_name: str
    is_terminal: bool

    model_config = ConfigDict(from_attributes=True)


class TicketUserBrief(BaseModel):
    user_id: int
    email: str
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class TicketSummaryResponse(BaseModel):
    ticket_id: int
    ticket_code: str
    title: str
    category: CategoryBrief
    priority: PriorityBrief
    status: TicketStatusBrief
    requester: TicketUserBrief
    current_assignee: TicketUserBrief | None
    created_at: datetime
    updated_at: datetime


class TicketDetail(BaseModel):
    ticket_id: int
    ticket_code: str
    requester_id: int
    category_id: int
    priority_id: int
    current_status_code: str
    title: str
    description: str
    first_response_at: datetime | None
    closed_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    category: CategoryBrief
    priority: PriorityBrief
    current_status: TicketStatusBrief

    model_config = ConfigDict(from_attributes=True)
