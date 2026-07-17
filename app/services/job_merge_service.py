"""Merge search-card and job-detail data into a single raw field set.

Detail-page values win when present; card values fill the gaps. A valid card
value is never overwritten with ``None``. Conflicting job IDs produce a warning
and the ID derived from the validated final job-detail URL is preferred.

The returned dict holds *raw* (un-normalized) values plus a ``warnings`` list;
normalization and enrichment happen later in the processing service.
"""

from app.schemas.parsed_job import JobCardData, JobDetailData
from app.utils.html_parser import normalize_linkedin_url
from app.utils.linkedin_url_validator import is_allowed_linkedin_url


def _prefer(detail_value, card_value):
    """Return the detail value when it is meaningful, else the card value."""
    if detail_value is not None and detail_value != "":
        return detail_value
    return card_value


def merge_job_data(card: JobCardData, detail: JobDetailData | None) -> dict:
    """Merge a card and optional detail into a raw field dict with warnings."""
    warnings: list[str] = []
    detail = detail or JobDetailData()

    # Resolve job URL: prefer a valid detail URL, else the card URL.
    detail_url = normalize_linkedin_url(detail.job_url)
    card_url = normalize_linkedin_url(card.job_url)
    if detail_url and is_allowed_linkedin_url(detail_url):
        job_url = detail_url
    elif card_url and is_allowed_linkedin_url(card_url):
        job_url = card_url
    else:
        job_url = detail_url or card_url  # may be invalid; validated downstream

    # Resolve job id, warning on genuine conflict.
    card_id = card.linkedin_job_id
    detail_id = detail.linkedin_job_id
    if card_id and detail_id and card_id != detail_id:
        warnings.append(
            "Job ID conflict between card and detail; preferring detail-URL id."
        )
        linkedin_job_id = detail_id
    else:
        linkedin_job_id = detail_id or card_id

    merged = {
        "linkedin_job_id": linkedin_job_id,
        "title": _prefer(detail.title, card.title),
        "company_name": _prefer(detail.company_name, card.company_name),
        "company_url": _prefer(detail.company_url, card.company_url),
        "job_url": job_url,
        "location": _prefer(detail.location, card.location),
        "workplace_type": detail.workplace_type,
        "employment_type": detail.employment_type,
        "experience_level": detail.experience_level,
        "salary_text": detail.salary_text,
        "description": detail.job_description,
        "applicant_count_text": detail.applicant_count_text,
        "posted_text": _prefer(detail.posted_text, card.posted_text),
        "easy_apply": _prefer(detail.easy_apply, card.easy_apply),
        "recruiter_name": detail.recruiter_name,
        "recruiter_profile_url": detail.recruiter_profile_url,
        "warnings": warnings,
    }
    return merged
