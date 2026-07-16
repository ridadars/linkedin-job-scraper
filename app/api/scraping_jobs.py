"""Scraping job and search API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db_session, get_settings_dependency
from app.schemas.common import PaginatedResponse
from app.schemas.job_search import JobSearchRequest
from app.schemas.scraping_job import (
    ScrapingJobCreateResponse,
    ScrapingJobDetail,
    ScrapingJobListResponse,
    ScrapingJobSummary,
)
from app.services.scraping_job_service import (
    InvalidScrapingJobIdError,
    ScrapingJobNotFoundError,
    calculate_total_pages,
    create_scraping_job,
    get_scraping_job,
    list_scraping_jobs,
)

search_router = APIRouter(tags=["search"])
scraping_jobs_router = APIRouter(prefix="/scraping-jobs", tags=["scraping-jobs"])


@search_router.post(
    "/search-jobs",
    response_model=ScrapingJobCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def search_jobs(
    search_request: JobSearchRequest,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings_dependency),
) -> ScrapingJobCreateResponse:
    """Create a pending scraping job for a LinkedIn job search."""
    scraping_job, reused = create_scraping_job(db, search_request, settings)
    message = (
        "An identical pending search already exists; returning the existing job."
        if reused
        else "The LinkedIn job search was created successfully."
    )
    return ScrapingJobCreateResponse(
        scraping_job_id=scraping_job.id,
        status=scraping_job.status,
        search_url=scraping_job.search_url or "",
        message=message,
        reused_existing=reused,
    )


@scraping_jobs_router.get("", response_model=ScrapingJobListResponse)
def get_scraping_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db_session),
) -> ScrapingJobListResponse:
    """List scraping jobs with pagination, newest first."""
    jobs, total_records = list_scraping_jobs(db, page, page_size)
    return ScrapingJobListResponse(
        pagination=PaginatedResponse(
            page=page,
            page_size=page_size,
            total_records=total_records,
            total_pages=calculate_total_pages(total_records, page_size),
        ),
        items=[ScrapingJobSummary.model_validate(job) for job in jobs],
    )


@scraping_jobs_router.get("/{job_id}", response_model=ScrapingJobDetail)
def get_scraping_job_by_id(
    job_id: str,
    db: Session = Depends(get_db_session),
) -> ScrapingJobDetail:
    """Return full details for a single scraping job."""
    try:
        scraping_job = get_scraping_job(db, job_id)
    except InvalidScrapingJobIdError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ScrapingJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ScrapingJobDetail.model_validate(scraping_job)
