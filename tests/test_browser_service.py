"""Tests for the async Playwright browser service.

Playwright is fully mocked; no browser binary is launched and no network
request is made.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.config import Settings
from app.exceptions import (
    BrowserLaunchError,
    InvalidLinkedInUrlError,
    NavigationTimeoutError,
)
from app.services import browser_service as browser_service_module
from app.services.browser_service import BrowserService

VALID_JOB_URL = "https://www.linkedin.com/jobs/view/1111111111/"


def _settings() -> Settings:
    return Settings(DATABASE_URL="sqlite://")


def _build_fake_playwright(page: MagicMock | None = None):
    """Build a fake async_playwright chain and its parts for assertions."""
    context = MagicMock(name="context")
    context.new_page = AsyncMock(return_value=page or _build_fake_page())
    context.close = AsyncMock()
    context.set_default_navigation_timeout = MagicMock()
    context.set_default_timeout = MagicMock()

    browser = MagicMock(name="browser")
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()

    chromium = MagicMock(name="chromium")
    chromium.launch = AsyncMock(return_value=browser)

    pw = MagicMock(name="playwright")
    pw.chromium = chromium
    pw.stop = AsyncMock()

    launcher = MagicMock(name="async_playwright")
    launcher.start = AsyncMock(return_value=pw)

    async_playwright_callable = MagicMock(return_value=launcher)
    parts = {
        "callable": async_playwright_callable,
        "pw": pw,
        "browser": browser,
        "context": context,
        "chromium": chromium,
    }
    return parts


def _build_fake_page(url: str = VALID_JOB_URL) -> MagicMock:
    page = MagicMock(name="page")
    page.goto = AsyncMock()
    page.url = url
    page.title = AsyncMock(return_value="Some Title")
    page.content = AsyncMock(return_value="<html><body>ok</body></html>")
    page.close = AsyncMock()
    page.evaluate = AsyncMock(return_value=0)
    return page


@pytest.fixture
def patched_playwright(monkeypatch):
    page = _build_fake_page()
    parts = _build_fake_playwright(page)
    monkeypatch.setattr(
        browser_service_module, "async_playwright", parts["callable"]
    )
    parts["page"] = page
    return parts


async def test_browser_starts_through_context_manager(patched_playwright) -> None:
    async with BrowserService(_settings()) as service:
        assert service is not None
        patched_playwright["chromium"].launch.assert_awaited_once()
        patched_playwright["browser"].new_context.assert_awaited_once()


async def test_browser_closes_normally(patched_playwright) -> None:
    async with BrowserService(_settings()):
        pass
    patched_playwright["context"].close.assert_awaited_once()
    patched_playwright["browser"].close.assert_awaited_once()
    patched_playwright["pw"].stop.assert_awaited_once()


async def test_browser_closes_after_exception(patched_playwright) -> None:
    with pytest.raises(RuntimeError):
        async with BrowserService(_settings()):
            raise RuntimeError("boom")
    patched_playwright["context"].close.assert_awaited_once()
    patched_playwright["browser"].close.assert_awaited_once()
    patched_playwright["pw"].stop.assert_awaited_once()


async def test_page_closes_after_navigation(patched_playwright) -> None:
    async with BrowserService(_settings()) as service:
        snapshot = await service.get_page_snapshot(VALID_JOB_URL)
    assert snapshot.final_url == VALID_JOB_URL
    assert snapshot.title == "Some Title"
    patched_playwright["page"].close.assert_awaited_once()


async def test_timeouts_applied(patched_playwright) -> None:
    settings = _settings()
    async with BrowserService(settings):
        pass
    context = patched_playwright["context"]
    context.set_default_navigation_timeout.assert_called_once_with(
        settings.navigation_timeout_seconds * 1000
    )
    context.set_default_timeout.assert_called_once_with(
        settings.page_timeout_seconds * 1000
    )


async def test_startup_failure_raises_browser_launch_error(monkeypatch) -> None:
    parts = _build_fake_playwright()
    parts["chromium"].launch = AsyncMock(side_effect=RuntimeError("no binary"))
    monkeypatch.setattr(browser_service_module, "async_playwright", parts["callable"])

    with pytest.raises(BrowserLaunchError):
        async with BrowserService(_settings()):
            pass
    # Playwright was stopped during cleanup of the partial startup.
    parts["pw"].stop.assert_awaited_once()


async def test_navigation_timeout_translated(patched_playwright) -> None:
    patched_playwright["page"].goto = AsyncMock(
        side_effect=PlaywrightTimeoutError("timeout")
    )
    async with BrowserService(_settings()) as service:
        with pytest.raises(NavigationTimeoutError):
            await service.get_page_snapshot(VALID_JOB_URL)
    # The page opened for the failed navigation was still closed.
    patched_playwright["page"].close.assert_awaited()


async def test_invalid_url_rejected_before_navigation(patched_playwright) -> None:
    async with BrowserService(_settings()) as service:
        with pytest.raises(InvalidLinkedInUrlError):
            await service.get_page_snapshot("https://evil.example.com/jobs/view/1/")
    # No page was ever opened for an invalid URL.
    patched_playwright["context"].new_page.assert_not_called()


def test_no_browser_starts_during_module_import() -> None:
    # Constructing the service must not start Playwright or a browser.
    service = BrowserService(_settings())
    assert service._playwright is None
    assert service._browser is None
    assert service._context is None
