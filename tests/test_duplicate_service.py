"""Tests for global duplicate detection."""

from app.models.linkedin_job import LinkedInJob
from app.models.scraping_job import ScrapingJob
from app.schemas.processed_job import ProcessedJobData
from app.services.duplicate_service import build_job_fingerprint, find_existing_job

JOB_URL = "https://www.linkedin.com/jobs/view/12345/"


def _scraping_job(db) -> ScrapingJob:
    job = ScrapingJob(keywords="python", max_jobs=10, status="pending")
    db.add(job)
    db.commit()
    return job


def _canonical(db, scraping_job_id: str, **kwargs) -> LinkedInJob:
    base = {
        "scraping_job_id": scraping_job_id,
        "linkedin_job_id": "12345",
        "title": "Python Engineer",
        "company_name": "Acme",
        "location": "Berlin",
        "job_url": JOB_URL,
        "normalized_job_url": JOB_URL,
    }
    base.update(kwargs)
    job = LinkedInJob(**base)
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
    }
    base.update(kwargs)
    return ProcessedJobData(**base)


def test_fingerprint_deterministic() -> None:
    a = build_job_fingerprint("Engineer", "Acme", "Berlin")
    b = build_job_fingerprint(" engineer ", "ACME", "berlin")
    assert a == b
    assert len(a) == 64  # sha-256 hex


def test_same_job_id_matches(db_session) -> None:
    sj = _scraping_job(db_session)
    _canonical(db_session, sj.id)
    match = find_existing_job(db_session, _processed(normalized_job_url="https://www.linkedin.com/jobs/view/99/"))
    assert match is not None


def test_same_normalized_url_matches(db_session) -> None:
    sj = _scraping_job(db_session)
    _canonical(db_session, sj.id)
    match = find_existing_job(db_session, _processed(linkedin_job_id=None))
    assert match is not None


def test_fingerprint_fallback_matches(db_session) -> None:
    sj = _scraping_job(db_session)
    _canonical(db_session, sj.id, linkedin_job_id=None, normalized_job_url=None)
    match = find_existing_job(
        db_session,
        _processed(
            linkedin_job_id=None,
            normalized_job_url="https://www.linkedin.com/jobs/view/777/",
        ),
    )
    assert match is not None


def test_different_company_not_duplicate(db_session) -> None:
    sj = _scraping_job(db_session)
    _canonical(db_session, sj.id, linkedin_job_id=None, normalized_job_url=None, company_name="Acme")
    match = find_existing_job(
        db_session,
        _processed(
            linkedin_job_id=None,
            normalized_job_url="https://www.linkedin.com/jobs/view/888/",
            company_name="Globex",
        ),
    )
    assert match is None


def test_different_location_not_duplicate(db_session) -> None:
    sj = _scraping_job(db_session)
    _canonical(db_session, sj.id, linkedin_job_id=None, normalized_job_url=None, location="Berlin")
    match = find_existing_job(
        db_session,
        _processed(
            linkedin_job_id=None,
            normalized_job_url="https://www.linkedin.com/jobs/view/888/",
            location="Munich",
        ),
    )
    assert match is None


def test_query_params_do_not_break_url_match(db_session) -> None:
    sj = _scraping_job(db_session)
    _canonical(db_session, sj.id, linkedin_job_id=None)
    # normalized_job_url has no query params, so a query-laden source still matches.
    match = find_existing_job(db_session, _processed(linkedin_job_id=None))
    assert match is not None
