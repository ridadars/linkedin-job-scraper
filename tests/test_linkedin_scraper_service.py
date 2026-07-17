"""Tests for the LinkedIn scraper orchestration service.

The browser is a mock returning canned page snapshots; no network access or
real Playwright browser is involved. No database models are touched.
"""

from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.exceptions import (
    AccessRestrictedError,
    AuthenticationRequiredError,
    CaptchaDetectedError,
    InvalidLinkedInUrlError,
    NavigationError,
    NavigationTimeoutError,
)
from app.schemas.parsed_job import JobDetailData, SearchPageResult
from app.services.browser_service import PageSnapshot
from app.services.linkedin_scraper_service import LinkedInScraperService
from tests.conftest import load_fixture

SEARCH_URL = "https://www.linkedin.com/jobs/search/"
JOB_URL = "https://www.linkedin.com/jobs/view/1111111111/"


def _settings(max_retries: int = 0) -> Settings:
    return Settings(
        DATABASE_URL="sqlite://",
        MAX_RETRIES=max_retries,
        REQUEST_DELAY_SECONDS=0,
    )


def _browser_returning(html: str, final_url: str) -> AsyncMock:
    browser = AsyncMock()
    browser.get_page_snapshot = AsyncMock(
        return_value=PageSnapshot(final_url=final_url, title="T", html=html)
    )
    return browser


def _browser_raising(exc: Exception) -> AsyncMock:
    browser = AsyncMock()
    browser.get_page_snapshot = AsyncMock(side_effect=exc)
    return browser


async def test_search_url_validated_before_navigation() -> None:
    browser = AsyncMock()
    service = LinkedInScraperService(browser, _settings())
    with pytest.raises(InvalidLinkedInUrlError):
        await service.collect_search_results("https://www.linkedin.com/feed/", 10)
    browser.get_page_snapshot.assert_not_called()


async def test_job_url_validated_before_navigation() -> None:
    browser = AsyncMock()
    service = LinkedInScraperService(browser, _settings())
    with pytest.raises(InvalidLinkedInUrlError):
        await service.collect_job_detail("https://evil.example.com/jobs/view/1/")
    browser.get_page_snapshot.assert_not_called()


async def test_html_sent_to_search_parser() -> None:
    browser = _browser_returning(load_fixture("search_results.html"), SEARCH_URL)
    service = LinkedInScraperService(browser, _settings())
    result = await service.collect_search_results(SEARCH_URL, 10)
    assert isinstance(result, SearchPageResult)
    assert len(result.jobs) == 4


async def test_html_sent_to_job_parser() -> None:
    browser = _browser_returning(load_fixture("job_detail.html"), JOB_URL)
    service = LinkedInScraperService(browser, _settings())
    result = await service.collect_job_detail(JOB_URL)
    assert isinstance(result, JobDetailData)
    assert result.title == "Senior Python Engineer"


async def test_final_redirect_url_validated() -> None:
    # Snapshot redirects to a non-search LinkedIn page: must be rejected.
    browser = _browser_returning(
        load_fixture("search_results.html"),
        "https://www.linkedin.com/feed/",
    )
    service = LinkedInScraperService(browser, _settings())
    with pytest.raises(InvalidLinkedInUrlError):
        await service.collect_search_results(SEARCH_URL, 10)


async def test_navigation_timeout_translated() -> None:
    browser = _browser_raising(NavigationTimeoutError("timeout"))
    service = LinkedInScraperService(browser, _settings(max_retries=0))
    with pytest.raises(NavigationTimeoutError):
        await service.collect_search_results(SEARCH_URL, 10)
    assert browser.get_page_snapshot.call_count == 1


async def test_captcha_not_retried() -> None:
    browser = _browser_returning(load_fixture("captcha_page.html"), SEARCH_URL)
    service = LinkedInScraperService(browser, _settings(max_retries=3))
    with pytest.raises(CaptchaDetectedError):
        await service.collect_search_results(SEARCH_URL, 10)
    assert browser.get_page_snapshot.call_count == 1


async def test_authentication_wall_not_retried() -> None:
    browser = _browser_returning(load_fixture("signin_wall.html"), SEARCH_URL)
    service = LinkedInScraperService(browser, _settings(max_retries=3))
    with pytest.raises(AuthenticationRequiredError):
        await service.collect_search_results(SEARCH_URL, 10)
    assert browser.get_page_snapshot.call_count == 1


async def test_access_restriction_not_retried() -> None:
    browser = _browser_returning(load_fixture("access_restricted.html"), SEARCH_URL)
    service = LinkedInScraperService(browser, _settings(max_retries=3))
    with pytest.raises(AccessRestrictedError):
        await service.collect_search_results(SEARCH_URL, 10)
    assert browser.get_page_snapshot.call_count == 1


async def test_temporary_errors_respect_retry_limit() -> None:
    browser = _browser_raising(NavigationError("temporary"))
    service = LinkedInScraperService(browser, _settings(max_retries=2))
    with pytest.raises(NavigationError):
        await service.collect_search_results(SEARCH_URL, 10)
    # Initial attempt plus two retries.
    assert browser.get_page_snapshot.call_count == 3


async def test_no_database_models_returned() -> None:
    browser = _browser_returning(load_fixture("job_detail.html"), JOB_URL)
    service = LinkedInScraperService(browser, _settings())
    result = await service.collect_job_detail(JOB_URL)
    # Parsers return plain Pydantic models, never SQLAlchemy instances.
    assert not hasattr(result, "__table__")
    assert not hasattr(result, "_sa_instance_state")
