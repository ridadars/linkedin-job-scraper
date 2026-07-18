"""Phase 4.1: salary pay-period parsing and propagation."""

from datetime import UTC, datetime

from app.schemas.parsed_job import JobCardData, JobDetailData
from app.services.job_processing_service import JobProcessingService
from app.services.salary_parser_service import parse_salary_text

REFERENCE = datetime(2026, 7, 18, tzinfo=UTC)
JOB_URL = "https://www.linkedin.com/jobs/view/12345/"
service = JobProcessingService()


def test_period_hour() -> None:
    assert parse_salary_text("EUR 40 - 60 per hour").period == "hour"


def test_period_day() -> None:
    assert parse_salary_text("USD 400 per day").period == "day"


def test_period_week() -> None:
    assert parse_salary_text("GBP 1,500 per week").period == "week"


def test_period_month() -> None:
    assert parse_salary_text("PKR 100,000 per month").period == "month"


def test_period_year() -> None:
    assert parse_salary_text("USD 80,000 - 120,000 per year").period == "year"


def test_period_missing() -> None:
    assert parse_salary_text("USD 80,000").period is None


def test_period_lowercase() -> None:
    assert parse_salary_text("USD 90,000 ANNUALLY").period == "year"


def test_raw_text_unchanged() -> None:
    raw = "PKR 100,000 per month"
    assert parse_salary_text(raw).raw_text == raw


def _card() -> JobCardData:
    return JobCardData(
        linkedin_job_id="12345",
        title="Python Engineer",
        company_name="Acme",
        location="Karachi, Pakistan",
        job_url=JOB_URL,
    )


def _detail(salary_text: str | None) -> JobDetailData:
    return JobDetailData(
        linkedin_job_id="12345",
        title="Senior Python Engineer",
        job_url=JOB_URL,
        employment_type="Full-time",
        experience_level="Mid-Senior level",
        job_description="Python role.",
        salary_text=salary_text,
    )


def test_processing_populates_month_period() -> None:
    result = service.process(_card(), _detail("PKR 100,000 per month"), REFERENCE)
    assert result.job is not None
    assert result.job.salary_period == "month"
    assert result.job.salary_min == 100000
    assert result.job.salary_max == 100000  # not annualized


def test_processing_populates_hour_period() -> None:
    result = service.process(_card(), _detail("EUR 40 - 60 per hour"), REFERENCE)
    assert result.job is not None
    assert result.job.salary_period == "hour"
    assert result.job.salary_currency == "EUR"


def test_processing_period_none_when_absent() -> None:
    result = service.process(_card(), _detail(None), REFERENCE)
    assert result.job is not None
    assert result.job.salary_period is None
