"""Tests for the internal scraping-job execution service.

The scraper service is mocked; no Playwright, network, or external API is used.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.exceptions import (
    AccessRestrictedError,
    AuthenticationRequiredError,
    CaptchaDetectedError,
    NavigationError,
)
from app.models.enums import ScrapingJobStatus
from app.models.linkedin_job import LinkedInJob
from app.models.scraping_error import ScrapingError
from app.models.scraping_job import ScrapingJob
from app.models.scraping_job_result import ScrapingJobResult
from app.schemas.parsed_job import JobCardData, JobDetailData, SearchPageResult
from app.services import scraping_job_execution_service as execution_module
from app.services.job_persistence_service import JobPersistenceError
from app.services.job_processing_service import JobProcessingService
from app.services.scraping_job_execution_service import (
    ScrapingJobExecutionConflictError,
    ScrapingJobExecutionService,
)

REFERENCE = datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC)
SEARCH_URL = "https://www.linkedin.com/jobs/search/"


def _settings() -> Settings:
    return Settings(DATABASE_URL="sqlite://", MAX_RETRIES=0)


def _pending_job(db, **kwargs) -> ScrapingJob:
    base = {
        "keywords": "python",
        "search_url": SEARCH_URL,
        "max_jobs": 10,
        "status": ScrapingJobStatus.PENDING.value,
    }
    base.update(kwargs)
    job = ScrapingJob(**base)
    db.add(job)
    db.commit()
    return job


def _card(job_id: str, title: str = "Python Engineer", **kwargs) -> JobCardData:
    base = {
        "linkedin_job_id": job_id,
        "title": title,
        "company_name": "Acme",
        "location": "Berlin",
        "job_url": f"https://www.linkedin.com/jobs/view/{job_id}/",
    }
    base.update(kwargs)
    return JobCardData(**base)


def _detail(job_id: str, **kwargs) -> JobDetailData:
    base = {
        "linkedin_job_id": job_id,
        "title": f"Senior Python Engineer {job_id}",
        "job_url": f"https://www.linkedin.com/jobs/view/{job_id}/",
        "workplace_type": "Remote",
        "employment_type": "Full-time",
        "experience_level": "Mid-Senior level",
        "job_description": "We use Python and Machine Learning.",
        "posted_text": "2 days ago",
    }
    base.update(kwargs)
    return JobDetailData(**base)


def _scraper(cards: list[JobCardData], detail_map: dict) -> AsyncMock:
    scraper = AsyncMock()
    scraper.collect_search_results = AsyncMock(
        return_value=SearchPageResult(jobs=cards, discovered_count=len(cards))
    )

    async def detail_side_effect(url: str):
        entry = detail_map.get(url)
        if isinstance(entry, Exception):
            raise entry
        if entry is None:
            raise NavigationError("no detail")
        return entry

    scraper.collect_job_detail = AsyncMock(side_effect=detail_side_effect)
    return scraper


def _service(db, scraper) -> ScrapingJobExecutionService:
    return ScrapingJobExecutionService(db, scraper, JobProcessingService(), _settings())


async def _run(db, scraper, job_id):
    return await _service(db, scraper).execute(job_id, reference_time=REFERENCE)


# --- Successful run ----------------------------------------------------------


async def test_successful_run(db_session) -> None:
    job = _pending_job(db_session)
    cards = [_card("111"), _card("222", title="Data Scientist")]
    detail_map = {
        cards[0].job_url: _detail("111"),
        cards[1].job_url: _detail("222"),
    }
    result = await _run(db_session, _scraper(cards, detail_map), job.id)

    assert result.status == ScrapingJobStatus.COMPLETED.value
    assert result.discovered_jobs == 2
    assert result.processed_jobs == 2
    assert result.successful_jobs == 2
    assert result.failed_jobs == 0
    assert result.started_at is not None
    assert result.completed_at is not None
    assert db_session.query(LinkedInJob).count() == 2
    assert db_session.query(ScrapingJobResult).count() == 2


# --- Empty search ------------------------------------------------------------


async def test_empty_search(db_session) -> None:
    job = _pending_job(db_session)
    result = await _run(db_session, _scraper([], {}), job.id)
    assert result.status == ScrapingJobStatus.COMPLETED.value
    assert result.discovered_jobs == 0
    assert result.processed_jobs == 0
    assert db_session.query(LinkedInJob).count() == 0


# --- Partial run -------------------------------------------------------------


async def test_partial_run(db_session) -> None:
    job = _pending_job(db_session)
    good = _card("111")
    bad = _card("222", title="Bad", job_url="https://www.linkedin.com/feed/")
    detail_map = {good.job_url: _detail("111")}  # bad url -> NavigationError
    result = await _run(db_session, _scraper([good, bad], detail_map), job.id)

    assert result.status == ScrapingJobStatus.PARTIALLY_COMPLETED.value
    assert result.successful_jobs == 1
    assert result.failed_jobs == 1
    assert result.processed_jobs == 2
    assert db_session.query(ScrapingError).count() >= 1


# --- Card-level fallback -----------------------------------------------------


async def test_card_level_fallback(db_session) -> None:
    job = _pending_job(db_session)
    card = _card("111")
    # Detail fetch fails for a recoverable reason; card has enough info.
    detail_map = {card.job_url: NavigationError("timeout-ish")}
    result = await _run(db_session, _scraper([card], detail_map), job.id)

    assert result.status == ScrapingJobStatus.COMPLETED.value
    assert result.successful_jobs == 1
    assert result.failed_jobs == 0
    assert db_session.query(LinkedInJob).count() == 1
    # A detail error was still recorded.
    assert db_session.query(ScrapingError).count() == 1
    assoc = db_session.query(ScrapingJobResult).one()
    assert assoc.detail_fetched is False


# --- Fatal search failure ----------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [CaptchaDetectedError(), AuthenticationRequiredError(), AccessRestrictedError()],
)
async def test_fatal_search_failure(db_session, error) -> None:
    job = _pending_job(db_session)
    scraper = AsyncMock()
    scraper.collect_search_results = AsyncMock(side_effect=error)
    result = await _service(db_session, scraper).execute(job.id, reference_time=REFERENCE)

    assert result.status == ScrapingJobStatus.FAILED.value
    assert db_session.query(LinkedInJob).count() == 0
    assert db_session.query(ScrapingError).count() == 1


# --- Duplicate run data ------------------------------------------------------


async def test_duplicate_run_reuses_canonical(db_session) -> None:
    # Pre-existing canonical job discovered by an earlier search.
    first = _pending_job(db_session)
    card = _card("111")
    await _run(db_session, _scraper([card], {card.job_url: _detail("111")}), first.id)
    assert db_session.query(LinkedInJob).count() == 1

    # A new search finds the same job.
    second = _pending_job(db_session)
    result = await _run(
        db_session, _scraper([card], {card.job_url: _detail("111")}), second.id
    )
    assert db_session.query(LinkedInJob).count() == 1  # not duplicated
    assert result.duplicate_jobs == 1
    assert result.successful_jobs == 1
    assert result.failed_jobs == 0
    assert db_session.query(ScrapingJobResult).count() == 2  # one per search


# --- Status safety -----------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [
        ScrapingJobStatus.COMPLETED.value,
        ScrapingJobStatus.RUNNING.value,
        ScrapingJobStatus.CANCELLED.value,
        ScrapingJobStatus.FAILED.value,
    ],
)
async def test_non_pending_job_cannot_start(db_session, status) -> None:
    job = _pending_job(db_session, status=status)
    with pytest.raises(ScrapingJobExecutionConflictError):
        await _run(db_session, _scraper([], {}), job.id)


async def test_cancellation_during_processing_stops_safely(db_session) -> None:
    job = _pending_job(db_session)
    cards = [_card("111"), _card("222", title="Data Scientist")]

    scraper = AsyncMock()
    scraper.collect_search_results = AsyncMock(
        return_value=SearchPageResult(jobs=cards, discovered_count=2)
    )

    async def detail_side_effect(url: str):
        if url == cards[0].job_url:
            # Simulate an external cancellation after the first detail fetch.
            job.status = ScrapingJobStatus.CANCELLED.value
            db_session.commit()
            return _detail("111")
        return _detail("222")

    scraper.collect_job_detail = AsyncMock(side_effect=detail_side_effect)

    result = await _service(db_session, scraper).execute(job.id, reference_time=REFERENCE)

    assert result.status == ScrapingJobStatus.CANCELLED.value
    assert result.completed_at is not None
    # The first job was preserved; the second was not processed or failed.
    assert result.successful_jobs == 1
    assert result.failed_jobs == 0
    assert db_session.query(LinkedInJob).count() == 1


# --- Transaction safety ------------------------------------------------------


async def test_persistence_failure_does_not_lose_earlier_jobs(
    db_session, monkeypatch
) -> None:
    job = _pending_job(db_session)
    cards = [_card("111"), _card("222", title="Data Scientist")]
    detail_map = {cards[0].job_url: _detail("111"), cards[1].job_url: _detail("222")}

    real_upsert = execution_module.upsert_linkedin_job
    calls = {"n": 0}

    def flaky_upsert(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise JobPersistenceError("simulated database error")
        return real_upsert(*args, **kwargs)

    monkeypatch.setattr(execution_module, "upsert_linkedin_job", flaky_upsert)

    result = await _run(db_session, _scraper(cards, detail_map), job.id)

    # First job persisted; second failed but did not corrupt the run.
    assert db_session.query(LinkedInJob).count() == 1
    assert result.successful_jobs == 1
    assert result.failed_jobs == 1
    assert result.processed_jobs == 2
    # Counters remain consistent.
    assert result.successful_jobs + result.failed_jobs == result.processed_jobs
    # Session still usable.
    assert db_session.query(ScrapingJob).count() == 1
