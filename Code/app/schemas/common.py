from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ResponseMeta(BaseModel):
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ErrorItem(BaseModel):
    field: str | None = None
    message: str


class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    code: str = "SUCCESS"
    message: str
    data: T
    meta: ResponseMeta


class ErrorResponse(BaseModel):
    success: bool = False
    code: str
    message: str
    errors: list[ErrorItem] = Field(default_factory=list)
    meta: ResponseMeta
