from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.ticket import TicketUserBrief


class RatingCreateRequest(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2_000)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "score": 5,
                "comment": "Nhân viên hỗ trợ nhanh và hướng dẫn rõ ràng.",
            }
        },
    )

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RatingResponse(BaseModel):
    rating_id: int
    ticket_id: int
    rated_by: TicketUserBrief
    score: int
    comment: str | None
    created_at: datetime
