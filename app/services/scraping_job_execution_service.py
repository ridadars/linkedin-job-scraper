"""Internal orchestration of a full scraping run.

Loads a pending ``ScrapingJob``, drives the (mocked-in-tests) scraper service to
collect search results and job details, processes and persists each job, records
per-job errors, and maintains progress counters and final status.

This is an *internal* service — Phase 4 deliberately exposes no ``/start`` or
``/cancel`` HTTP endpoint. Individual job failures never stop the run;
search-level blocking conditions (CAPTCHA, sign-in wall, access restriction)
stop it safely. No concurrency is used; jobs are processed one at a time.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import Settings
from app.exceptions import (
    AccessRestrictedError,
    AuthenticationRequiredError,
    CaptchaDetectedError,
    InvalidLinkedInUrlError,
    JobPageNotFoundError,
    LinkedInScraperError,
    NavigationError,
    NavigationTimeoutError,
    ParsingError,
)
from app.models.enums import ScrapingJobStatus
from app.models.scraping_job import ScrapingJob
from app.schemas.processed_job import ProcessingStatus
from app.services.job_persistence_service import (
    JobPersistenceError,
    upsert_linkedin_job,
)
from app.services.job_processing_service import JobProcessingService
from app.services.linkedin_scraper_service import LinkedInScraperService
from app.services.scraping_error_service import record_scraping_error

logger = logging.getLogger(__name__)

# Blocking errors that stop the entire run immediately.
_BLOCKING_ERRORS = (
    CaptchaDetectedError,
    AuthenticationRequiredError,
    AccessRestrictedError,
)


class ScrapingJobExecutionConflictError(LinkedInScraperError):
    """Raised when a scraping job is not in a startable state."""

    code = "scraping_job_conflict"


def mark_scraping_job_running(db: Session, job: ScrapingJob) -> ScrapingJob:
    """Atomically transition a pending job to running (guarded), and commit.

    Used by the API start endpoint to prevent duplicate starts and report a
    running status immediately, before the actual work is scheduled in the
    background. Raises :class:`ScrapingJobExecutionConflictError` if the job is
    not pending.
    """
    status = job.status
    if status == ScrapingJobStatus.RUNNING.value:
        raise ScrapingJobExecutionConflictError("Scraping job is already running.")
    if status != ScrapingJobStatus.PENDING.value:
        raise ScrapingJobExecutionConflictError(
            f"Scraping job cannot start from status '{status}'."
        )
    job.status = ScrapingJobStatus.RUNNING.value
    job.started_at = datetime.now(UTC)
    job.discovered_jobs = 0
    job.processed_jobs = 0
    job.successful_jobs = 0
    job.duplicate_jobs = 0
    job.failed_jobs = 0
    job.completed_at = None
    job.error_message = None
    db.commit()
    db.refresh(job)
    return job


def _search_error_type(exc: Exception) -> str:
    """Map an exception to a stable error type for search-level failures."""
    if isinstance(exc, CaptchaDetectedError):
        return "captcha_detected"
    if isinstance(exc, AuthenticationRequiredError):
        return "authentication_required"
    if isinstance(exc, AccessRestrictedError):
        return "access_restricted"
    if isinstance(exc, NavigationTimeoutError):
        return "navigation_timeout"
    if isinstance(exc, InvalidLinkedInUrlError):
        return "invalid_job_url"
    return "unexpected_error"


def _detail_error_type(exc: Exception) -> str:
    """Map an exception to a stable error type for detail-level failures."""
    if isinstance(exc, JobPageNotFoundError):
        return "job_not_found"
    if isinstance(exc, NavigationTimeoutError):
        return "navigation_timeout"
    if isinstance(exc, InvalidLinkedInUrlError):
        return "invalid_job_url"
    if isinstance(exc, ParsingError):
        return "detail_parse_failed"
    if isinstance(exc, NavigationError):
        return "navigation_timeout"
    return "detail_parse_failed"


class ScrapingJobExecutionService:
    """Coordinates a single scraping run end to end."""

    def __init__(
        self,
        db: Session,
        scraper_service: LinkedInScraperService,
        processing_service: JobProcessingService,
        settings: Settings,
    ) -> None:
        self._db = db
        self._scraper = scraper_service
        self._processing = processing_service
        self._settings = settings

    async def execute(
        self,
        scraping_job_id: str,
        reference_time: datetime | None = None,
    ) -> ScrapingJob:
        """Execute the scraping job and return the updated record.

        Guards that the job is pending, marks it running, then runs it. Used by
        internal callers and tests. The API path instead marks the job running
        synchronously and calls :meth:`resume`.
        """
        job = self._db.get(ScrapingJob, scraping_job_id)
        if job is None:
            raise ScrapingJobExecutionConflictError(
                f"Scraping job '{scraping_job_id}' was not found."
            )
        self._guard_startable(job)
        self._begin(job)
        return await self._run(job, reference_time)

    async def resume(
        self,
        scraping_job_id: str,
        reference_time: datetime | None = None,
    ) -> ScrapingJob:
        """Run a job that a caller has already transitioned to ``running``.

        Used by the API start endpoint, which marks the job running
        synchronously (to prevent duplicate starts and report status
        immediately) and then schedules the actual work in the background.
        """
        job = self._db.get(ScrapingJob, scraping_job_id)
        if job is None:
            raise ScrapingJobExecutionConflictError(
                f"Scraping job '{scraping_job_id}' was not found."
            )
        if job.status != ScrapingJobStatus.RUNNING.value:
            raise ScrapingJobExecutionConflictError(
                f"Scraping job must be running to resume; got '{job.status}'."
            )
        return await self._run(job, reference_time)

    async def _run(
        self,
        job: ScrapingJob,
        reference_time: datetime | None = None,
    ) -> ScrapingJob:
        """Collect, process, persist, and finalize a running job."""
        # --- Search-level collection ------------------------------------
        try:
            search_result = await self._scraper.collect_search_results(
                job.search_url or "",
                job.max_jobs,
            )
        except Exception as exc:  # search failure is fatal for the run
            self._record_error(job.id, job.search_url, _search_error_type(exc), exc)
            return self._finalize(job, ScrapingJobStatus.FAILED)

        job.discovered_jobs = len(search_result.jobs)
        self._db.commit()

        if job.discovered_jobs == 0:
            return self._finalize(job, ScrapingJobStatus.COMPLETED)

        # --- Per-job processing -----------------------------------------
        fatal_block = False
        for index, card in enumerate(search_result.jobs, start=1):
            if self._is_cancelled(job):
                logger.info("Scraping job %s cancelled; stopping safely.", job.id)
                return self._finalize(job, ScrapingJobStatus.CANCELLED)

            detail = None
            detail_fetched = False
            try:
                detail = await self._scraper.collect_job_detail(card.job_url or "")
                detail_fetched = True
            except _BLOCKING_ERRORS as exc:
                self._record_error(job.id, card.job_url, _search_error_type(exc), exc)
                fatal_block = True
                break
            except Exception as exc:  # recoverable: fall back to card-only
                self._record_error(job.id, card.job_url, _detail_error_type(exc), exc)

            self._process_and_persist(job, card, detail, index, detail_fetched, reference_time)

        # --- Final status -----------------------------------------------
        if fatal_block:
            final = (
                ScrapingJobStatus.PARTIALLY_COMPLETED
                if job.successful_jobs > 0
                else ScrapingJobStatus.FAILED
            )
        elif job.failed_jobs and job.successful_jobs:
            final = ScrapingJobStatus.PARTIALLY_COMPLETED
        elif job.failed_jobs and not job.successful_jobs:
            final = ScrapingJobStatus.FAILED
        else:
            final = ScrapingJobStatus.COMPLETED

        return self._finalize(job, final)

    # ------------------------------------------------------------------

    def _guard_startable(self, job: ScrapingJob) -> None:
        """Only a pending job may be started."""
        status = job.status
        if status == ScrapingJobStatus.RUNNING.value:
            raise ScrapingJobExecutionConflictError(
                "Scraping job is already running."
            )
        if status != ScrapingJobStatus.PENDING.value:
            raise ScrapingJobExecutionConflictError(
                f"Scraping job cannot start from status '{status}'."
            )

    def _begin(self, job: ScrapingJob) -> None:
        """Mark the job running and reset counters."""
        job.status = ScrapingJobStatus.RUNNING.value
        job.started_at = datetime.now(UTC)
        job.discovered_jobs = 0
        job.processed_jobs = 0
        job.successful_jobs = 0
        job.duplicate_jobs = 0
        job.failed_jobs = 0
        job.error_message = None
        self._db.commit()

    def _is_cancelled(self, job: ScrapingJob) -> bool:
        """Re-read status from the database to honor external cancellation."""
        self._db.refresh(job)
        return job.status == ScrapingJobStatus.CANCELLED.value

    def _process_and_persist(
        self,
        job: ScrapingJob,
        card,
        detail,
        source_rank: int,
        detail_fetched: bool,
        reference_time: datetime | None,
    ) -> None:
        """Process one card, persist it, and update counters (isolated)."""
        result = self._processing.process(card, detail, reference_time)
        job.processed_jobs += 1

        if result.status == ProcessingStatus.FAILED.value or result.job is None:
            job.failed_jobs += 1
            self._record_error(
                job.id,
                card.job_url,
                result.error_type or "processing_failed",
                result.error_message or "Processing failed.",
            )
            self._db.commit()
            return

        try:
            _, created = upsert_linkedin_job(
                self._db,
                result.job,
                job.id,
                source_rank,
                detail_fetched=detail_fetched,
            )
        except JobPersistenceError as exc:
            job.failed_jobs += 1
            self._record_error(job.id, card.job_url, "database_error", exc)
            self._db.commit()
            return

        if not created:
            job.duplicate_jobs += 1
        job.successful_jobs += 1
        self._db.commit()

    def _record_error(
        self,
        scraping_job_id: str,
        job_url: str | None,
        error_type: str,
        error,
    ) -> None:
        """Record a sanitized error, tolerating error-recording failure."""
        message = str(error) if error is not None else ""
        try:
            record_scraping_error(
                self._db,
                scraping_job_id,
                job_url,
                error_type,
                message,
            )
        except Exception:  # never let error-recording break the run
            logger.warning("Failed to record scraping error of type %s.", error_type)

    def _finalize(self, job: ScrapingJob, status: ScrapingJobStatus) -> ScrapingJob:
        """Set the final status and completion timestamp, then commit."""
        job.status = status.value
        job.completed_at = datetime.now(UTC)
        self._db.commit()
        self._db.refresh(job)
        logger.info(
            "Scraping job %s finished: status=%s discovered=%d processed=%d "
            "successful=%d duplicate=%d failed=%d.",
            job.id,
            job.status,
            job.discovered_jobs,
            job.processed_jobs,
            job.successful_jobs,
            job.duplicate_jobs,
            job.failed_jobs,
        )
        return job
