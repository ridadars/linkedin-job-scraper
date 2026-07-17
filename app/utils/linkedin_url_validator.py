"""Safe LinkedIn URL validation.

Only two categories of public LinkedIn job URL are permitted:

* Search results: ``https://www.linkedin.com/jobs/search/``
* A single job view: ``https://www.linkedin.com/jobs/view/{numeric-job-id}/``

Everything else is rejected. This module is the single source of truth for
URL safety and is applied both before navigation and after Playwright
redirects, so a redirect to an off-limits page is caught.
"""

import re
from urllib.parse import urlsplit

from app.exceptions import InvalidLinkedInUrlError

ALLOWED_HOST = "www.linkedin.com"
ALLOWED_SCHEME = "https"

_SEARCH_PATH_PATTERN = re.compile(r"^/jobs/search/?$")
_JOB_VIEW_PATH_PATTERN = re.compile(r"^/jobs/view/(\d+)/?$")


def _split_safe(url: str):
    """Split a URL, converting any parsing failure into a rejection."""
    if not isinstance(url, str) or not url.strip():
        raise InvalidLinkedInUrlError("URL must be a non-empty string.")
    try:
        return urlsplit(url.strip())
    except ValueError as exc:  # malformed URL (e.g. bad IPv6/port)
        raise InvalidLinkedInUrlError("URL is malformed.") from exc


def _validate_host_and_scheme(parts) -> None:
    """Enforce HTTPS scheme, exact host, no credentials, no custom port."""
    if parts.scheme != ALLOWED_SCHEME:
        raise InvalidLinkedInUrlError("URL must use the HTTPS scheme.")

    # Reject embedded username/password (userinfo) before it reaches a browser.
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise InvalidLinkedInUrlError("URL must not contain embedded credentials.")

    # ``hostname`` is lower-cased and strips any port; compare exactly.
    if parts.hostname != ALLOWED_HOST:
        raise InvalidLinkedInUrlError("URL host must be exactly www.linkedin.com.")

    # Reject non-standard ports. ``port`` raises ValueError for junk ports.
    try:
        port = parts.port
    except ValueError as exc:
        raise InvalidLinkedInUrlError("URL has an invalid port.") from exc
    if port is not None and port != 443:
        raise InvalidLinkedInUrlError("URL must not use a non-standard port.")


def validate_linkedin_search_url(url: str) -> str:
    """Return the URL if it is a permitted LinkedIn job-search URL.

    Raises ``InvalidLinkedInUrlError`` otherwise.
    """
    parts = _split_safe(url)
    _validate_host_and_scheme(parts)
    if not _SEARCH_PATH_PATTERN.match(parts.path):
        raise InvalidLinkedInUrlError("URL is not a LinkedIn jobs search URL.")
    return url.strip()


def validate_linkedin_job_url(url: str) -> str:
    """Return the URL if it is a permitted LinkedIn job-view URL.

    Raises ``InvalidLinkedInUrlError`` otherwise.
    """
    parts = _split_safe(url)
    _validate_host_and_scheme(parts)
    if not _JOB_VIEW_PATH_PATTERN.match(parts.path):
        raise InvalidLinkedInUrlError("URL is not a LinkedIn job-view URL.")
    return url.strip()


def is_allowed_linkedin_url(url: str) -> bool:
    """Return True if the URL is either a permitted search or job URL.

    This is the strict check used for navigation targets and job links.
    """
    for validator in (validate_linkedin_search_url, validate_linkedin_job_url):
        try:
            validator(url)
            return True
        except InvalidLinkedInUrlError:
            continue
    return False


def is_linkedin_domain_url(url: str) -> bool:
    """Return True if the URL is a safe HTTPS www.linkedin.com URL, any path.

    Used for *extracted* auxiliary links (company pages, recruiter profiles)
    where the path is not restricted to jobs, but the URL must still be a
    genuine LinkedIn HTTPS URL with no embedded credentials or custom port.
    """
    try:
        parts = _split_safe(url)
        _validate_host_and_scheme(parts)
    except InvalidLinkedInUrlError:
        return False
    return True
