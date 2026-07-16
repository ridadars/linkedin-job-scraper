"""LinkedIn job search URL builder service."""

from urllib.parse import urlencode, urlparse

from app.linkedin_filters import (
    DATE_POSTED_CODES,
    EASY_APPLY_PARAM,
    EASY_APPLY_VALUE,
    EMPLOYMENT_TYPE_CODES,
    EXPERIENCE_LEVEL_CODES,
    FILTER_PARAM_ORDER,
    LINKEDIN_JOBS_SEARCH_BASE_URL,
    PARAM_DATE_POSTED,
    PARAM_EMPLOYMENT,
    PARAM_EXPERIENCE,
    PARAM_KEYWORDS,
    PARAM_LOCATION,
    PARAM_WORKPLACE,
    WORKPLACE_TYPE_CODES,
)
from app.schemas.job_search import DatePosted, JobSearchRequest
from app.utils.search_normalizer import enum_to_storage_value


class InvalidLinkedInUrlError(ValueError):
    """Raised when a URL fails LinkedIn safety validation."""


def _build_filter_params(search_request: JobSearchRequest) -> dict[str, str]:
    """Map selected filters to LinkedIn query parameters."""
    params: dict[str, str] = {}

    if search_request.experience_level is not None:
        code = EXPERIENCE_LEVEL_CODES[
            enum_to_storage_value(search_request.experience_level)  # type: ignore[index]
        ]
        params[PARAM_EXPERIENCE] = code

    if search_request.employment_type is not None:
        code = EMPLOYMENT_TYPE_CODES[
            enum_to_storage_value(search_request.employment_type)  # type: ignore[index]
        ]
        params[PARAM_EMPLOYMENT] = code

    if search_request.workplace_type is not None:
        code = WORKPLACE_TYPE_CODES[
            enum_to_storage_value(search_request.workplace_type)  # type: ignore[index]
        ]
        params[PARAM_WORKPLACE] = code

    if (
        search_request.date_posted is not None
        and search_request.date_posted != DatePosted.ANY_TIME
    ):
        code = DATE_POSTED_CODES[
            enum_to_storage_value(search_request.date_posted)  # type: ignore[index]
        ]
        params[PARAM_DATE_POSTED] = code

    if search_request.easy_apply_only:
        params[EASY_APPLY_PARAM] = EASY_APPLY_VALUE

    return params


def validate_linkedin_url(url: str) -> str:
    """Ensure a URL is HTTPS and belongs to LinkedIn."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise InvalidLinkedInUrlError("Generated URL must use HTTPS.")
    if parsed.netloc not in {"www.linkedin.com", "linkedin.com"}:
        raise InvalidLinkedInUrlError("Generated URL must belong to LinkedIn.")
    if not parsed.path.startswith("/jobs/search"):
        raise InvalidLinkedInUrlError("Generated URL must be a LinkedIn jobs search URL.")
    return url


def build_linkedin_jobs_url(search_request: JobSearchRequest) -> str:
    """Build a deterministic LinkedIn jobs search URL from validated filters."""
    query_parts: list[tuple[str, str]] = [
        (PARAM_KEYWORDS, search_request.keywords),
    ]

    if search_request.location:
        query_parts.append((PARAM_LOCATION, search_request.location))

    filter_params = _build_filter_params(search_request)
    for param_name in FILTER_PARAM_ORDER:
        if param_name in filter_params:
            query_parts.append((param_name, filter_params[param_name]))

    query_string = urlencode(query_parts)
    url = f"{LINKEDIN_JOBS_SEARCH_BASE_URL}?{query_string}"
    return validate_linkedin_url(url)
