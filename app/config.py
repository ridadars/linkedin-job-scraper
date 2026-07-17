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
    browser_name: str = Field(default="chromium", alias="BROWSER_NAME")
    request_delay_seconds: float = Field(default=8.0, alias="REQUEST_DELAY_SECONDS")
    max_jobs_per_search: int = Field(default=50, alias="MAX_JOBS_PER_SEARCH")
    default_max_jobs: int = Field(default=20, alias="DEFAULT_MAX_JOBS")
    duplicate_search_window_seconds: int = Field(
        default=60,
        alias="DUPLICATE_SEARCH_WINDOW_SECONDS",
    )
    page_timeout_seconds: int = Field(default=30, alias="PAGE_TIMEOUT_SECONDS")
    navigation_timeout_seconds: int = Field(
        default=30,
        alias="NAVIGATION_TIMEOUT_SECONDS",
    )
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    max_scroll_attempts: int = Field(default=5, alias="MAX_SCROLL_ATTEMPTS")
    scroll_wait_seconds: float = Field(default=1.0, alias="SCROLL_WAIT_SECONDS")
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

    @field_validator("page_timeout_seconds", "navigation_timeout_seconds")
    @classmethod
    def validate_positive_timeouts(cls, value: int) -> int:
        """Timeouts must be greater than zero."""
        if value <= 0:
            raise ValueError("Timeout values must be greater than 0.")
        return value

    @field_validator("request_delay_seconds", "scroll_wait_seconds")
    @classmethod
    def validate_non_negative_delays(cls, value: float) -> float:
        """Delays must be zero or greater."""
        if value < 0:
            raise ValueError("Delay values must be 0 or greater.")
        return value

    @field_validator("max_retries")
    @classmethod
    def validate_max_retries(cls, value: int) -> int:
        """MAX_RETRIES must be between 0 and 5 inclusive."""
        if not 0 <= value <= 5:
            raise ValueError("MAX_RETRIES must be between 0 and 5.")
        return value

    @field_validator("max_scroll_attempts")
    @classmethod
    def validate_max_scroll_attempts(cls, value: int) -> int:
        """MAX_SCROLL_ATTEMPTS must be between 0 and 10 inclusive."""
        if not 0 <= value <= 10:
            raise ValueError("MAX_SCROLL_ATTEMPTS must be between 0 and 10.")
        return value

    @field_validator("browser_name")
    @classmethod
    def validate_browser_name(cls, value: str) -> str:
        """Only Chromium is supported for now."""
        normalized = value.strip().lower()
        if normalized != "chromium":
            raise ValueError("BROWSER_NAME only supports 'chromium' for now.")
        return normalized

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
