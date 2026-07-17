"""Processing-stage result schemas.

``ProcessedJobData`` is the normalized, enriched representation of a job after
card+detail merge, skill extraction, and salary/applicant/date parsing. Its
fields align with the ``LinkedInJob`` database model but it is a plain Pydantic
model — never a SQLAlchemy object — used as the intermediate processing object.

``JobProcessingResult`` wraps the outcome with a status and any warnings.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ProcessingStatus(StrEnum):
    """Outcome of processing a single job."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class ProcessedJobData(BaseModel):
    """Normalized, enriched job data ready for persistence."""

    linkedin_job_id: str | None = None
    title: str
    company_name: str | None = None
    company_url: str | None = None
    job_url: str
    normalized_job_url: str
    location: str | None = None
    country: str | None = None
    workplace_type: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None

    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_text: str | None = None

    description: str | None = None
    required_skills: list[str] = Field(default_factory=list)

    applicant_count: int | None = None
    easy_apply: bool | None = None

    posted_date: datetime | None = None
    relative_posted_time: str | None = None
    application_deadline: datetime | None = None

    company_industry: str | None = None
    company_size: str | None = None
    company_website: str | None = None

    recruiter_name: str | None = None
    recruiter_profile_url: str | None = None

    processing_status: str = ProcessingStatus.COMPLETE.value
    processing_warnings: list[str] = Field(default_factory=list)


class JobProcessingResult(BaseModel):
    """The result of processing one card (+ optional detail)."""

    job: ProcessedJobData | None = None
    status: str
    warnings: list[str] = Field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None
