from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator


class AuditLogQuery(BaseModel):
    actor_user_id: PositiveInt | None = None
    ticket_id: PositiveInt | None = None
    action_code: str | None = Field(default=None, min_length=1, max_length=80)
    entity_type: str | None = Field(default=None, min_length=1, max_length=80)
    entity_id: PositiveInt | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("action_code", "entity_type")
    @classmethod
    def normalize_codes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Giá trị bộ lọc không được để trống")
        return normalized

    @field_validator("created_from", "created_to")
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
            self.created_from is not None
            and self.created_to is not None
            and self.created_from > self.created_to
        ):
            raise ValueError("created_from phải nhỏ hơn hoặc bằng created_to")
        return self


class AuditLogResponse(BaseModel):
    audit_id: int
    actor_user_id: int | None
    ticket_id: int | None
    action_code: str
    entity_type: str
    entity_id: int | None
    old_value_json: dict[str, Any] | None
    new_value_json: dict[str, Any] | None
    reason: str | None
    ip_address: str | None
    request_id: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
