"""Scraping job creation service tests."""

import uuid

import pytest

from app.models.enums import ScrapingJobStatus
from app.models.scraping_job import ScrapingJob
from app.schemas.job_search import EmploymentType, ExperienceLevel, JobSearchRequest, WorkplaceType
from app.services.scraping_job_service import (
    InvalidScrapingJobIdError,
    ScrapingJobNotFoundError,
    create_scraping_job,
    get_scraping_job,
    list_scraping_jobs,
    validate_scraping_job_id,
)


def _sample_request(**overrides) -> JobSearchRequest:
    payload = {
        "keywords": "Python Developer",
        "location": "Karachi, Pakistan",
        "experience_level": ExperienceLevel.ENTRY_LEVEL,
        "employment_type": EmploymentType.FULL_TIME,
        "workplace_type": WorkplaceType.REMOTE,
        "max_jobs": 10,
    }
    payload.update(overrides)
    return JobSearchRequest(**payload)


def test_creates_pending_job(db_session, test_settings) -> None:
    job, reused = create_scraping_job(db_session, _sample_request(), test_settings)

    assert reused is False
    assert job.status == ScrapingJobStatus.PENDING.value
    assert uuid.UUID(job.id)


def test_stores_normalized_filters(db_session, test_settings) -> None:
    request = JobSearchRequest(keywords="  Python Developer  ", location="Karachi")
    job, _ = create_scraping_job(db_session, request, test_settings)

    assert job.keywords == "Python Developer"
    assert job.location == "Karachi"
    assert job.experience_level is None
    assert job.employment_type is None


def test_initializes_counters_to_zero(db_session, test_settings) -> None:
    job, _ = create_scraping_job(db_session, _sample_request(), test_settings)

    assert job.discovered_jobs == 0
    assert job.processed_jobs == 0
    assert job.successful_jobs == 0
    assert job.duplicate_jobs == 0
    assert job.failed_jobs == 0


def test_stores_generated_url(db_session, test_settings) -> None:
    job, _ = create_scraping_job(db_session, _sample_request(), test_settings)

    assert job.search_url is not None
    assert job.search_url.startswith("https://www.linkedin.com/jobs/search/")


def test_commits_database_record(db_session, test_settings) -> None:
    job, _ = create_scraping_job(db_session, _sample_request(), test_settings)
    stored = db_session.get(ScrapingJob, job.id)
    assert stored is not None
    assert stored.keywords == "Python Developer"


def test_reuses_recent_duplicate_pending_job(db_session, test_settings) -> None:
    first, reused_first = create_scraping_job(db_session, _sample_request(), test_settings)
    second, reused_second = create_scraping_job(db_session, _sample_request(), test_settings)

    assert reused_first is False
    assert reused_second is True
    assert first.id == second.id


def test_does_not_reuse_completed_job(db_session, test_settings) -> None:
    first, _ = create_scraping_job(db_session, _sample_request(), test_settings)
    first.status = ScrapingJobStatus.COMPLETED.value
    db_session.commit()

    second, reused = create_scraping_job(db_session, _sample_request(), test_settings)
    assert reused is False
    assert first.id != second.id


def test_get_scraping_job_success(db_session, test_settings) -> None:
    created, _ = create_scraping_job(db_session, _sample_request(), test_settings)
    fetched = get_scraping_job(db_session, created.id)
    assert fetched.id == created.id


def test_get_scraping_job_not_found(db_session) -> None:
    missing_id = str(uuid.uuid4())
    with pytest.raises(ScrapingJobNotFoundError):
        get_scraping_job(db_session, missing_id)


def test_invalid_scraping_job_id(db_session) -> None:
    with pytest.raises(InvalidScrapingJobIdError):
        get_scraping_job(db_session, "not-a-uuid")


def test_validate_scraping_job_id_accepts_valid_uuid() -> None:
    job_id = str(uuid.uuid4())
    assert validate_scraping_job_id(job_id) == job_id


def test_list_scraping_jobs_pagination(db_session, test_settings) -> None:
    create_scraping_job(db_session, _sample_request(keywords="Job One"), test_settings)
    create_scraping_job(db_session, _sample_request(keywords="Job Two"), test_settings)

    jobs, total = list_scraping_jobs(db_session, page=1, page_size=1)
    assert total == 2
    assert len(jobs) == 1
