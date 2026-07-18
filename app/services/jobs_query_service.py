"""Query service for canonical jobs: filtering, sorting, and pagination.

Builds deterministic SQLAlchemy queries over ``LinkedInJob`` and over the jobs
discovered by a specific scraping job (via ``ScrapingJobResult``). All string
filters are case-insensitive substring matches; categorical filters are exact.
Results are always given a stable secondary ordering by ``id`` so responses are
reproducible.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.orm import Session

from app.models.linkedin_job import LinkedInJob
from app.models.scraping_job_result import ScrapingJobResult


@dataclass
class JobFilters:
    """Optional filters for the jobs listing endpoint."""

    keyword: str | None = None
    company: str | None = None
    location: str | None = None
    country: str | None = None
    workplace_type: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    skill: str | None = None
    easy_apply: bool | None = None
    posted_after: datetime | None = None
    posted_before: datetime | None = None


def _apply_filters(stmt: Select, filters: JobFilters) -> Select:
    """Apply the provided filters to a LinkedInJob select statement."""
    if filters.keyword:
        like = f"%{filters.keyword}%"
        stmt = stmt.where(
            LinkedInJob.title.ilike(like)
            | LinkedInJob.company_name.ilike(like)
            | LinkedInJob.description.ilike(like)
        )
    if filters.company:
        stmt = stmt.where(LinkedInJob.company_name.ilike(f"%{filters.company}%"))
    if filters.location:
        stmt = stmt.where(LinkedInJob.location.ilike(f"%{filters.location}%"))
    if filters.country:
        stmt = stmt.where(LinkedInJob.country.ilike(f"%{filters.country}%"))
    if filters.workplace_type:
        stmt = stmt.where(LinkedInJob.workplace_type == filters.workplace_type)
    if filters.employment_type:
        stmt = stmt.where(LinkedInJob.employment_type == filters.employment_type)
    if filters.experience_level:
        stmt = stmt.where(LinkedInJob.experience_level == filters.experience_level)
    if filters.skill:
        # Skills are stored as a JSON array of canonical names.
        stmt = stmt.where(LinkedInJob.required_skills_json.ilike(f"%{filters.skill}%"))
    if filters.easy_apply is not None:
        stmt = stmt.where(LinkedInJob.easy_apply.is_(filters.easy_apply))
    if filters.posted_after is not None:
        stmt = stmt.where(LinkedInJob.posted_date >= filters.posted_after)
    if filters.posted_before is not None:
        stmt = stmt.where(LinkedInJob.posted_date <= filters.posted_before)
    return stmt


def _order(stmt: Select, sort: str) -> Select:
    """Apply deterministic ordering. ``sort`` is 'newest' (default) or 'oldest'."""
    direction = asc if sort == "oldest" else desc
    return stmt.order_by(direction(LinkedInJob.scraped_at), LinkedInJob.id)


def query_jobs(
    db: Session,
    filters: JobFilters,
    page: int,
    page_size: int,
    sort: str = "newest",
) -> tuple[list[LinkedInJob], int]:
    """Return a page of filtered canonical jobs and the total match count."""
    base = _apply_filters(select(LinkedInJob), filters)
    total = db.scalar(
        select(func.count()).select_from(_apply_filters(select(LinkedInJob.id), filters).subquery())
    ) or 0
    stmt = _order(base, sort).offset((page - 1) * page_size).limit(page_size)
    jobs = list(db.scalars(stmt).all())
    return jobs, total


def query_all_jobs(db: Session, filters: JobFilters, sort: str = "newest") -> list[LinkedInJob]:
    """Return every filtered canonical job (used for exports, no pagination)."""
    stmt = _order(_apply_filters(select(LinkedInJob), filters), sort)
    return list(db.scalars(stmt).all())


def query_results_for_scraping_job(
    db: Session,
    scraping_job_id: str,
    page: int,
    page_size: int,
) -> tuple[list[LinkedInJob], int]:
    """Return a page of canonical jobs discovered by one scraping job.

    Ordered by the discovery rank recorded on the association.
    """
    join = (
        select(LinkedInJob)
        .join(ScrapingJobResult, ScrapingJobResult.linkedin_job_id == LinkedInJob.id)
        .where(ScrapingJobResult.scraping_job_id == scraping_job_id)
    )
    total = db.scalar(
        select(func.count())
        .select_from(ScrapingJobResult)
        .where(ScrapingJobResult.scraping_job_id == scraping_job_id)
    ) or 0
    stmt = (
        join.order_by(asc(ScrapingJobResult.source_rank), LinkedInJob.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    jobs = list(db.scalars(stmt).all())
    return jobs, total


def all_results_for_scraping_job(db: Session, scraping_job_id: str) -> list[LinkedInJob]:
    """Return every canonical job discovered by one scraping job (for exports)."""
    stmt = (
        select(LinkedInJob)
        .join(ScrapingJobResult, ScrapingJobResult.linkedin_job_id == LinkedInJob.id)
        .where(ScrapingJobResult.scraping_job_id == scraping_job_id)
        .order_by(asc(ScrapingJobResult.source_rank), LinkedInJob.id)
    )
    return list(db.scalars(stmt).all())
