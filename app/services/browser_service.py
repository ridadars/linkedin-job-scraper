"""Asynchronous Playwright browser management.

``BrowserService`` is an async context manager that owns the full Playwright
lifecycle: it starts Playwright, launches a Chromium browser, and creates an
isolated, non-persistent context on ``__aenter__`` and tears everything down on
``__aexit__`` — even after a partial startup failure or an exception in the
body.

Design rules enforced here:

* Nothing starts at import time; the browser starts only inside the context.
* No cookies, sessions, or persistent profiles are stored.
* No automatic LinkedIn login is ever attempted.
* URLs are validated before navigation and again after redirects.
* Playwright launch failures become :class:`BrowserLaunchError`; navigation
  timeouts become :class:`NavigationTimeoutError`.
"""

import logging
from dataclasses import dataclass

from playwright.async_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from app.exceptions import (
    BrowserLaunchError,
    InvalidLinkedInUrlError,
    NavigationError,
    NavigationTimeoutError,
)
from app.utils.linkedin_url_validator import is_allowed_linkedin_url

logger = logging.getLogger(__name__)


@dataclass
class PageSnapshot:
    """A read-only snapshot of a fetched page."""

    final_url: str
    title: str
    html: str


class BrowserService:
    """Owns the async Playwright browser lifecycle for a single session."""

    def __init__(self, settings) -> None:
        self._settings = settings
        self._playwright = None
        self._browser = None
        self._context = None

    async def __aenter__(self) -> "BrowserService":
        """Start Playwright, launch Chromium, and create an isolated context."""
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._settings.headless,
            )
            # Non-persistent context: nothing is written to disk, no reused
            # cookies or storage between sessions.
            self._context = await self._browser.new_context()
            self._apply_timeouts(self._context)
            logger.info(
                "Browser launched (chromium, headless=%s).",
                self._settings.headless,
            )
            return self
        except (PlaywrightError, Exception) as exc:
            # Clean up whatever partially started before re-raising.
            await self._safe_shutdown()
            logger.error("Browser launch failed.")
            raise BrowserLaunchError("Failed to launch the browser.") from exc

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        """Tear down the browser stack safely regardless of body outcome."""
        await self._safe_shutdown()
        logger.info("Browser closed.")

    def _apply_timeouts(self, context) -> None:
        """Apply configured navigation and default timeouts (milliseconds)."""
        context.set_default_navigation_timeout(
            self._settings.navigation_timeout_seconds * 1000
        )
        context.set_default_timeout(self._settings.page_timeout_seconds * 1000)

    async def open_page(self, url: str):
        """Validate ``url``, navigate to it, and return the Playwright page.

        The caller is responsible for closing the returned page, or use
        :meth:`get_page_snapshot` which manages the page lifecycle.
        """
        if self._context is None:
            raise BrowserLaunchError("Browser context is not started.")

        if not is_allowed_linkedin_url(url):
            raise InvalidLinkedInUrlError("Refusing to navigate to a non-LinkedIn URL.")

        page = await self._context.new_page()
        try:
            logger.info("Navigating to approved URL.")
            await page.goto(url, wait_until="domcontentloaded")
        except PlaywrightTimeoutError as exc:
            await self._safe_close_page(page)
            logger.warning("Navigation timed out.")
            raise NavigationTimeoutError("Navigation timed out.") from exc
        except PlaywrightError as exc:
            await self._safe_close_page(page)
            logger.warning("Navigation failed.")
            raise NavigationError("Navigation failed.") from exc
        return page

    async def get_page_snapshot(self, url: str, scroll: bool = False) -> PageSnapshot:
        """Navigate to ``url`` and return a validated :class:`PageSnapshot`.

        When ``scroll`` is True, limited controlled scrolling is performed to
        load lazily-rendered job cards before the snapshot is captured.
        """
        page = await self.open_page(url)
        try:
            final_url = page.url
            # Validate the URL after any redirects; reject unsupported targets.
            if not is_allowed_linkedin_url(final_url):
                raise InvalidLinkedInUrlError(
                    "Redirected to a URL outside the allowed LinkedIn scope."
                )
            if scroll:
                await self._controlled_scroll(page)
            title = await page.title()
            html = await page.content()
            logger.info("Captured page snapshot from approved final URL.")
            return PageSnapshot(final_url=final_url, title=title, html=html)
        finally:
            await self._safe_close_page(page)

    async def _controlled_scroll(self, page) -> None:
        """Scroll down a bounded number of times to load more job cards.

        This never clicks any control (no CAPTCHA/login/verification buttons),
        never refreshes, and stops early when the page height stops growing.
        """
        import asyncio

        max_attempts = self._settings.max_scroll_attempts
        wait_seconds = self._settings.scroll_wait_seconds
        previous_height = 0

        for attempt in range(max_attempts):
            try:
                height = await page.evaluate("document.body.scrollHeight")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except PlaywrightError:
                logger.debug("Scroll evaluation failed; stopping scroll.")
                return

            if height <= previous_height:
                logger.debug("No new content after scroll; stopping.")
                return
            previous_height = height

            await asyncio.sleep(wait_seconds)
            logger.debug("Completed scroll attempt %d.", attempt + 1)

    async def _safe_close_page(self, page) -> None:
        """Close a page, swallowing any teardown error."""
        try:
            await page.close()
        except Exception:  # teardown must not raise
            logger.debug("Ignoring error while closing page.")

    async def _safe_shutdown(self) -> None:
        """Close context, browser, and Playwright, tolerating partial state."""
        for closer, target in (
            ("context", self._context),
            ("browser", self._browser),
        ):
            if target is not None:
                try:
                    await target.close()
                except Exception:
                    logger.debug("Ignoring error while closing %s.", closer)

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                logger.debug("Ignoring error while stopping Playwright.")

        self._context = None
        self._browser = None
        self._playwright = None
