"""Blocked-page and empty-result detection.

``detect_page_state`` classifies a fetched LinkedIn page using several signals
combined: the final URL, the page title, dedicated challenge/blocked-page
elements, and a small set of specific phrases. Dedicated selectors do the heavy
lifting so that an ordinary job description mentioning "security", "login", or
"authentication" is never mistaken for a blocked page.
"""

import logging
from enum import Enum

from bs4 import BeautifulSoup

from app.linkedin_selectors import (
    ACCESS_RESTRICTED_ELEMENTS,
    CAPTCHA_ELEMENTS,
    EMPTY_SEARCH_ELEMENTS,
    REMOVED_JOB_ELEMENTS,
    SIGNIN_WALL_ELEMENTS,
)
from app.utils.html_parser import element_matches

logger = logging.getLogger(__name__)


class PageState(str, Enum):
    """Classification of a fetched LinkedIn page."""

    normal = "normal"
    empty_results = "empty_results"
    authentication_required = "authentication_required"
    captcha = "captcha"
    access_restricted = "access_restricted"
    job_not_found = "job_not_found"
    unexpected_page = "unexpected_page"


# URL path fragments that unambiguously indicate a specific state.
_CAPTCHA_URL_FRAGMENTS = ("checkpoint/challenge", "/challenge", "captcha")
_AUTH_URL_FRAGMENTS = ("/authwall", "/login", "/uas/login", "/checkpoint/lg")

# Specific phrases. These are full, unambiguous strings that do not appear in
# ordinary job descriptions, keeping false positives out.
_CAPTCHA_PHRASES = (
    "security verification",
    "please solve this puzzle",
    "verify you are a human",
    "let's do a quick security check",
)
_AUTH_PHRASES = (
    "sign in to see",
    "join linkedin to see",
    "sign in to view more",
    "make the most of your professional life",
)
_ACCESS_RESTRICTED_PHRASES = (
    "you've reached the weekly limit",
    "you have reached the limit",
    "too many requests",
    "access to this page has been denied",
    "http error 429",
)
_JOB_NOT_FOUND_PHRASES = (
    "this job is no longer available",
    "no longer accepting applications",
    "the job you were looking for was not found",
    "this job posting has been removed",
)
_EMPTY_RESULT_PHRASES = (
    "no matching jobs found",
    "no results found",
    "we couldn't find any jobs",
    "try adjusting your search",
)


def _title_or_body_contains(title_text: str, body_text: str, phrases) -> bool:
    """Return True if any phrase appears in the title or visible body text."""
    haystack = f"{title_text}\n{body_text}"
    return any(phrase in haystack for phrase in phrases)


def detect_page_state(
    html: str,
    current_url: str,
    page_title: str | None = None,
) -> PageState:
    """Classify a fetched page using URL, title, elements, and text signals."""
    soup = BeautifulSoup(html or "", "lxml")
    body = soup.body if soup.body is not None else soup

    url = (current_url or "").lower()
    title_text = (page_title or (soup.title.get_text() if soup.title else "")).lower()
    body_text = body.get_text(separator="\n").lower()

    # 1. CAPTCHA / security challenge — highest priority.
    if (
        element_matches(soup, CAPTCHA_ELEMENTS)
        or any(fragment in url for fragment in _CAPTCHA_URL_FRAGMENTS)
        or _title_or_body_contains(title_text, body_text, _CAPTCHA_PHRASES)
    ):
        logger.warning("Detected CAPTCHA/challenge page state.")
        return PageState.captcha

    # 2. Sign-in wall / authentication required.
    if (
        element_matches(soup, SIGNIN_WALL_ELEMENTS)
        or any(fragment in url for fragment in _AUTH_URL_FRAGMENTS)
        or _title_or_body_contains(title_text, body_text, _AUTH_PHRASES)
    ):
        logger.warning("Detected authentication-required page state.")
        return PageState.authentication_required

    # 3. Rate limit / access denied.
    if (
        element_matches(soup, ACCESS_RESTRICTED_ELEMENTS)
        or _title_or_body_contains(title_text, body_text, _ACCESS_RESTRICTED_PHRASES)
    ):
        logger.warning("Detected access-restricted page state.")
        return PageState.access_restricted

    # 4. Removed / expired job.
    if (
        element_matches(soup, REMOVED_JOB_ELEMENTS)
        or _title_or_body_contains(title_text, body_text, _JOB_NOT_FOUND_PHRASES)
    ):
        logger.info("Detected removed/expired job page state.")
        return PageState.job_not_found

    # 5. Valid but empty search results.
    if (
        element_matches(soup, EMPTY_SEARCH_ELEMENTS)
        or _title_or_body_contains(title_text, body_text, _EMPTY_RESULT_PHRASES)
    ):
        logger.info("Detected empty-results page state.")
        return PageState.empty_results

    return PageState.normal
