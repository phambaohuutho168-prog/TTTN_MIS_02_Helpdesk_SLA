from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_required(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Nội dung không được để trống.")
    return normalized


class TransitionReasonRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class RequestInfoRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        return _strip_required(value)


class ProvideInfoRequest(RequestInfoRequest):
    pass


class ResolveRequest(BaseModel):
    resolution_note: str = Field(min_length=5, max_length=8000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("resolution_note")
    @classmethod
    def normalize_resolution_note(cls, value: str) -> str:
        normalized = _strip_required(value)
        if len(normalized) < 5:
            raise ValueError("Kết quả xử lý phải có ít nhất 5 ký tự.")
        return normalized


class CloseRequest(TransitionReasonRequest):
    pass


class ReopenRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = _strip_required(value)
        if len(normalized) < 5:
            raise ValueError("Lý do phải có ít nhất 5 ký tự.")
        return normalized


class RejectRequest(ReopenRequest):
    pass
