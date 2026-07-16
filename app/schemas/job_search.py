"""Job search request and filter enums."""

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import get_settings
from app.utils.search_normalizer import (
    MAX_KEYWORDS_LENGTH,
    MAX_LOCATION_LENGTH,
    normalize_keywords,
    normalize_location,
)


class ExperienceLevel(StrEnum):
    """Supported LinkedIn experience-level filters."""

    INTERNSHIP = "internship"
    ENTRY_LEVEL = "entry_level"
    ASSOCIATE = "associate"
    MID_SENIOR = "mid_senior"
    DIRECTOR = "director"
    EXECUTIVE = "executive"


class EmploymentType(StrEnum):
    """Supported LinkedIn employment-type filters."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    VOLUNTEER = "volunteer"


class WorkplaceType(StrEnum):
    """Supported LinkedIn workplace-type filters."""

    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"


class DatePosted(StrEnum):
    """Supported LinkedIn date-posted filters."""

    ANY_TIME = "any_time"
    PAST_24_HOURS = "past_24_hours"
    PAST_WEEK = "past_week"
    PAST_MONTH = "past_month"


class JobSearchRequest(BaseModel):
    """Validated request payload for creating a LinkedIn job search."""

    keywords: str = Field(
        ...,
        min_length=1,
        max_length=MAX_KEYWORDS_LENGTH,
        description="Job title or search keywords.",
    )
    location: str | None = Field(
        default=None,
        max_length=MAX_LOCATION_LENGTH,
        description="Geographic location for the search.",
    )
    experience_level: ExperienceLevel | None = Field(
        default=None,
        description="Experience level filter.",
    )
    employment_type: EmploymentType | None = Field(
        default=None,
        description="Employment type filter.",
    )
    workplace_type: WorkplaceType | None = Field(
        default=None,
        description="Workplace type filter.",
    )
    date_posted: DatePosted | None = Field(
        default=None,
        description="Date posted filter.",
    )
    easy_apply_only: bool = Field(
        default=False,
        description="Restrict results to Easy Apply listings.",
    )
    max_jobs: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of jobs to collect.",
    )

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, value: str) -> str:
        """Normalize and validate keywords."""
        return normalize_keywords(value)

    @field_validator("location")
    @classmethod
    def validate_location(cls, value: str | None) -> str | None:
        """Normalize and validate optional location."""
        return normalize_location(value)

    @model_validator(mode="after")
    def apply_defaults_and_limits(self) -> "JobSearchRequest":
        """Apply default max_jobs and enforce configured maximum."""
        settings = get_settings()
        if self.max_jobs is None:
            object.__setattr__(self, "max_jobs", settings.default_max_jobs)
        if self.max_jobs > settings.max_jobs_per_search:
            raise ValueError(
                f"max_jobs must not exceed {settings.max_jobs_per_search}."
            )
        return self
