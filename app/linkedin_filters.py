"""Centralized LinkedIn job-search query-parameter mappings.

These codes reflect LinkedIn's public jobs-search URL parameters as observed
on https://www.linkedin.com/jobs/search/. Update this module if LinkedIn changes
its filter encoding — business logic should import from here only.
"""

from typing import Final

LINKEDIN_JOBS_SEARCH_BASE_URL: Final[str] = "https://www.linkedin.com/jobs/search/"

ALLOWED_LINKEDIN_DOMAINS: Final[frozenset[str]] = frozenset(
    {"www.linkedin.com", "linkedin.com"}
)

# f_E — experience level filter codes
EXPERIENCE_LEVEL_CODES: Final[dict[str, str]] = {
    "internship": "1",
    "entry_level": "2",
    "associate": "3",
    "mid_senior": "4",
    "director": "5",
    "executive": "6",
}

# f_JT — employment / job type filter codes
EMPLOYMENT_TYPE_CODES: Final[dict[str, str]] = {
    "full_time": "F",
    "part_time": "P",
    "contract": "C",
    "temporary": "T",
    "internship": "I",
    "volunteer": "V",
}

# f_WT — workplace type filter codes
WORKPLACE_TYPE_CODES: Final[dict[str, str]] = {
    "onsite": "1",
    "remote": "2",
    "hybrid": "3",
}

# f_TPR — date posted filter (relative time in seconds)
DATE_POSTED_CODES: Final[dict[str, str]] = {
    "past_24_hours": "r86400",
    "past_week": "r604800",
    "past_month": "r2592000",
}

# f_AL — Easy Apply filter
EASY_APPLY_PARAM: Final[str] = "f_AL"
EASY_APPLY_VALUE: Final[str] = "true"

# LinkedIn query parameter names
PARAM_KEYWORDS: Final[str] = "keywords"
PARAM_LOCATION: Final[str] = "location"
PARAM_EXPERIENCE: Final[str] = "f_E"
PARAM_EMPLOYMENT: Final[str] = "f_JT"
PARAM_WORKPLACE: Final[str] = "f_WT"
PARAM_DATE_POSTED: Final[str] = "f_TPR"

# Deterministic parameter order for URL generation
FILTER_PARAM_ORDER: Final[tuple[str, ...]] = (
    PARAM_EXPERIENCE,
    PARAM_EMPLOYMENT,
    PARAM_WORKPLACE,
    PARAM_DATE_POSTED,
    EASY_APPLY_PARAM,
)
