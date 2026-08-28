from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_name(value: object) -> object:
    if not isinstance(value, str):
        return value
    return " ".join(value.split())


def _normalize_description(value: object) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    return stripped or None


class CategoryCreateRequest(BaseModel):
    category_name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    model_config = ConfigDict(extra="forbid")

    _clean_name = field_validator("category_name", mode="before")(_normalize_name)
    _clean_description = field_validator("description", mode="before")(
        _normalize_description
    )


class CategoryUpdateRequest(BaseModel):
    category_name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")

    _clean_name = field_validator("category_name", mode="before")(_normalize_name)
    _clean_description = field_validator("description", mode="before")(
        _normalize_description
    )

    @model_validator(mode="after")
    def require_update_field(self):
        if not self.model_fields_set:
            raise ValueError("Cần cung cấp ít nhất một trường để cập nhật.")
        if "category_name" in self.model_fields_set and self.category_name is None:
            raise ValueError("category_name không được là null.")
        return self


class CategoryResponse(BaseModel):
    category_id: int
    category_name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PriorityCreateRequest(BaseModel):
    priority_code: str = Field(pattern=r"^P[1-4]$")
    priority_level: int = Field(ge=1, le=4)
    priority_name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("priority_code", mode="before")
    @classmethod
    def normalize_priority_code(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    _clean_name = field_validator("priority_name", mode="before")(_normalize_name)
    _clean_description = field_validator("description", mode="before")(
        _normalize_description
    )

class PriorityUpdateRequest(BaseModel):
    priority_name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")

    _clean_name = field_validator("priority_name", mode="before")(_normalize_name)
    _clean_description = field_validator("description", mode="before")(
        _normalize_description
    )

    @model_validator(mode="after")
    def require_update_field(self):
        if not self.model_fields_set:
            raise ValueError("Cần cung cấp ít nhất một trường để cập nhật.")
        if "priority_name" in self.model_fields_set and self.priority_name is None:
            raise ValueError("priority_name không được là null.")
        return self


class PriorityResponse(BaseModel):
    priority_id: int
    priority_code: str
    priority_level: int
    priority_name: str
    description: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TicketStatusResponse(BaseModel):
    status_code: str
    status_name: str
    is_terminal: bool
    description: str | None

    model_config = ConfigDict(from_attributes=True)
