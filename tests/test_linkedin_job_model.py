"""Tests for Phase 4.1 LinkedInJob model columns and indexes."""

from app.models.linkedin_job import LinkedInJob
from app.models.scraping_job import ScrapingJob


def test_model_has_new_columns() -> None:
    columns = set(LinkedInJob.__table__.columns.keys())
    assert "salary_period" in columns
    assert "job_fingerprint" in columns


def test_fingerprint_index_in_metadata() -> None:
    indexed = {
        tuple(col.name for col in index.columns)
        for index in LinkedInJob.__table__.indexes
    }
    assert ("job_fingerprint",) in indexed


def test_new_columns_round_trip(db_session) -> None:
    sj = ScrapingJob(keywords="python", max_jobs=10, status="running")
    db_session.add(sj)
    db_session.commit()

    job = LinkedInJob(
        scraping_job_id=sj.id,
        title="Engineer",
        job_url="https://www.linkedin.com/jobs/view/1/",
        normalized_job_url="https://www.linkedin.com/jobs/view/1/",
        salary_period="month",
        job_fingerprint="a" * 64,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    assert job.salary_period == "month"
    assert job.job_fingerprint == "a" * 64
