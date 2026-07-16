"""Pydantic request and response schemas."""

from app.schemas.common import ErrorResponse, PaginatedResponse, PaginationParams
from app.schemas.job_search import (
    DatePosted,
    EmploymentType,
    ExperienceLevel,
    JobSearchRequest,
    WorkplaceType,
)
from app.schemas.scraping_job import (
    ScrapingJobCreateResponse,
    ScrapingJobDetail,
    ScrapingJobListResponse,
    ScrapingJobSummary,
)

__all__ = [
    "DatePosted",
    "EmploymentType",
    "ErrorResponse",
    "ExperienceLevel",
    "JobSearchRequest",
    "PaginatedResponse",
    "PaginationParams",
    "ScrapingJobCreateResponse",
    "ScrapingJobDetail",
    "ScrapingJobListResponse",
    "ScrapingJobSummary",
    "WorkplaceType",
]
