"""Tests for scraping-error recording."""

from app.models.scraping_error import ScrapingError
from app.models.scraping_job import ScrapingJob
from app.services.scraping_error_service import (
    MAX_MESSAGE_LENGTH,
    record_scraping_error,
    sanitize_error_message,
)


def _scraping_job(db) -> ScrapingJob:
    job = ScrapingJob(keywords="python", max_jobs=10, status="running")
    db.add(job)
    db.commit()
    return job


def test_error_row_created(db_session) -> None:
    sj = _scraping_job(db_session)
    error = record_scraping_error(
        db_session, sj.id, "https://www.linkedin.com/jobs/view/1/", "job_not_found", "Gone"
    )
    assert error.id is not None
    assert db_session.query(ScrapingError).count() == 1


def test_message_sanitized_of_html() -> None:
    msg = "<div class='x'>Blocked</div>  page   here"
    cleaned = sanitize_error_message(msg)
    assert "<" not in cleaned and ">" not in cleaned
    assert "Blocked" in cleaned
    assert "  " not in cleaned


def test_very_long_message_truncated() -> None:
    long = "x" * (MAX_MESSAGE_LENGTH + 500)
    cleaned = sanitize_error_message(long)
    assert len(cleaned) <= MAX_MESSAGE_LENGTH


def test_html_not_stored(db_session) -> None:
    sj = _scraping_job(db_session)
    error = record_scraping_error(
        db_session, sj.id, None, "detail_parse_failed", "<html><body>secret</body></html>"
    )
    assert "<html>" not in (error.error_message or "")


def test_duplicate_identical_errors_deduplicated(db_session) -> None:
    sj = _scraping_job(db_session)
    record_scraping_error(db_session, sj.id, None, "processing_failed", "boom")
    record_scraping_error(db_session, sj.id, None, "processing_failed", "boom")
    assert db_session.query(ScrapingError).count() == 1


def test_error_commit_survives_later_job_failure(db_session) -> None:
    sj = _scraping_job(db_session)
    record_scraping_error(db_session, sj.id, None, "processing_failed", "first")
    # A later rollback must not erase the committed error.
    db_session.rollback()
    assert db_session.query(ScrapingError).count() == 1
