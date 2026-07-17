"""Individual job-detail HTML parser.

Turns a single LinkedIn job-view page into a :class:`JobDetailData`. Blocked
pages raise the appropriate structured exception and removed/expired jobs raise
:class:`JobPageNotFoundError`. Every field is optional; missing data yields
``None`` rather than an error. Description formatting (line breaks) is
preserved. No numeric/date/skill derivation happens here — that is a later
phase.
"""

import logging

from bs4 import BeautifulSoup

from app.exceptions import (
    AccessRestrictedError,
    AuthenticationRequiredError,
    CaptchaDetectedError,
    JobPageNotFoundError,
)
from app.linkedin_selectors import (
    APPLICANT_COUNT,
    COMPANY_NAME,
    COMPANY_URL,
    EASY_APPLY,
    EMPLOYMENT_TYPE,
    EXPERIENCE_LEVEL,
    JOB_DESCRIPTION,
    JOB_TITLE,
    LOCATION,
    POSTED_DATE,
    RECRUITER_NAME,
    RECRUITER_PROFILE_URL,
    SALARY,
    WORKPLACE_TYPE,
)
from app.schemas.parsed_job import JobDetailData
from app.services.page_state_service import PageState, detect_page_state
from app.utils.html_parser import (
    clean_extracted_text,
    element_matches,
    extract_linkedin_job_id,
    first_attribute,
    first_text,
    normalize_linkedin_url,
)
from app.utils.linkedin_url_validator import (
    is_allowed_linkedin_url,
    is_linkedin_domain_url,
)

logger = logging.getLogger(__name__)


def _extract_description(soup: BeautifulSoup) -> str | None:
    """Extract the job description, preserving readable line breaks."""
    for selector in JOB_DESCRIPTION:
        element = soup.select_one(selector)
        if element is not None:
            # Convert <br> to newlines and treat block tags as line breaks so
            # the description stays readable.
            text = element.get_text(separator="\n")
            cleaned = clean_extracted_text(text, preserve_line_breaks=True)
            if cleaned:
                return cleaned
    return None


def _safe_job_url(raw_url: str | None) -> str | None:
    """Normalize and return a URL only if it is a permitted job/search URL."""
    normalized = normalize_linkedin_url(raw_url)
    if normalized and is_allowed_linkedin_url(normalized):
        return normalized
    return None


def _safe_domain_url(raw_url: str | None) -> str | None:
    """Normalize and return an auxiliary URL only if it is on linkedin.com.

    Used for company pages and recruiter profiles, whose paths are not the
    jobs paths but which must still be genuine LinkedIn HTTPS URLs.
    """
    normalized = normalize_linkedin_url(raw_url)
    if normalized and is_linkedin_domain_url(normalized):
        return normalized
    return None


def parse_job_detail(html: str, current_url: str) -> JobDetailData:
    """Parse a job-detail page into a :class:`JobDetailData`."""
    state = detect_page_state(html, current_url)

    if state is PageState.captcha:
        raise CaptchaDetectedError()
    if state is PageState.authentication_required:
        raise AuthenticationRequiredError()
    if state is PageState.access_restricted:
        raise AccessRestrictedError()
    if state is PageState.job_not_found:
        raise JobPageNotFoundError()

    soup = BeautifulSoup(html or "", "lxml")

    job_url = _safe_job_url(current_url) or normalize_linkedin_url(current_url)
    job_id = extract_linkedin_job_id(current_url)

    # Recruiter data is optional and must never fail the parse.
    recruiter_name = first_text(soup, RECRUITER_NAME)
    recruiter_profile_url = _safe_domain_url(
        first_attribute(soup, RECRUITER_PROFILE_URL, "href")
    )

    detail = JobDetailData(
        linkedin_job_id=job_id,
        title=first_text(soup, JOB_TITLE),
        company_name=first_text(soup, COMPANY_NAME),
        company_url=_safe_domain_url(first_attribute(soup, COMPANY_URL, "href")),
        job_url=job_url,
        location=first_text(soup, LOCATION),
        workplace_type=first_text(soup, WORKPLACE_TYPE),
        employment_type=first_text(soup, EMPLOYMENT_TYPE),
        experience_level=first_text(soup, EXPERIENCE_LEVEL),
        salary_text=first_text(soup, SALARY),
        job_description=_extract_description(soup),
        applicant_count_text=first_text(soup, APPLICANT_COUNT),
        posted_text=first_text(soup, POSTED_DATE),
        easy_apply=True if element_matches(soup, EASY_APPLY) else None,
        recruiter_name=recruiter_name,
        recruiter_profile_url=recruiter_profile_url,
    )

    logger.info("Parsed job-detail page (job_id=%s).", job_id or "unknown")
    return detail
