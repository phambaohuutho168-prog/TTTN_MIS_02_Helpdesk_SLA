from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NotificationListQuery(BaseModel):
    is_read: bool | None = None
    type: str | None = Field(default=None, max_length=30)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("type")
    @classmethod
    def normalize_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None


class NotificationResponse(BaseModel):
    notification_id: int
    ticket_id: int | None
    sla_event_id: int | None
    type: str
    title: str
    message: str
    is_read: bool
    deep_link: str | None
    created_at: datetime
    read_at: datetime | None
    updated_at: datetime


class BulkUpdateResponse(BaseModel):
    updated_count: int = Field(ge=0)
