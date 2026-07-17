"""Per-job scraping error recording.

Stores stable error types with short, sanitized messages. Never stores HTML,
cookies, tokens, credentials, or CAPTCHA content. Messages are stripped of
markup and truncated. Each error is committed in its own unit of work so a later
failure cannot erase earlier error records, and identical errors are not
duplicated.
"""

import re

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.scraping_error import ScrapingError

MAX_MESSAGE_LENGTH = 1000

_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")

# Known stable error types (documentation / reference).
ERROR_TYPES = (
    "navigation_timeout",
    "access_restricted",
    "captcha_detected",
    "authentication_required",
    "job_not_found",
    "invalid_job_url",
    "detail_parse_failed",
    "processing_failed",
    "database_error",
    "unexpected_error",
)


def sanitize_error_message(message: str | None) -> str:
    """Strip markup, collapse whitespace, and truncate an error message."""
    if not message:
        return ""
    stripped = _TAG_PATTERN.sub(" ", message)
    collapsed = _WHITESPACE_PATTERN.sub(" ", stripped).strip()
    if len(collapsed) > MAX_MESSAGE_LENGTH:
        collapsed = collapsed[: MAX_MESSAGE_LENGTH - 1].rstrip() + "…"
    return collapsed


def record_scraping_error(
    db: Session,
    scraping_job_id: str,
    job_url: str | None,
    error_type: str,
    error_message: str,
) -> ScrapingError:
    """Record (or reuse) a sanitized scraping error, committed independently."""
    safe_message = sanitize_error_message(error_message)

    try:
        existing = db.execute(
            select(ScrapingError).where(
                ScrapingError.scraping_job_id == scraping_job_id,
                ScrapingError.job_url == job_url,
                ScrapingError.error_type == error_type,
                ScrapingError.error_message == safe_message,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        error = ScrapingError(
            scraping_job_id=scraping_job_id,
            job_url=job_url,
            error_type=error_type,
            error_message=safe_message,
        )
        db.add(error)
        db.commit()
        db.refresh(error)
        return error
    except SQLAlchemyError:
        db.rollback()
        raise
