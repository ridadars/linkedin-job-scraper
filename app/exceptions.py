"""Structured exceptions for the LinkedIn scraper.

Exception messages must never contain complete HTML, credentials, cookies,
or sensitive browser state. Keep messages short and safe to log.
"""


class LinkedInScraperError(Exception):
    """Base scraper exception.

    Every scraper-specific error inherits from this so callers can catch the
    whole family with a single ``except`` clause. A stable ``code`` is exposed
    for structured logging and future API error mapping.
    """

    code: str = "scraper_error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.__class__.__doc__ or self.code)


class InvalidLinkedInUrlError(LinkedInScraperError):
    """The supplied URL is not a permitted LinkedIn URL."""

    code = "invalid_linkedin_url"


class BrowserLaunchError(LinkedInScraperError):
    """The Playwright browser could not be launched."""

    code = "browser_launch_failed"


class NavigationError(LinkedInScraperError):
    """Navigation to a page failed for a non-timeout reason."""

    code = "navigation_failed"


class NavigationTimeoutError(NavigationError):
    """Navigation exceeded the configured timeout."""

    code = "navigation_timeout"


class AccessRestrictedError(LinkedInScraperError):
    """LinkedIn returned a rate-limit or access-denied page."""

    code = "access_restricted"


class CaptchaDetectedError(LinkedInScraperError):
    """A CAPTCHA or security challenge page was detected."""

    code = "captcha_detected"


class AuthenticationRequiredError(LinkedInScraperError):
    """A LinkedIn sign-in wall was detected."""

    code = "authentication_required"


class JobPageNotFoundError(LinkedInScraperError):
    """The requested job posting was removed, expired, or not found."""

    code = "job_not_found"


class ParsingError(LinkedInScraperError):
    """HTML could not be parsed into structured data."""

    code = "parsing_error"
