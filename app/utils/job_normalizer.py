"""Field normalization for processed jobs.

Cleans free-text values and maps LinkedIn's human-readable categorical labels
(e.g. "Full-time", "Mid-Senior level", "Remote") to the same stable storage
values used by the Phase 2 search filters. URL normalization strips tracking
parameters while preserving only validated LinkedIn job URLs. Country inference
is intentionally conservative — it only fires on clear mappings.
"""

from app.exceptions import InvalidLinkedInUrlError
from app.utils.html_parser import normalize_linkedin_url
from app.utils.linkedin_url_validator import validate_linkedin_job_url
from app.utils.search_normalizer import collapse_spaces, trim_text


def _clean(value: str | None) -> str | None:
    """Trim and collapse whitespace, returning None for empty values."""
    if value is None:
        return None
    cleaned = collapse_spaces(trim_text(value))
    return cleaned or None


def normalize_job_title(value: str | None) -> str | None:
    """Normalize a job title, preserving meaningful punctuation."""
    return _clean(value)


def normalize_company_name(value: str | None) -> str | None:
    """Normalize a company name."""
    return _clean(value)


def normalize_location(value: str | None) -> str | None:
    """Normalize a location string."""
    return _clean(value)


# Map lowercased free-text labels to stable storage values.
_WORKPLACE_MAP = {
    "on-site": "onsite",
    "onsite": "onsite",
    "on site": "onsite",
    "remote": "remote",
    "hybrid": "hybrid",
}

_EMPLOYMENT_MAP = {
    "full-time": "full_time",
    "full time": "full_time",
    "part-time": "part_time",
    "part time": "part_time",
    "contract": "contract",
    "temporary": "temporary",
    "internship": "internship",
    "intern": "internship",
    "volunteer": "volunteer",
}

_EXPERIENCE_MAP = {
    "internship": "internship",
    "intern": "internship",
    "entry level": "entry_level",
    "entry-level": "entry_level",
    "associate": "associate",
    "mid-senior level": "mid_senior",
    "mid-senior": "mid_senior",
    "mid senior level": "mid_senior",
    "director": "director",
    "executive": "executive",
}


def _map_label(value: str | None, mapping: dict[str, str]) -> str | None:
    """Look up a cleaned, lowercased label in a mapping."""
    cleaned = _clean(value)
    if cleaned is None:
        return None
    return mapping.get(cleaned.lower())


def normalize_workplace_type(value: str | None) -> str | None:
    """Map workplace text to onsite/remote/hybrid, else None."""
    return _map_label(value, _WORKPLACE_MAP)


def normalize_employment_type(value: str | None) -> str | None:
    """Map employment text to a stable employment-type value, else None."""
    return _map_label(value, _EMPLOYMENT_MAP)


def normalize_experience_level(value: str | None) -> str | None:
    """Map experience text to a stable experience-level value, else None."""
    return _map_label(value, _EXPERIENCE_MAP)


def normalize_job_url(value: str) -> str:
    """Normalize and validate a LinkedIn job URL.

    Strips query/fragment (tracking parameters) and confirms the result is a
    permitted ``/jobs/view/{id}/`` URL. Raises ``InvalidLinkedInUrlError``
    otherwise.
    """
    normalized = normalize_linkedin_url(value)
    if not normalized:
        raise InvalidLinkedInUrlError("Job URL is empty after normalization.")
    return validate_linkedin_job_url(normalized)


# Conservative country inference. Keys are lowercased tokens; only clear,
# unambiguous mappings are included. Anything else returns None.
_CITY_COUNTRY = {
    "karachi": "Pakistan",
    "lahore": "Pakistan",
    "islamabad": "Pakistan",
    "rawalpindi": "Pakistan",
    "faisalabad": "Pakistan",
}
_KNOWN_COUNTRIES = {
    "pakistan": "Pakistan",
    "united states": "United States",
    "usa": "United States",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "germany": "Germany",
    "canada": "Canada",
}


def infer_country(location: str | None) -> str | None:
    """Infer a country from a location string, only for clear mappings."""
    cleaned = _clean(location)
    if cleaned is None:
        return None

    lowered = cleaned.lower()

    # Prefer an explicit country name appearing as a comma-separated segment
    # or the whole string.
    segments = [segment.strip().lower() for segment in cleaned.split(",")]
    for segment in reversed(segments):
        if segment in _KNOWN_COUNTRIES:
            return _KNOWN_COUNTRIES[segment]

    if lowered in _KNOWN_COUNTRIES:
        return _KNOWN_COUNTRIES[lowered]

    # Fall back to a known-city mapping.
    for segment in segments:
        if segment in _CITY_COUNTRY:
            return _CITY_COUNTRY[segment]

    return None
