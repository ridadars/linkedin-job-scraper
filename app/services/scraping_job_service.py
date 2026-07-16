"""Scraping job creation and retrieval service."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.enums import ScrapingJobStatus
from app.models.scraping_job import ScrapingJob
from app.schemas.job_search import JobSearchRequest
from app.services.search_url_service import build_linkedin_jobs_url
from app.utils.search_normalizer import enum_to_storage_value


class ScrapingJobNotFoundError(Exception):
    """Raised when a scraping job ID does not exist."""


class InvalidScrapingJobIdError(Exception):
    """Raised when a scraping job ID is not a valid UUID."""


def validate_scraping_job_id(job_id: str) -> str:
    """Validate UUID format for scraping job identifiers."""
    try:
        parsed = uuid.UUID(job_id)
    except (ValueError, AttributeError) as exc:
        raise InvalidScrapingJobIdError(
            "Invalid scraping job ID format. Expected a UUID."
        ) from exc
    return str(parsed)


def _storage_filters(search_request: JobSearchRequest) -> dict[str, object]:
    """Convert search request enums to consistent database string values."""
    return {
        "keywords": search_request.keywords,
        "location": search_request.location,
        "experience_level": enum_to_storage_value(search_request.experience_level),
        "employment_type": enum_to_storage_value(search_request.employment_type),
        "workplace_type": enum_to_storage_value(search_request.workplace_type),
        "date_posted": enum_to_storage_value(search_request.date_posted),
        "easy_apply_only": search_request.easy_apply_only,
        "max_jobs": search_request.max_jobs,
    }


def _find_recent_duplicate(
    db: Session,
    filters: dict[str, object],
    settings: Settings,
) -> ScrapingJob | None:
    """Return a recent pending job with identical filters, if one exists."""
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.duplicate_search_window_seconds)

    query = (
        select(ScrapingJob)
        .where(
            ScrapingJob.status == ScrapingJobStatus.PENDING.value,
            ScrapingJob.created_at >= cutoff,
            ScrapingJob.keywords == filters["keywords"],
            ScrapingJob.location == filters["location"],
            ScrapingJob.experience_level == filters["experience_level"],
            ScrapingJob.employment_type == filters["employment_type"],
            ScrapingJob.workplace_type == filters["workplace_type"],
            ScrapingJob.date_posted == filters["date_posted"],
            ScrapingJob.easy_apply_only == filters["easy_apply_only"],
            ScrapingJob.max_jobs == filters["max_jobs"],
        )
        .order_by(desc(ScrapingJob.created_at))
        .limit(1)
    )
    return db.execute(query).scalar_one_or_none()


def create_scraping_job(
    db: Session,
    search_request: JobSearchRequest,
    settings: Settings,
) -> tuple[ScrapingJob, bool]:
    """Create or reuse a pending scraping job for the given search request."""
    filters = _storage_filters(search_request)
    existing = _find_recent_duplicate(db, filters, settings)
    if existing is not None:
        return existing, True

    search_url = build_linkedin_jobs_url(search_request)
    scraping_job = ScrapingJob(
        keywords=filters["keywords"],  # type: ignore[arg-type]
        location=filters["location"],  # type: ignore[arg-type]
        experience_level=filters["experience_level"],  # type: ignore[arg-type]
        employment_type=filters["employment_type"],  # type: ignore[arg-type]
        workplace_type=filters["workplace_type"],  # type: ignore[arg-type]
        date_posted=filters["date_posted"],  # type: ignore[arg-type]
        easy_apply_only=filters["easy_apply_only"],  # type: ignore[arg-type]
        max_jobs=filters["max_jobs"],  # type: ignore[arg-type]
        search_url=search_url,
        status=ScrapingJobStatus.PENDING.value,
        discovered_jobs=0,
        processed_jobs=0,
        successful_jobs=0,
        duplicate_jobs=0,
        failed_jobs=0,
    )
    db.add(scraping_job)
    db.commit()
    db.refresh(scraping_job)
    return scraping_job, False


def get_scraping_job(db: Session, job_id: str) -> ScrapingJob:
    """Fetch a scraping job by ID or raise a domain error."""
    validate_scraping_job_id(job_id)
    scraping_job = db.get(ScrapingJob, job_id)
    if scraping_job is None:
        raise ScrapingJobNotFoundError(f"Scraping job '{job_id}' was not found.")
    return scraping_job


def list_scraping_jobs(
    db: Session,
    page: int,
    page_size: int,
) -> tuple[list[ScrapingJob], int]:
    """Return paginated scraping jobs ordered newest first."""
    total_records = db.scalar(select(func.count()).select_from(ScrapingJob)) or 0
    offset = (page - 1) * page_size
    jobs = db.scalars(
        select(ScrapingJob)
        .order_by(desc(ScrapingJob.created_at))
        .offset(offset)
        .limit(page_size)
    ).all()
    return list(jobs), total_records


def calculate_total_pages(total_records: int, page_size: int) -> int:
    """Calculate total pages for pagination metadata."""
    if total_records == 0:
        return 0
    return math.ceil(total_records / page_size)
