"""Canonical job persistence and search-association upserts.

``upsert_linkedin_job`` finds an existing canonical job (via
:mod:`app.services.duplicate_service`) and either inserts a new record or
updates the existing one with better/newer information, then records the
``ScrapingJobResult`` association linking the discovering search to the job.

Update rules:

* Non-empty values replace missing/empty existing values.
* A longer non-empty description replaces a shorter one.
* A non-empty skills list replaces the stored list.
* Existing values are never erased by missing (``None``) data.
* Canonical ``linkedin_job_id`` and ``normalized_job_url`` stay stable once set.
* ``scraped_at`` always advances to the latest scrape time.

Each call commits in its own unit of work and rolls back on database errors, so
one failed job never corrupts an in-progress run.
"""

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import LinkedInScraperError
from app.models.linkedin_job import LinkedInJob
from app.models.scraping_job_result import ScrapingJobResult
from app.schemas.processed_job import ProcessedJobData
from app.services.duplicate_service import build_job_fingerprint, find_existing_job


class JobPersistenceError(LinkedInScraperError):
    """Raised when a job could not be persisted."""

    code = "database_error"


def _skills_json(skills: list[str]) -> str:
    return json.dumps(skills, ensure_ascii=False)


def _set_if_better(job: LinkedInJob, field: str, value) -> None:
    """Set a scalar field only when the new value is non-empty."""
    if value is None or value == "":
        return
    setattr(job, field, value)


def _apply_updates(job: LinkedInJob, processed: ProcessedJobData) -> None:
    """Update an existing canonical job with better/newer, non-erasing data."""
    # Stable identifiers: set only if currently empty.
    if not job.linkedin_job_id and processed.linkedin_job_id:
        job.linkedin_job_id = processed.linkedin_job_id
    if not job.normalized_job_url and processed.normalized_job_url:
        job.normalized_job_url = processed.normalized_job_url

    for field in (
        "title",
        "company_name",
        "company_url",
        "location",
        "country",
        "workplace_type",
        "employment_type",
        "experience_level",
        "salary_min",
        "salary_max",
        "salary_currency",
        "salary_period",
        "salary_text",
        "applicant_count",
        "easy_apply",
        "posted_date",
        "relative_posted_time",
        "recruiter_name",
        "recruiter_profile_url",
    ):
        _set_if_better(job, field, getattr(processed, field))

    # Description: replace only with a longer non-empty description.
    new_description = processed.description
    if new_description and (
        not job.description or len(new_description) > len(job.description)
    ):
        job.description = new_description

    # Skills: replace with any non-empty skill list.
    if processed.required_skills:
        job.required_skills_json = _skills_json(processed.required_skills)

    # Recompute the fingerprint from the (possibly updated) identity fields.
    # This keeps it in sync after meaningful title/company/location changes and
    # backfills legacy rows. A valid title always yields a valid fingerprint, so
    # a missing update never erases an existing one.
    if job.title:
        job.job_fingerprint = build_job_fingerprint(
            job.title, job.company_name, job.location
        )

    # Status and freshness.
    if processed.processing_status:
        job.status = processed.processing_status
    job.scraped_at = datetime.now(UTC)


def _build_new_job(
    processed: ProcessedJobData,
    scraping_job_id: str,
) -> LinkedInJob:
    """Construct a new canonical LinkedInJob from processed data."""
    return LinkedInJob(
        linkedin_job_id=processed.linkedin_job_id,
        scraping_job_id=scraping_job_id,
        title=processed.title,
        company_name=processed.company_name,
        company_url=processed.company_url,
        job_url=processed.job_url,
        normalized_job_url=processed.normalized_job_url,
        location=processed.location,
        country=processed.country,
        workplace_type=processed.workplace_type,
        employment_type=processed.employment_type,
        experience_level=processed.experience_level,
        job_fingerprint=build_job_fingerprint(
            processed.title, processed.company_name, processed.location
        ),
        salary_min=processed.salary_min,
        salary_max=processed.salary_max,
        salary_currency=processed.salary_currency,
        salary_period=processed.salary_period,
        salary_text=processed.salary_text,
        description=processed.description,
        required_skills_json=_skills_json(processed.required_skills),
        applicant_count=processed.applicant_count,
        easy_apply=processed.easy_apply,
        posted_date=processed.posted_date,
        relative_posted_time=processed.relative_posted_time,
        recruiter_name=processed.recruiter_name,
        recruiter_profile_url=processed.recruiter_profile_url,
        status=processed.processing_status,
    )


def _upsert_association(
    db: Session,
    scraping_job_id: str,
    linkedin_job_pk: str,
    source_rank: int,
    result_status: str,
    detail_fetched: bool,
) -> None:
    """Create or update the search-to-job association (no duplicates)."""
    existing = db.execute(
        select(ScrapingJobResult).where(
            ScrapingJobResult.scraping_job_id == scraping_job_id,
            ScrapingJobResult.linkedin_job_id == linkedin_job_pk,
        )
    ).scalar_one_or_none()

    if existing is None:
        db.add(
            ScrapingJobResult(
                scraping_job_id=scraping_job_id,
                linkedin_job_id=linkedin_job_pk,
                source_rank=source_rank,
                result_status=result_status,
                detail_fetched=detail_fetched,
            )
        )
    else:
        existing.source_rank = source_rank
        existing.result_status = result_status
        existing.detail_fetched = detail_fetched


def upsert_linkedin_job(
    db: Session,
    processed_job: ProcessedJobData,
    scraping_job_id: str,
    source_rank: int,
    detail_fetched: bool = True,
) -> tuple[LinkedInJob, bool]:
    """Insert or update a canonical job and its association.

    Returns ``(job, created)`` where ``created`` is True for a new canonical
    record. Commits on success; rolls back and raises ``JobPersistenceError``
    on database failure.
    """
    try:
        existing = find_existing_job(db, processed_job)
        if existing is None:
            job = _build_new_job(processed_job, scraping_job_id)
            db.add(job)
            db.flush()  # assign primary key
            created = True
        else:
            job = existing
            _apply_updates(job, processed_job)
            created = False

        db.flush()
        _upsert_association(
            db,
            scraping_job_id=scraping_job_id,
            linkedin_job_pk=job.id,
            source_rank=source_rank,
            result_status=processed_job.processing_status,
            detail_fetched=detail_fetched,
        )
        db.commit()
        db.refresh(job)
        return job, created
    except SQLAlchemyError as exc:
        db.rollback()
        raise JobPersistenceError("Failed to persist job.") from exc
