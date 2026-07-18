"""Response schemas for canonical job results and listings."""

import json
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import PaginatedResponse


def parse_skills(required_skills_json: str | None) -> list[str]:
    """Decode the stored JSON skills list, tolerating bad/empty data."""
    if not required_skills_json:
        return []
    try:
        value = json.loads(required_skills_json)
    except (ValueError, TypeError):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


class JobItem(BaseModel):
    """A canonical LinkedIn job as returned by the results/jobs APIs."""

    id: str
    linkedin_job_id: str | None = None
    title: str | None = None
    company_name: str | None = None
    location: str | None = None
    country: str | None = None
    workplace_type: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_text: str | None = None
    skills: list[str] = []
    applicant_count: int | None = None
    posted_date: datetime | None = None
    easy_apply: bool | None = None
    job_url: str | None = None
    processing_status: str | None = None

    @classmethod
    def from_orm_job(cls, job) -> "JobItem":
        """Build a JobItem from a ``LinkedInJob`` ORM row."""
        return cls(
            id=job.id,
            linkedin_job_id=job.linkedin_job_id,
            title=job.title,
            company_name=job.company_name,
            location=job.location,
            country=job.country,
            workplace_type=job.workplace_type,
            employment_type=job.employment_type,
            experience_level=job.experience_level,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            salary_currency=job.salary_currency,
            salary_period=job.salary_period,
            salary_text=job.salary_text,
            skills=parse_skills(job.required_skills_json),
            applicant_count=job.applicant_count,
            posted_date=job.posted_date,
            easy_apply=job.easy_apply,
            job_url=job.job_url,
            processing_status=job.status,
        )


class JobListResponse(BaseModel):
    """Paginated list of canonical jobs."""

    pagination: PaginatedResponse
    items: list[JobItem]


class ScrapingJobResultsResponse(BaseModel):
    """Paginated jobs discovered by a specific scraping job."""

    scraping_job_id: str
    pagination: PaginatedResponse
    items: list[JobItem]
