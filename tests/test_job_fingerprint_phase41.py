"""Phase 4.1: persisted, indexed job fingerprint and duplicate lookup."""

from app.models.linkedin_job import LinkedInJob
from app.models.scraping_job import ScrapingJob
from app.schemas.processed_job import ProcessedJobData
from app.services.duplicate_service import build_job_fingerprint, find_existing_job
from app.services.job_persistence_service import upsert_linkedin_job

JOB_URL = "https://www.linkedin.com/jobs/view/12345/"


def _sj(db) -> ScrapingJob:
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


def _canonical(db, sj_id, **kwargs) -> LinkedInJob:
    base = {
        "scraping_job_id": sj_id,
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


def test_fingerprint_deterministic() -> None:
    assert build_job_fingerprint("Engineer", "Acme", "Berlin") == build_job_fingerprint(
        " engineer ", "ACME", "berlin"
    )


def test_fingerprint_stored_on_creation(db_session) -> None:
    sj = _sj(db_session)
    job, _ = upsert_linkedin_job(db_session, _processed(), sj.id, 1)
    assert job.job_fingerprint == build_job_fingerprint("Python Engineer", "Acme", "Berlin")


def test_fingerprint_updates_on_meaningful_change(db_session) -> None:
    sj = _sj(db_session)
    job, _ = upsert_linkedin_job(db_session, _processed(), sj.id, 1)
    original = job.job_fingerprint
    job2, _ = upsert_linkedin_job(db_session, _processed(company_name="Acme Corporation"), sj.id, 1)
    assert job2.job_fingerprint != original
    assert job2.job_fingerprint == build_job_fingerprint(
        "Python Engineer", "Acme Corporation", "Berlin"
    )


def test_indexed_fingerprint_lookup_matches(db_session) -> None:
    sj = _sj(db_session)
    _canonical(
        db_session, sj.id, linkedin_job_id=None, normalized_job_url=None,
        job_fingerprint=build_job_fingerprint("Python Engineer", "Acme", "Berlin"),
    )
    match = find_existing_job(
        db_session,
        _processed(linkedin_job_id=None, normalized_job_url="https://www.linkedin.com/jobs/view/99/"),
    )
    assert match is not None


def test_different_company_not_matched(db_session) -> None:
    sj = _sj(db_session)
    _canonical(
        db_session, sj.id, linkedin_job_id=None, normalized_job_url=None,
        job_fingerprint=build_job_fingerprint("Python Engineer", "Acme", "Berlin"),
    )
    match = find_existing_job(
        db_session,
        _processed(
            linkedin_job_id=None,
            normalized_job_url="https://www.linkedin.com/jobs/view/99/",
            company_name="Globex",
        ),
    )
    assert match is None


def test_job_id_priority_over_fingerprint(db_session) -> None:
    sj = _sj(db_session)
    _canonical(
        db_session, sj.id, linkedin_job_id=None, normalized_job_url=None,
        job_fingerprint=build_job_fingerprint("Python Engineer", "Acme", "Berlin"),
    )
    row_b = _canonical(
        db_session, sj.id, linkedin_job_id="999",
        job_url="https://www.linkedin.com/jobs/view/999/",
        normalized_job_url="https://www.linkedin.com/jobs/view/999/",
        job_fingerprint=build_job_fingerprint("Different", "X", "Y"),
    )
    match = find_existing_job(
        db_session,
        _processed(linkedin_job_id="999", normalized_job_url="https://www.linkedin.com/jobs/view/999/"),
    )
    assert match is not None and match.id == row_b.id


def test_url_priority_over_fingerprint(db_session) -> None:
    sj = _sj(db_session)
    _canonical(
        db_session, sj.id, linkedin_job_id=None, normalized_job_url=None,
        job_fingerprint=build_job_fingerprint("Python Engineer", "Acme", "Berlin"),
    )
    row_b = _canonical(
        db_session, sj.id, linkedin_job_id=None,
        job_url="https://www.linkedin.com/jobs/view/777/",
        normalized_job_url="https://www.linkedin.com/jobs/view/777/",
        job_fingerprint=build_job_fingerprint("Different", "X", "Y"),
    )
    match = find_existing_job(
        db_session,
        _processed(linkedin_job_id=None, normalized_job_url="https://www.linkedin.com/jobs/view/777/"),
    )
    assert match is not None and match.id == row_b.id


def test_missing_fingerprint_does_not_crash(db_session) -> None:
    sj = _sj(db_session)
    _canonical(db_session, sj.id, linkedin_job_id=None, normalized_job_url=None, job_fingerprint=None)
    match = find_existing_job(
        db_session,
        _processed(linkedin_job_id=None, normalized_job_url="https://www.linkedin.com/jobs/view/99/"),
    )
    assert match is not None


def test_query_params_do_not_break_url_match(db_session) -> None:
    sj = _sj(db_session)
    _canonical(db_session, sj.id)
    match = find_existing_job(db_session, _processed(linkedin_job_id=None))
    assert match is not None
