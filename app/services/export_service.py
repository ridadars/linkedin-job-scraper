"""CSV and JSON export builders for canonical jobs.

Pure, in-memory serialization — no files are written and no network access
occurs. CSV is UTF-8 with one job per row and skills joined by ``; ``. JSON
includes a generated timestamp, total count, and caller-supplied metadata
(filters or scraping-job info) alongside the job list.
"""

import csv
import io
import re
from datetime import UTC, datetime

from app.schemas.job_result import JobItem

# Column order for CSV exports.
CSV_COLUMNS = [
    "id",
    "linkedin_job_id",
    "title",
    "company_name",
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
    "skills",
    "applicant_count",
    "easy_apply",
    "posted_date",
    "job_url",
    "processing_status",
]

SKILLS_SEPARATOR = "; "

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


def _now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def safe_filename(base: str, extension: str) -> str:
    """Build a filesystem-safe, timestamped download filename."""
    cleaned = _SAFE_NAME.sub("_", base).strip("_") or "export"
    return f"{cleaned}_{_now_stamp()}.{extension}"


def _row(item: JobItem) -> dict:
    posted = item.posted_date.isoformat() if item.posted_date else ""
    return {
        "id": item.id,
        "linkedin_job_id": item.linkedin_job_id or "",
        "title": item.title or "",
        "company_name": item.company_name or "",
        "location": item.location or "",
        "country": item.country or "",
        "workplace_type": item.workplace_type or "",
        "employment_type": item.employment_type or "",
        "experience_level": item.experience_level or "",
        "salary_min": item.salary_min if item.salary_min is not None else "",
        "salary_max": item.salary_max if item.salary_max is not None else "",
        "salary_currency": item.salary_currency or "",
        "salary_period": item.salary_period or "",
        "salary_text": item.salary_text or "",
        "skills": SKILLS_SEPARATOR.join(item.skills),
        "applicant_count": item.applicant_count if item.applicant_count is not None else "",
        "easy_apply": "" if item.easy_apply is None else str(item.easy_apply).lower(),
        "posted_date": posted,
        "job_url": item.job_url or "",
        "processing_status": item.processing_status or "",
    }


def jobs_to_csv(items: list[JobItem]) -> str:
    """Serialize job items to a UTF-8 CSV string (one job per row)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow(_row(item))
    return buffer.getvalue()


def jobs_to_json(items: list[JobItem], metadata: dict | None = None) -> dict:
    """Build the JSON export payload with a generated timestamp and totals."""
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_jobs": len(items),
        "metadata": metadata or {},
        "jobs": [item.model_dump(mode="json") for item in items],
    }
