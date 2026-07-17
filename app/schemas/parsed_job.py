"""Parser result schemas.

These are plain Pydantic models returned by the HTML parsers. Every extracted
field is optional because LinkedIn markup varies and missing data must never
crash a parser. Parsers never return SQLAlchemy models; persistence is a later
phase.
"""

from pydantic import BaseModel

from app.services.page_state_service import PageState


class JobCardData(BaseModel):
    """A single job card extracted from a search-results page."""

    linkedin_job_id: str | None = None
    title: str | None = None
    company_name: str | None = None
    location: str | None = None
    job_url: str | None = None
    company_url: str | None = None
    posted_text: str | None = None
    easy_apply: bool | None = None


class JobDetailData(BaseModel):
    """Structured data extracted from an individual job-detail page."""

    linkedin_job_id: str | None = None
    title: str | None = None
    company_name: str | None = None
    company_url: str | None = None
    job_url: str | None = None
    location: str | None = None
    workplace_type: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    salary_text: str | None = None
    job_description: str | None = None
    applicant_count_text: str | None = None
    posted_text: str | None = None
    easy_apply: bool | None = None
    recruiter_name: str | None = None
    recruiter_profile_url: str | None = None


class SearchPageResult(BaseModel):
    """The outcome of parsing one search-results page."""

    jobs: list[JobCardData] = []
    discovered_count: int = 0
    page_state: PageState = PageState.normal
