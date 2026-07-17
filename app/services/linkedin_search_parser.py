"""Search-results HTML parser.

Turns a LinkedIn job-search results page into a :class:`SearchPageResult`.
Blocked pages raise the appropriate structured exception; a valid page with no
results returns an empty list. Each card is parsed independently so one broken
card cannot fail the whole page. Duplicates within the page are removed.
"""

import logging

from bs4 import BeautifulSoup, Tag

from app.exceptions import (
    AccessRestrictedError,
    AuthenticationRequiredError,
    CaptchaDetectedError,
)
from app.linkedin_selectors import (
    COMPANY_NAME,
    COMPANY_URL,
    EASY_APPLY,
    JOB_ID_ATTRIBUTES,
    JOB_ID_CONTAINERS,
    JOB_TITLE,
    JOB_URL,
    LOCATION,
    POSTED_DATE,
    SEARCH_JOB_CARDS,
)
from app.schemas.parsed_job import JobCardData, SearchPageResult
from app.services.page_state_service import PageState, detect_page_state
from app.utils.html_parser import (
    element_matches,
    extract_linkedin_job_id,
    first_attribute,
    first_text,
    normalize_linkedin_url,
)
from app.utils.linkedin_url_validator import is_allowed_linkedin_url

logger = logging.getLogger(__name__)


def _find_cards(soup: BeautifulSoup) -> list[Tag]:
    """Return job-card elements using the first selector group that matches."""
    for selector in SEARCH_JOB_CARDS:
        cards = soup.select(selector)
        if cards:
            return cards
    return []


def _extract_job_id(card: Tag, job_url: str | None) -> str | None:
    """Extract the numeric job id from the URL or a card data attribute."""
    raw_id: str | None = None
    for selector in JOB_ID_CONTAINERS:
        element = card.select_one(selector)
        if element is None:
            continue
        for attribute in JOB_ID_ATTRIBUTES:
            value = element.get(attribute)
            if value:
                raw_id = value if isinstance(value, str) else " ".join(value)
                break
        if raw_id:
            break
    return extract_linkedin_job_id(job_url, raw_id)


def _parse_card(card: Tag) -> JobCardData | None:
    """Parse a single card, returning None if it lacks a title and job URL."""
    title = first_text(card, JOB_TITLE)
    raw_job_url = first_attribute(card, JOB_URL, "href")
    job_url = normalize_linkedin_url(raw_job_url)

    # A useful card needs both a title and a valid LinkedIn job URL.
    if not title or not job_url or not is_allowed_linkedin_url(job_url):
        return None

    raw_company_url = first_attribute(card, COMPANY_URL, "href")

    return JobCardData(
        linkedin_job_id=_extract_job_id(card, job_url),
        title=title,
        company_name=first_text(card, COMPANY_NAME),
        location=first_text(card, LOCATION),
        job_url=job_url,
        company_url=normalize_linkedin_url(raw_company_url),
        posted_text=first_text(card, POSTED_DATE),
        easy_apply=True if element_matches(card, EASY_APPLY) else None,
    )


def _dedupe_key(job: JobCardData) -> str:
    """Build a stable duplicate key by priority: id > url > title/company/loc."""
    if job.linkedin_job_id:
        return f"id:{job.linkedin_job_id}"
    if job.job_url:
        return f"url:{job.job_url.lower()}"
    parts = [
        (job.title or "").lower(),
        (job.company_name or "").lower(),
        (job.location or "").lower(),
    ]
    return "combo:" + "|".join(parts)


def parse_search_results(
    html: str,
    current_url: str,
    max_jobs: int,
) -> SearchPageResult:
    """Parse a search-results page into a :class:`SearchPageResult`."""
    state = detect_page_state(html, current_url)

    if state is PageState.captcha:
        raise CaptchaDetectedError()
    if state is PageState.authentication_required:
        raise AuthenticationRequiredError()
    if state is PageState.access_restricted:
        raise AccessRestrictedError()
    if state is PageState.empty_results:
        logger.info("Search page reported empty results.")
        return SearchPageResult(jobs=[], discovered_count=0, page_state=state)

    soup = BeautifulSoup(html or "", "lxml")
    cards = _find_cards(soup)

    jobs: list[JobCardData] = []
    seen_keys: set[str] = set()
    skipped = 0

    for card in cards:
        if max_jobs > 0 and len(jobs) >= max_jobs:
            break
        try:
            job = _parse_card(card)
        except Exception:  # never let one malformed card break the page
            skipped += 1
            logger.warning("Skipped a malformed job card.")
            continue

        if job is None:
            skipped += 1
            continue

        key = _dedupe_key(job)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        jobs.append(job)

    logger.info(
        "Parsed %d job card(s); skipped %d; page_state=%s.",
        len(jobs),
        skipped,
        state.value,
    )

    return SearchPageResult(
        jobs=jobs,
        discovered_count=len(jobs),
        page_state=state,
    )
