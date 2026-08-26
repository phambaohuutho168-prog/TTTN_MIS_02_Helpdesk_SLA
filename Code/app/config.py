from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Hệ Thống Helpdesk SLA"
    SECRET_KEY: str = "secret"
    DATABASE_URL: str = "sqlite:///./helpdesk.db"

    class Config:
        env_file = ".env"

settings = Settings()