"""Tests for canonical job persistence and associations."""

import json

import pytest

from app.models.linkedin_job import LinkedInJob
from app.models.scraping_job import ScrapingJob
from app.models.scraping_job_result import ScrapingJobResult
from app.schemas.processed_job import ProcessedJobData
from app.services.job_persistence_service import (
    JobPersistenceError,
    upsert_linkedin_job,
)

JOB_URL = "https://www.linkedin.com/jobs/view/12345/"


def _scraping_job(db) -> ScrapingJob:
    job = ScrapingJob(keywords="python", max_jobs=10, status="running")
    db.add(job)
    db.commit()
    return job


def _processed(**kwargs) -> ProcessedJobData:
    base = {
        "title": "Python Engineer",
        "company_name": "Acme",
        "location": "Berlin",
        "job_url": JOB_URL,
        "normalized_job_url": JOB_URL,
        "linkedin_job_id": "12345",
        "required_skills": ["Python"],
        "processing_status": "complete",
    }
    base.update(kwargs)
    return ProcessedJobData(**base)


def test_new_canonical_job_created(db_session) -> None:
    sj = _scraping_job(db_session)
    job, created = upsert_linkedin_job(db_session, _processed(), sj.id, 1)
    assert created is True
    assert job.title == "Python Engineer"
    assert db_session.query(LinkedInJob).count() == 1


def test_existing_job_updated_not_duplicated(db_session) -> None:
    sj = _scraping_job(db_session)
    upsert_linkedin_job(db_session, _processed(), sj.id, 1)
    _, created = upsert_linkedin_job(
        db_session, _processed(title="Senior Python Engineer"), sj.id, 1
    )
    assert created is False
    assert db_session.query(LinkedInJob).count() == 1
    job = db_session.query(LinkedInJob).one()
    assert job.title == "Senior Python Engineer"


def test_missing_values_do_not_erase_existing(db_session) -> None:
    sj = _scraping_job(db_session)
    upsert_linkedin_job(db_session, _processed(company_name="Acme"), sj.id, 1)
    upsert_linkedin_job(db_session, _processed(company_name=None), sj.id, 1)
    job = db_session.query(LinkedInJob).one()
    assert job.company_name == "Acme"


def test_longer_description_replaces_shorter(db_session) -> None:
    sj = _scraping_job(db_session)
    upsert_linkedin_job(db_session, _processed(description="Short."), sj.id, 1)
    upsert_linkedin_job(
        db_session, _processed(description="A much longer description of the role."), sj.id, 1
    )
    job = db_session.query(LinkedInJob).one()
    assert job.description == "A much longer description of the role."

    # A shorter description does not overwrite the longer one.
    upsert_linkedin_job(db_session, _processed(description="Tiny."), sj.id, 1)
    job = db_session.query(LinkedInJob).one()
    assert job.description == "A much longer description of the role."


def test_skills_stored_as_json(db_session) -> None:
    sj = _scraping_job(db_session)
    job, _ = upsert_linkedin_job(
        db_session, _processed(required_skills=["Python", "FastAPI"]), sj.id, 1
    )
    assert json.loads(job.required_skills_json) == ["Python", "FastAPI"]


def test_scraped_at_updates(db_session) -> None:
    sj = _scraping_job(db_session)
    job, _ = upsert_linkedin_job(db_session, _processed(), sj.id, 1)
    first = job.scraped_at
    job2, _ = upsert_linkedin_job(db_session, _processed(title="Updated"), sj.id, 1)
    assert job2.scraped_at >= first


def test_association_created(db_session) -> None:
    sj = _scraping_job(db_session)
    job, _ = upsert_linkedin_job(db_session, _processed(), sj.id, 3)
    assoc = db_session.query(ScrapingJobResult).one()
    assert assoc.scraping_job_id == sj.id
    assert assoc.linkedin_job_id == job.id
    assert assoc.source_rank == 3


def test_duplicate_association_not_created(db_session) -> None:
    sj = _scraping_job(db_session)
    upsert_linkedin_job(db_session, _processed(), sj.id, 1)
    upsert_linkedin_job(db_session, _processed(), sj.id, 2)
    assert db_session.query(ScrapingJobResult).count() == 1
    assoc = db_session.query(ScrapingJobResult).one()
    assert assoc.source_rank == 2  # updated in place


def test_one_job_in_multiple_searches(db_session) -> None:
    sj1 = _scraping_job(db_session)
    sj2 = _scraping_job(db_session)
    upsert_linkedin_job(db_session, _processed(), sj1.id, 1)
    upsert_linkedin_job(db_session, _processed(), sj2.id, 1)
    assert db_session.query(LinkedInJob).count() == 1
    assert db_session.query(ScrapingJobResult).count() == 2


def test_rollback_on_database_error_keeps_session_usable(db_session) -> None:
    sj = _scraping_job(db_session)
    # A missing scraping_job_id FK triggers an IntegrityError on flush/commit.
    with pytest.raises(JobPersistenceError):
        upsert_linkedin_job(db_session, _processed(), "nonexistent-scraping-job", 1)
    # Session still works after rollback.
    job, created = upsert_linkedin_job(db_session, _processed(), sj.id, 1)
    assert created is True
    assert db_session.query(LinkedInJob).count() == 1
