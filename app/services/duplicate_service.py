"""Deterministic global duplicate detection for canonical jobs.

Matching priority:

1. LinkedIn job ID (exact)
2. Normalized LinkedIn job URL (exact)
3. SHA-256 fingerprint of normalized title + company + location

The fingerprint is a stable SHA-256 hash (never Python's built-in ``hash()``),
so results are reproducible across processes. Different companies or different
locations only collide when the job ID or URL matches — never via the
fingerprint alone.
"""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.linkedin_job import LinkedInJob
from app.schemas.processed_job import ProcessedJobData
from app.utils.search_normalizer import collapse_spaces, trim_text


def _norm(value: str | None) -> str:
    """Lowercase and whitespace-normalize a fingerprint component."""
    if not value:
        return ""
    return collapse_spaces(trim_text(value)).lower()


def build_job_fingerprint(
    title: str,
    company_name: str | None,
    location: str | None,
) -> str:
    """Return a deterministic SHA-256 fingerprint of the identity fields."""
    parts = [_norm(title), _norm(company_name), _norm(location)]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_existing_job(
    db: Session,
    processed_job: ProcessedJobData,
) -> LinkedInJob | None:
    """Find an existing canonical job matching ``processed_job``, or None."""
    # 1. Exact LinkedIn job ID.
    if processed_job.linkedin_job_id:
        existing = db.execute(
            select(LinkedInJob)
            .where(LinkedInJob.linkedin_job_id == processed_job.linkedin_job_id)
            .limit(1)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    # 2. Normalized job URL.
    if processed_job.normalized_job_url:
        existing = db.execute(
            select(LinkedInJob)
            .where(LinkedInJob.normalized_job_url == processed_job.normalized_job_url)
            .limit(1)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    # 3. Title/company/location fingerprint fallback.
    target = build_job_fingerprint(
        processed_job.title,
        processed_job.company_name,
        processed_job.location,
    )
    candidates = db.execute(
        select(LinkedInJob).where(LinkedInJob.title.isnot(None))
    ).scalars()
    for candidate in candidates:
        candidate_fp = build_job_fingerprint(
            candidate.title or "",
            candidate.company_name,
            candidate.location,
        )
        if candidate_fp == target:
            return candidate

    return None
