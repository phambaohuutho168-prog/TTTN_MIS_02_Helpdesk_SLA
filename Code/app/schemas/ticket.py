import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class DepartmentBrief(BaseModel):
    department_id: int
    department_name: str

    model_config = ConfigDict(from_attributes=True)


class RoleBrief(BaseModel):
    role_id: int
    role_code: str
    role_name: str

    model_config = ConfigDict(from_attributes=True)


class UserDetail(BaseModel):
    user_id: int
    email: EmailStr
    full_name: str
    phone: str | None
    department: DepartmentBrief | None
    roles: list[RoleBrief]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.split())
        if not value:
            raise ValueError("Họ tên không được để trống")
        return value

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = re.sub(r"[\s().-]", "", value)
        if value == "":
            return None
        if not re.fullmatch(r"\+?[0-9]{8,15}", value):
            raise ValueError("Số điện thoại không hợp lệ")
        return value

    @model_validator(mode="after")
    def require_at_least_one_field(self):
        if "full_name" not in self.model_fields_set and "phone" not in self.model_fields_set:
            raise ValueError("Cần cung cấp ít nhất full_name hoặc phone")
        return self
