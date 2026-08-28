from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator


class AssignmentRequest(BaseModel):
    assignee_id: PositiveInt
    reason: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None
