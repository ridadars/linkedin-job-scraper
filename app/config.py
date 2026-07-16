"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with sensible defaults for local development."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="LinkedIn Job Scraper", alias="APP_NAME")
    debug: bool = Field(default=False, alias="DEBUG")
    database_url: str = Field(
        default="sqlite:///./linkedin_jobs.db",
        alias="DATABASE_URL",
    )
    headless: bool = Field(default=True, alias="HEADLESS")
    request_delay_seconds: float = Field(default=8.0, alias="REQUEST_DELAY_SECONDS")
    max_jobs_per_search: int = Field(default=50, alias="MAX_JOBS_PER_SEARCH")
    default_max_jobs: int = Field(default=20, alias="DEFAULT_MAX_JOBS")
    duplicate_search_window_seconds: int = Field(
        default=60,
        alias="DUPLICATE_SEARCH_WINDOW_SECONDS",
    )
    page_timeout_seconds: int = Field(default=30, alias="PAGE_TIMEOUT_SECONDS")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    export_directory: str = Field(default="exports", alias="EXPORT_DIRECTORY")
    cors_origins: str = Field(
        default="http://localhost:8000,http://127.0.0.1:8000",
        alias="CORS_ORIGINS",
    )

    @field_validator("max_jobs_per_search", "default_max_jobs", "duplicate_search_window_seconds")
    @classmethod
    def validate_positive_integers(cls, value: int) -> int:
        """Ensure numeric configuration values are positive."""
        if value < 1:
            raise ValueError("Configuration values must be at least 1.")
        return value

    @model_validator(mode="after")
    def validate_max_jobs_configuration(self) -> "Settings":
        """Ensure default_max_jobs does not exceed max_jobs_per_search."""
        if self.default_max_jobs > self.max_jobs_per_search:
            raise ValueError(
                "DEFAULT_MAX_JOBS must not exceed MAX_JOBS_PER_SEARCH."
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def export_path(self) -> Path:
        """Return the export directory as a Path object."""
        return Path(self.export_directory)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
