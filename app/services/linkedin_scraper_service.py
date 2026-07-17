"""High-level LinkedIn scraping orchestration.

``LinkedInScraperService`` ties the browser and parsers together. It validates
URLs, fetches a page snapshot through :class:`BrowserService`, re-validates the
final redirected URL, and hands the HTML to the correct parser.

It deliberately does **not**: touch the database, modify ``ScrapingJob``, expose
API endpoints, or run concurrently. Pages are processed one at a time.

Retry policy: only transient navigation errors are retried, with limited
exponential backoff bounded by ``MAX_RETRIES``. Blocked pages (CAPTCHA, sign-in
wall, access restriction), invalid URLs, and removed jobs are never retried.
"""

import asyncio
import logging

from app.exceptions import (
    AccessRestrictedError,
    AuthenticationRequiredError,
    CaptchaDetectedError,
    InvalidLinkedInUrlError,
    JobPageNotFoundError,
    NavigationError,
)
from app.schemas.parsed_job import JobDetailData, SearchPageResult
from app.services.browser_service import BrowserService
from app.services.linkedin_job_parser import parse_job_detail
from app.services.linkedin_search_parser import parse_search_results
from app.utils.linkedin_url_validator import (
    validate_linkedin_job_url,
    validate_linkedin_search_url,
)

logger = logging.getLogger(__name__)

# Errors that must never be retried.
_NON_RETRYABLE = (
    CaptchaDetectedError,
    AuthenticationRequiredError,
    AccessRestrictedError,
    JobPageNotFoundError,
    InvalidLinkedInUrlError,
)


class LinkedInScraperService:
    """Coordinate browser navigation and HTML parsing for a scraping session."""

    def __init__(self, browser_service: BrowserService, settings) -> None:
        self._browser = browser_service
        self._settings = settings

    async def collect_search_results(
        self,
        search_url: str,
        max_jobs: int,
    ) -> SearchPageResult:
        """Fetch and parse a LinkedIn job-search results page."""
        validated_url = validate_linkedin_search_url(search_url)

        async def _run() -> SearchPageResult:
            snapshot = await self._browser.get_page_snapshot(validated_url, scroll=True)
            final_url = validate_linkedin_search_url(snapshot.final_url)
            return parse_search_results(snapshot.html, final_url, max_jobs)

        return await self._with_retries(_run, context="search results")

    async def collect_job_detail(self, job_url: str) -> JobDetailData:
        """Fetch and parse an individual LinkedIn job-detail page."""
        validated_url = validate_linkedin_job_url(job_url)

        async def _run() -> JobDetailData:
            snapshot = await self._browser.get_page_snapshot(validated_url)
            final_url = validate_linkedin_job_url(snapshot.final_url)
            return parse_job_detail(snapshot.html, final_url)

        return await self._with_retries(_run, context="job detail")

    async def _with_retries(self, operation, context: str):
        """Run ``operation`` retrying only transient navigation errors."""
        max_retries = self._settings.max_retries
        attempt = 0

        while True:
            try:
                return await operation()
            except _NON_RETRYABLE:
                # Blocked pages, invalid URLs, and removed jobs are terminal.
                raise
            except NavigationError as exc:
                if attempt >= max_retries:
                    logger.warning(
                        "Giving up on %s after %d retr%s.",
                        context,
                        attempt,
                        "y" if attempt == 1 else "ies",
                    )
                    raise
                delay = self._settings.request_delay_seconds * (2**attempt)
                attempt += 1
                logger.info(
                    "Transient navigation error on %s; retry %d/%d after %.1fs.",
                    context,
                    attempt,
                    max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
