"""Background execution wrapper for scraping jobs.

The API start endpoint transitions a job to ``running`` synchronously, then
schedules :func:`run_scraping_job_sync` via FastAPI ``BackgroundTasks``. This
wrapper owns its **own** database session and browser lifecycle (the request
session is closed once the HTTP response is sent) and delegates to the existing
internal execution service.

NOTE: FastAPI ``BackgroundTasks`` is an in-process convenience for this FYP MVP,
not a production-grade job queue — tasks share the web process, do not survive a
restart, and are not distributed. Production would use a real worker/queue.
"""

import asyncio
import logging
from datetime import UTC, datetime

from app.config import Settings
from app.database import SessionLocal
from app.models.enums import ScrapingJobStatus
from app.models.scraping_job import ScrapingJob
from app.services.job_processing_service import JobProcessingService
from app.services.linkedin_scraper_service import LinkedInScraperService
from app.services.scraping_job_execution_service import ScrapingJobExecutionService

logger = logging.getLogger(__name__)


def _mark_failed(job_id: str, message: str) -> None:
    """Best-effort: mark a job failed if the background run could not proceed."""
    db = SessionLocal()
    try:
        job = db.get(ScrapingJob, job_id)
        if job is not None and job.status == ScrapingJobStatus.RUNNING.value:
            job.status = ScrapingJobStatus.FAILED.value
            job.completed_at = datetime.now(UTC)
            job.error_message = (message or "Background run failed.")[:1000]
            db.commit()
    except Exception:
        logger.exception("Failed to mark job %s as failed.", job_id)
    finally:
        db.close()


async def run_scraping_job(job_id: str, settings: Settings) -> None:
    """Run a scraping job that has already been transitioned to ``running``."""
    # Import here so importing this module never launches Playwright.
    from app.services.browser_service import BrowserService

    db = SessionLocal()
    try:
        async with BrowserService(settings) as browser:
            scraper = LinkedInScraperService(browser, settings)
            service = ScrapingJobExecutionService(
                db, scraper, JobProcessingService(), settings
            )
            await service.resume(job_id)
    except Exception as exc:  # noqa: BLE001 - background task must not raise
        logger.exception("Background scraping run failed for job %s.", job_id)
        _mark_failed(job_id, str(exc))
    finally:
        db.close()


def run_scraping_job_sync(job_id: str, settings: Settings) -> None:
    """Synchronous entry point for FastAPI BackgroundTasks (runs in a thread)."""
    asyncio.run(run_scraping_job(job_id, settings))
