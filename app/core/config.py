from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://certuser:certpass@localhost:5432/certdb"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # Storage
    storage_root: str = "storage"

    # Limits
    max_recipients_per_job: int = 500
    batch_size: int = 50

    # Certificate font — empty means use built-in Helvetica fallback
    certificate_font_path: str = ""

    # Logging
    log_level: str = "INFO"

    @field_validator("max_recipients_per_job", "batch_size", mode="before")
    @classmethod
    def _positive_int(cls, v: object) -> object:
        value = int(v)  # type: ignore[arg-type]
        if value < 1:
            raise ValueError("Must be a positive integer")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
