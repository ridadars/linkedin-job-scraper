"""Scraping job API response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginatedResponse


class ScrapingJobCreateResponse(BaseModel):
    """Response returned when a new scraping job is created."""

    scraping_job_id: str
    status: str
    search_url: str
    message: str
    reused_existing: bool = Field(
        default=False,
        description="True when a recent identical pending job was reused.",
    )


class ScrapingJobSummary(BaseModel):
    """Summary view of a scraping job for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    keywords: str
    location: str | None
    experience_level: str | None
    employment_type: str | None
    workplace_type: str | None
    date_posted: str | None
    easy_apply_only: bool
    max_jobs: int
    status: str
    discovered_jobs: int
    processed_jobs: int
    successful_jobs: int
    duplicate_jobs: int
    failed_jobs: int
    created_at: datetime


class ScrapingJobDetail(ScrapingJobSummary):
    """Detailed view of a scraping job."""

    search_url: str | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None


class ScrapingJobListResponse(BaseModel):
    """Paginated list of scraping job summaries."""

    pagination: PaginatedResponse
    items: list[ScrapingJobSummary]
