from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator


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
