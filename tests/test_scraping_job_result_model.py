"""Tests for the ScrapingJobResult association model."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.linkedin_job import LinkedInJob
from app.models.scraping_job import ScrapingJob
from app.models.scraping_job_result import ScrapingJobResult

JOB_URL = "https://www.linkedin.com/jobs/view/12345/"


def _scraping_job(db, keywords="python") -> ScrapingJob:
    job = ScrapingJob(keywords=keywords, max_jobs=10, status="running")
    db.add(job)
    db.commit()
    return job


def _canonical(db, scraping_job_id: str, **kwargs) -> LinkedInJob:
    base = {
        "scraping_job_id": scraping_job_id,
        "title": "Engineer",
        "job_url": JOB_URL,
        "normalized_job_url": JOB_URL,
    }
    base.update(kwargs)
    job = LinkedInJob(**base)
    db.add(job)
    db.commit()
    return job


def test_association_created_with_relationships(db_session) -> None:
    sj = _scraping_job(db_session)
    lj = _canonical(db_session, sj.id)
    assoc = ScrapingJobResult(scraping_job_id=sj.id, linkedin_job_id=lj.id, source_rank=1)
    db_session.add(assoc)
    db_session.commit()

    assert assoc.scraping_job.id == sj.id
    assert assoc.linkedin_job.id == lj.id
    assert sj.results[0].id == assoc.id
    assert lj.search_results[0].id == assoc.id


def test_unique_search_job_pair(db_session) -> None:
    sj = _scraping_job(db_session)
    lj = _canonical(db_session, sj.id)
    db_session.add(ScrapingJobResult(scraping_job_id=sj.id, linkedin_job_id=lj.id))
    db_session.commit()
    db_session.add(ScrapingJobResult(scraping_job_id=sj.id, linkedin_job_id=lj.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_canonical_job_in_multiple_searches(db_session) -> None:
    sj1 = _scraping_job(db_session, "a")
    sj2 = _scraping_job(db_session, "b")
    lj = _canonical(db_session, sj1.id)
    db_session.add(ScrapingJobResult(scraping_job_id=sj1.id, linkedin_job_id=lj.id))
    db_session.add(ScrapingJobResult(scraping_job_id=sj2.id, linkedin_job_id=lj.id))
    db_session.commit()
    assert len(lj.search_results) == 2


def test_search_contains_multiple_jobs(db_session) -> None:
    sj = _scraping_job(db_session)
    lj1 = _canonical(db_session, sj.id, job_url="https://www.linkedin.com/jobs/view/1/", normalized_job_url="https://www.linkedin.com/jobs/view/1/")
    lj2 = _canonical(db_session, sj.id, job_url="https://www.linkedin.com/jobs/view/2/", normalized_job_url="https://www.linkedin.com/jobs/view/2/")
    db_session.add(ScrapingJobResult(scraping_job_id=sj.id, linkedin_job_id=lj1.id))
    db_session.add(ScrapingJobResult(scraping_job_id=sj.id, linkedin_job_id=lj2.id))
    db_session.commit()
    assert len(sj.results) == 2


def test_cascade_delete_from_scraping_job(db_session) -> None:
    sj = _scraping_job(db_session)
    lj = _canonical(db_session, sj.id)
    db_session.add(ScrapingJobResult(scraping_job_id=sj.id, linkedin_job_id=lj.id))
    db_session.commit()

    db_session.delete(sj)
    db_session.commit()
    assert db_session.query(ScrapingJobResult).count() == 0
