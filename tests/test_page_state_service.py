"""Tests for blocked-page and empty-result detection."""

from app.services.page_state_service import PageState, detect_page_state
from tests.conftest import load_fixture

NORMAL_URL = "https://www.linkedin.com/jobs/view/1111111111/"
SEARCH_URL = "https://www.linkedin.com/jobs/search/"


def test_normal_search_page() -> None:
    html = load_fixture("search_results.html")
    assert detect_page_state(html, SEARCH_URL) is PageState.normal


def test_empty_search_page() -> None:
    html = load_fixture("search_results_empty.html")
    assert detect_page_state(html, SEARCH_URL) is PageState.empty_results


def test_signin_wall_page() -> None:
    html = load_fixture("signin_wall.html")
    state = detect_page_state(html, "https://www.linkedin.com/authwall")
    assert state is PageState.authentication_required


def test_captcha_page() -> None:
    html = load_fixture("captcha_page.html")
    state = detect_page_state(
        html, "https://www.linkedin.com/checkpoint/challenge/verify"
    )
    assert state is PageState.captcha


def test_access_restricted_page() -> None:
    html = load_fixture("access_restricted.html")
    assert detect_page_state(html, NORMAL_URL) is PageState.access_restricted


def test_removed_job_page() -> None:
    html = load_fixture("job_not_found.html")
    assert detect_page_state(html, NORMAL_URL) is PageState.job_not_found


def test_normal_security_job_not_flagged() -> None:
    # A legitimate job whose description mentions security/login/authentication
    # must not be classified as blocked.
    html = load_fixture("normal_security_job.html")
    assert detect_page_state(html, NORMAL_URL) is PageState.normal


def test_full_job_detail_is_normal() -> None:
    html = load_fixture("job_detail.html")
    assert detect_page_state(html, NORMAL_URL) is PageState.normal
