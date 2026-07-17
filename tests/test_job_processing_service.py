"""Tests for the end-to-end job processing service."""

from datetime import UTC, datetime

from app.schemas.parsed_job import JobCardData, JobDetailData
from app.schemas.processed_job import ProcessingStatus
from app.services.job_processing_service import JobProcessingService

REFERENCE = datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC)
JOB_URL = "https://www.linkedin.com/jobs/view/12345/"

service = JobProcessingService()


def _card(**kwargs) -> JobCardData:
    base = {
        "linkedin_job_id": "12345",
        "title": "Python Engineer",
        "company_name": "Acme",
        "location": "Karachi, Pakistan",
        "job_url": JOB_URL,
    }
    base.update(kwargs)
    return JobCardData(**base)


def _full_detail() -> JobDetailData:
    return JobDetailData(
        linkedin_job_id="12345",
        title="Senior Python Engineer",
        job_url=JOB_URL,
        workplace_type="Remote",
        employment_type="Full-time",
        experience_level="Mid-Senior level",
        salary_text="$80,000 - $120,000 per year",
        applicant_count_text="Over 100 applicants",
        job_description="We use Python, PyTorch and Machine Learning.",
        posted_text="2 days ago",
    )


def test_complete_when_core_detail_present() -> None:
    result = service.process(_card(), _full_detail(), REFERENCE)
    assert result.status == ProcessingStatus.COMPLETE.value
    job = result.job
    assert job is not None
    assert job.title == "Senior Python Engineer"
    assert job.country == "Pakistan"
    assert job.salary_min == 80000 and job.salary_max == 120000
    assert job.applicant_count == 100
    assert "Python" in job.required_skills
    assert job.posted_date is not None


def test_partial_when_detail_missing() -> None:
    result = service.process(_card(), None, REFERENCE)
    assert result.status == ProcessingStatus.PARTIAL.value
    assert result.job is not None
    assert result.job.title == "Python Engineer"


def test_failed_when_title_missing() -> None:
    card = JobCardData(title=None, job_url=JOB_URL)
    result = service.process(card, None, REFERENCE)
    assert result.status == ProcessingStatus.FAILED.value
    assert result.job is None


def test_failed_when_job_url_invalid() -> None:
    card = JobCardData(title="Engineer", job_url="https://www.linkedin.com/feed/")
    result = service.process(card, None, REFERENCE)
    assert result.status == ProcessingStatus.FAILED.value
    assert result.error_type == "invalid_job_url"


def test_salary_period_warning_for_monthly() -> None:
    detail = _full_detail()
    detail.salary_text = "PKR 100,000 per month"
    result = service.process(_card(), detail, REFERENCE)
    assert any("per month" in w for w in result.warnings)


def test_normalized_url_strips_tracking() -> None:
    card = _card(job_url=JOB_URL + "?refId=abc")
    result = service.process(card, None, REFERENCE)
    assert result.job is not None
    assert result.job.normalized_job_url == JOB_URL
