"""Reusable HTML extraction and text-cleaning helpers.

These operate on BeautifulSoup ``Tag`` elements and are shared by the search
and job-detail parsers. Text cleaning collapses whitespace without damaging
technical terms such as ``C++``, ``C#``, ``.NET`` and ``Node.js``.
"""

import re
from urllib.parse import urlsplit, urlunsplit

from bs4 import Tag

_MULTI_SPACE_PATTERN = re.compile(r"[ \t\f\v]+")
_MULTI_BLANK_LINE_PATTERN = re.compile(r"\n{3,}")
_JOB_ID_FROM_URL_PATTERN = re.compile(r"/jobs/view/(\d+)")
_TRAILING_ID_PATTERN = re.compile(r"(\d{5,})")


def first_text(element: Tag | None, selectors: list[str]) -> str | None:
    """Return cleaned text of the first selector that matches, else None."""
    if element is None:
        return None
    for selector in selectors:
        found = element.select_one(selector)
        if found is not None:
            text = clean_extracted_text(found.get_text())
            if text:
                return text
    return None


def first_attribute(
    element: Tag | None,
    selectors: list[str],
    attribute: str,
) -> str | None:
    """Return the attribute value of the first matching selector, else None."""
    if element is None:
        return None
    for selector in selectors:
        found = element.select_one(selector)
        if found is None:
            continue
        value = found.get(attribute)
        if isinstance(value, list):  # multi-valued attributes (e.g. class)
            value = " ".join(value)
        if value:
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def element_matches(element: Tag | None, selectors: list[str]) -> bool:
    """Return True if the element contains any of the given selectors."""
    if element is None:
        return False
    return any(element.select_one(selector) is not None for selector in selectors)


def clean_extracted_text(
    value: str | None,
    preserve_line_breaks: bool = False,
) -> str | None:
    """Normalize whitespace, returning None for empty/unavailable values.

    When ``preserve_line_breaks`` is True, newlines are kept (collapsing runs
    of three or more blank lines to two) so job descriptions stay readable.
    Otherwise all whitespace collapses to single spaces.
    """
    if value is None:
        return None

    # Normalize non-breaking spaces that LinkedIn frequently emits.
    text = value.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")

    if preserve_line_breaks:
        lines = [_MULTI_SPACE_PATTERN.sub(" ", line).strip() for line in text.split("\n")]
        text = "\n".join(lines)
        text = _MULTI_BLANK_LINE_PATTERN.sub("\n\n", text)
        text = text.strip()
    else:
        text = _MULTI_SPACE_PATTERN.sub(" ", text.replace("\n", " ")).strip()

    return text or None


def extract_linkedin_job_id(
    job_url: str | None,
    raw_job_id: str | None = None,
) -> str | None:
    """Derive the numeric LinkedIn job id from a URL or a raw attribute value.

    The URL form ``/jobs/view/{id}/`` is preferred. Otherwise the raw value
    (e.g. a ``data-entity-urn`` like ``urn:li:jobPosting:12345``) is scanned
    for a trailing numeric id.
    """
    if job_url:
        match = _JOB_ID_FROM_URL_PATTERN.search(job_url)
        if match:
            return match.group(1)

    if raw_job_id:
        candidate = raw_job_id.strip()
        if candidate.isdigit():
            return candidate
        match = _TRAILING_ID_PATTERN.search(candidate)
        if match:
            return match.group(1)

    return None


def normalize_linkedin_url(
    url: str | None,
    base_url: str = "https://www.linkedin.com",
) -> str | None:
    """Convert a relative LinkedIn URL to an absolute HTTPS URL.

    Query strings and fragments are stripped so URLs normalize consistently
    for duplicate detection. Already-absolute non-LinkedIn URLs are returned
    unchanged (validation happens separately). Returns None for empty input.
    """
    if not url:
        return None

    cleaned = url.strip()
    if not cleaned:
        return None

    parts = urlsplit(cleaned)

    if parts.scheme and parts.netloc:
        # Absolute URL: drop query/fragment but keep scheme/host/path.
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    # Relative URL: resolve against the base host.
    base = urlsplit(base_url)
    path = cleaned.split("?", 1)[0].split("#", 1)[0]
    if not path.startswith("/"):
        path = "/" + path
    return urlunsplit((base.scheme or "https", base.netloc, path, "", ""))
