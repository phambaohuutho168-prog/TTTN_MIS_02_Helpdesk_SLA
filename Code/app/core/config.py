from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Hệ thống Helpdesk SLA"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    BUILD_ID: str = "local"

    SECRET_KEY: SecretStr = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "helpdesk-sla"
    JWT_AUDIENCE: str = "helpdesk-sla-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(15, ge=1, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(7, ge=1, le=30)

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    LOGIN_MAX_ATTEMPTS: int = Field(5, ge=1, le=20)
    LOGIN_RATE_LIMIT_SECONDS: int = Field(300, ge=10, le=3600)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def reject_placeholder_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value().upper()
        if "REPLACE_WITH" in secret or "CHANGE_ME" in secret:
            raise ValueError("SECRET_KEY phải được thay bằng giá trị ngẫu nhiên cục bộ")
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_driver(cls, value: str) -> str:
        allowed = ("postgresql+asyncpg://", "sqlite+aiosqlite://")
        if not value.startswith(allowed):
            raise ValueError("DATABASE_URL phải dùng asyncpg hoặc aiosqlite")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
