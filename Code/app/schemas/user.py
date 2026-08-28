import re
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)


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


class AdminUserCreateRequest(BaseModel):
    email: EmailStr = Field(max_length=254)
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=30)
    department_id: PositiveInt | None = None
    role_ids: list[PositiveInt] = Field(min_length=1, max_length=3)
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Họ tên không được để trống")
        return normalized

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return _normalize_phone(value)

    @field_validator("role_ids")
    @classmethod
    def require_unique_roles(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("role_ids không được chứa giá trị trùng lặp")
        return value


class AdminUserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    department_id: PositiveInt | None = None
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Họ tên không được là null")
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Họ tên không được để trống")
        return normalized

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return _normalize_phone(value)

    @field_validator("is_active")
    @classmethod
    def reject_null_status(cls, value: bool | None) -> bool | None:
        if value is None:
            raise ValueError("is_active không được là null")
        return value

    @model_validator(mode="after")
    def require_at_least_one_field(self):
        allowed_fields = {"full_name", "phone", "department_id", "is_active"}
        if not self.model_fields_set.intersection(allowed_fields):
            raise ValueError("Cần cung cấp ít nhất một trường để cập nhật")
        return self


class RoleResponse(BaseModel):
    role_id: int
    role_code: str
    role_name: str
    description: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class DepartmentResponse(BaseModel):
    department_id: int
    department_name: str
    description: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


def _normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"[\s().-]", "", value)
    if normalized == "":
        return None
    if not re.fullmatch(r"\+?[0-9]{8,15}", normalized):
        raise ValueError("Số điện thoại không hợp lệ")
    return normalized
