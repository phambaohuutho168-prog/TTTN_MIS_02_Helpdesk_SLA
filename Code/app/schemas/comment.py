from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


CommentVisibility = Literal["PUBLIC", "INTERNAL"]
CommentType = Literal["REPLY", "REQUEST_INFO", "SYSTEM_NOTE"]


class CommentCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4_000)
    visibility: CommentVisibility = "PUBLIC"
    comment_type: CommentType = "REPLY"

    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Nội dung trao đổi không được để trống")
        return normalized


class CommentUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4_000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Nội dung trao đổi không được để trống")
        return normalized
