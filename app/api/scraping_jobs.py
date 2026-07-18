"""Scraping job and search API endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db_session, get_settings_dependency
from app.models.enums import ScrapingJobStatus
from app.schemas.common import PaginatedResponse
from app.schemas.job_result import JobItem, ScrapingJobResultsResponse
from app.schemas.job_search import JobSearchRequest
from app.schemas.scraping_job import (
    ScrapingJobCreateResponse,
    ScrapingJobDetail,
    ScrapingJobListResponse,
    ScrapingJobStartResponse,
    ScrapingJobSummary,
)
from app.services import export_service
from app.services.jobs_query_service import (
    all_results_for_scraping_job,
    query_results_for_scraping_job,
)
from app.services.scraping_job_execution_service import (
    ScrapingJobExecutionConflictError,
    mark_scraping_job_running,
)
from app.services.scraping_job_runner import run_scraping_job_sync
from app.services.scraping_job_service import (
    InvalidScrapingJobIdError,
    ScrapingJobNotFoundError,
    calculate_total_pages,
    create_scraping_job,
    get_scraping_job,
    list_scraping_jobs,
)
from app.utils.export_response import csv_response, json_download_response

search_router = APIRouter(tags=["search"])
scraping_jobs_router = APIRouter(prefix="/scraping-jobs", tags=["scraping-jobs"])


def _load_job_or_http(db: Session, job_id: str):
    """Fetch a scraping job, translating domain errors to HTTP errors."""
    try:
        return get_scraping_job(db, job_id)
    except InvalidScrapingJobIdError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ScrapingJobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


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
    scraping_job = _load_job_or_http(db, job_id)
    return ScrapingJobDetail.model_validate(scraping_job)


@scraping_jobs_router.post(
    "/{job_id}/start",
    response_model=ScrapingJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_scraping_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings_dependency),
) -> ScrapingJobStartResponse:
    """Start a pending scraping job in the background and return immediately.

    Only pending jobs can start; the job is transitioned to ``running``
    synchronously (preventing duplicate starts) before the actual scraping is
    scheduled via BackgroundTasks, so the request never blocks until completion.
    """
    scraping_job = _load_job_or_http(db, job_id)
    try:
        mark_scraping_job_running(db, scraping_job)
    except ScrapingJobExecutionConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    background_tasks.add_task(run_scraping_job_sync, scraping_job.id, settings)

    return ScrapingJobStartResponse(
        scraping_job_id=scraping_job.id,
        status=ScrapingJobStatus.RUNNING.value,
        message="Scraping job started; processing runs in the background.",
    )


@scraping_jobs_router.get(
    "/{job_id}/results",
    response_model=ScrapingJobResultsResponse,
)
def get_scraping_job_results(
    job_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db_session),
) -> ScrapingJobResultsResponse:
    """Return the canonical jobs discovered by a scraping job (paginated)."""
    scraping_job = _load_job_or_http(db, job_id)
    jobs, total = query_results_for_scraping_job(db, scraping_job.id, page, page_size)
    return ScrapingJobResultsResponse(
        scraping_job_id=scraping_job.id,
        pagination=PaginatedResponse(
            page=page,
            page_size=page_size,
            total_records=total,
            total_pages=calculate_total_pages(total, page_size),
        ),
        items=[JobItem.from_orm_job(job) for job in jobs],
    )


@scraping_jobs_router.get("/{job_id}/export/csv")
def export_scraping_job_csv(
    job_id: str,
    db: Session = Depends(get_db_session),
) -> Response:
    """Export a single scraping job's discovered jobs as CSV."""
    scraping_job = _load_job_or_http(db, job_id)
    jobs = all_results_for_scraping_job(db, scraping_job.id)
    items = [JobItem.from_orm_job(job) for job in jobs]
    content = export_service.jobs_to_csv(items)
    filename = export_service.safe_filename(f"scraping_job_{scraping_job.id}_jobs", "csv")
    return csv_response(content, filename)


@scraping_jobs_router.get("/{job_id}/export/json")
def export_scraping_job_json(
    job_id: str,
    db: Session = Depends(get_db_session),
) -> Response:
    """Export a single scraping job's discovered jobs as JSON."""
    scraping_job = _load_job_or_http(db, job_id)
    jobs = all_results_for_scraping_job(db, scraping_job.id)
    items = [JobItem.from_orm_job(job) for job in jobs]
    payload = export_service.jobs_to_json(
        items,
        metadata={
            "scraping_job_id": scraping_job.id,
            "keywords": scraping_job.keywords,
            "location": scraping_job.location,
            "status": scraping_job.status,
        },
    )
    filename = export_service.safe_filename(f"scraping_job_{scraping_job.id}_jobs", "json")
    return json_download_response(payload, filename)
