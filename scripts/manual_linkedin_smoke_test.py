"""Optional MANUAL live smoke test for the LinkedIn scraper.

This utility is intentionally **not** part of the application or the automated
test suite. It is never imported by ``app`` and never runs during ``pytest``.
Running it makes a real network request to LinkedIn, so it requires an explicit
command-line invocation and a manually installed Chromium browser.

Usage::

    playwright install chromium   # one-time, manual
    python scripts/manual_linkedin_smoke_test.py \\
        --search-url "https://www.linkedin.com/jobs/search/?keywords=Python&location=Pakistan" \\
        --max-jobs 1

Responsible use: this only reads publicly available job listings. It never logs
in, stores cookies/credentials, solves or bypasses CAPTCHAs, rotates proxies, or
spoofs fingerprints. It stops immediately on a CAPTCHA, sign-in wall, or access
restriction, and it never writes to the application database. It prints only a
short, safe summary — never full HTML.
"""

import argparse
import asyncio
import pathlib
import sys

# Ensure the project root is importable when run as `python scripts/...`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Hard cap: this manual tool must never fetch more than a handful of jobs.
_MAX_ALLOWED_JOBS = 3


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual, opt-in live smoke test for the LinkedIn scraper.",
    )
    parser.add_argument(
        "--search-url",
        required=True,
        help="A LinkedIn jobs search URL (https://www.linkedin.com/jobs/search/...).",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=1,
        help=f"Max job cards to summarize (1-{_MAX_ALLOWED_JOBS}).",
    )
    parser.add_argument(
        "--i-understand-this-makes-a-live-request",
        action="store_true",
        dest="confirmed",
        help="Required acknowledgement flag to actually perform the live request.",
    )
    return parser.parse_args(argv)


def _print_responsible_use_warning() -> None:
    print("=" * 70)
    print("RESPONSIBLE-USE WARNING")
    print("-" * 70)
    print(
        "This will make a REAL request to LinkedIn and read only publicly\n"
        "available job listings. It will NOT log in, store credentials/cookies,\n"
        "solve/bypass CAPTCHAs, rotate proxies, or spoof fingerprints. It stops\n"
        "immediately on any blocked page and never writes to the database.\n"
        "Only use this on URLs you are authorized to access."
    )
    print("=" * 70)


async def _run(search_url: str, max_jobs: int) -> int:
    # Imports are deferred so that merely importing this module has no side
    # effects and does not require Playwright/Chromium to be installed.
    from app.config import get_settings
    from app.exceptions import (
        AccessRestrictedError,
        AuthenticationRequiredError,
        CaptchaDetectedError,
        InvalidLinkedInUrlError,
    )
    from app.services.browser_service import BrowserService
    from app.services.linkedin_scraper_service import LinkedInScraperService
    from app.utils.linkedin_url_validator import validate_linkedin_search_url

    try:
        validate_linkedin_search_url(search_url)
    except InvalidLinkedInUrlError as exc:
        print(f"Refusing to navigate: {exc}")
        return 2

    settings = get_settings()
    print(f"Navigating to approved search URL (max_jobs={max_jobs})...")

    try:
        async with BrowserService(settings) as browser:
            scraper = LinkedInScraperService(browser, settings)
            result = await scraper.collect_search_results(search_url, max_jobs)
    except CaptchaDetectedError:
        print("STOP: CAPTCHA/challenge detected. Not retrying, not bypassing.")
        return 3
    except AuthenticationRequiredError:
        print("STOP: sign-in wall detected. Not logging in, not retrying.")
        return 3
    except AccessRestrictedError:
        print("STOP: access restricted / rate limited. Not retrying.")
        return 3

    print("-" * 70)
    print(f"Page state:   {result.page_state.value}")
    print(f"Cards found:  {len(result.jobs)}")
    for index, card in enumerate(result.jobs[:max_jobs], start=1):
        print(f"  [{index}] title:    {card.title}")
        print(f"      company:  {card.company_name}")
        print(f"      location: {card.location}")
        print(f"      job_url:  {card.job_url}")
    print("-" * 70)
    print("Done. No data was persisted.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code; performs no work on import."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    max_jobs = max(1, min(args.max_jobs, _MAX_ALLOWED_JOBS))

    _print_responsible_use_warning()
    if not args.confirmed:
        print(
            "\nAborted: pass --i-understand-this-makes-a-live-request to proceed."
        )
        return 1

    return asyncio.run(_run(args.search_url, max_jobs))


if __name__ == "__main__":
    raise SystemExit(main())
