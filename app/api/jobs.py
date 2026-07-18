"""Canonical job listing, detail, and global export endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db_session
from app.models.linkedin_job import LinkedInJob
from app.schemas.common import PaginatedResponse
from app.schemas.job_result import JobItem, JobListResponse
from app.services import export_service
from app.services.jobs_query_service import JobFilters, query_all_jobs, query_jobs
from app.services.scraping_job_service import calculate_total_pages
from app.utils.export_response import csv_response, json_download_response

jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])
export_router = APIRouter(prefix="/export", tags=["export"])


def _filters(
    keyword: str | None,
    company: str | None,
    location: str | None,
    country: str | None,
    workplace_type: str | None,
    employment_type: str | None,
    experience_level: str | None,
    skill: str | None,
    easy_apply: bool | None,
    posted_after: datetime | None,
    posted_before: datetime | None,
) -> JobFilters:
    return JobFilters(
        keyword=keyword,
        company=company,
        location=location,
        country=country,
        workplace_type=workplace_type,
        employment_type=employment_type,
        experience_level=experience_level,
        skill=skill,
        easy_apply=easy_apply,
        posted_after=posted_after,
        posted_before=posted_before,
    )


# Shared query-parameter dependency signature for filters.
def filter_params(
    keyword: str | None = Query(default=None),
    company: str | None = Query(default=None),
    location: str | None = Query(default=None),
    country: str | None = Query(default=None),
    workplace_type: str | None = Query(default=None),
    employment_type: str | None = Query(default=None),
    experience_level: str | None = Query(default=None),
    skill: str | None = Query(default=None),
    easy_apply: bool | None = Query(default=None),
    posted_after: datetime | None = Query(default=None),
    posted_before: datetime | None = Query(default=None),
) -> JobFilters:
    """Collect the shared job filters from query parameters."""
    return _filters(
        keyword, company, location, country, workplace_type, employment_type,
        experience_level, skill, easy_apply, posted_after, posted_before,
    )


@jobs_router.get("", response_model=JobListResponse)
def list_jobs(
    filters: JobFilters = Depends(filter_params),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="newest", pattern="^(newest|oldest)$"),
    db: Session = Depends(get_db_session),
) -> JobListResponse:
    """List canonical jobs with filtering, sorting, and pagination."""
    jobs, total = query_jobs(db, filters, page, page_size, sort)
    return JobListResponse(
        pagination=PaginatedResponse(
            page=page,
            page_size=page_size,
            total_records=total,
            total_pages=calculate_total_pages(total, page_size),
        ),
        items=[JobItem.from_orm_job(job) for job in jobs],
    )


@jobs_router.get("/{job_id}", response_model=JobItem)
def get_job(job_id: str, db: Session = Depends(get_db_session)) -> JobItem:
    """Return a single canonical job by its internal id."""
    job = db.get(LinkedInJob, job_id)
    if job is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' was not found."
        )
    return JobItem.from_orm_job(job)


def _filters_metadata(filters: JobFilters) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v)
            for k, v in filters.__dict__.items() if v is not None}


@export_router.get("/csv")
def export_jobs_csv(
    filters: JobFilters = Depends(filter_params),
    sort: str = Query(default="newest", pattern="^(newest|oldest)$"),
    db: Session = Depends(get_db_session),
) -> Response:
    """Export all filtered canonical jobs as CSV."""
    jobs = query_all_jobs(db, filters, sort)
    items = [JobItem.from_orm_job(job) for job in jobs]
    content = export_service.jobs_to_csv(items)
    filename = export_service.safe_filename("linkedin_jobs", "csv")
    return csv_response(content, filename)


@export_router.get("/json")
def export_jobs_json(
    filters: JobFilters = Depends(filter_params),
    sort: str = Query(default="newest", pattern="^(newest|oldest)$"),
    db: Session = Depends(get_db_session),
) -> Response:
    """Export all filtered canonical jobs as JSON."""
    jobs = query_all_jobs(db, filters, sort)
    items = [JobItem.from_orm_job(job) for job in jobs]
    payload = export_service.jobs_to_json(
        items, metadata={"filters": _filters_metadata(filters), "sort": sort}
    )
    filename = export_service.safe_filename("linkedin_jobs", "json")
    return json_download_response(payload, filename)
