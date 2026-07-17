"""Tests for the search-results HTML parser."""

import pytest

from app.exceptions import (
    AccessRestrictedError,
    AuthenticationRequiredError,
    CaptchaDetectedError,
)
from app.services.linkedin_search_parser import parse_search_results
from tests.conftest import load_fixture

SEARCH_URL = "https://www.linkedin.com/jobs/search/"


def _parse(name: str, max_jobs: int = 25):
    return parse_search_results(load_fixture(name), SEARCH_URL, max_jobs)


def test_multiple_cards_parsed() -> None:
    result = _parse("search_results.html")
    assert len(result.jobs) == 4
    assert result.discovered_count == 4


def test_correct_fields_extracted() -> None:
    result = _parse("search_results.html")
    first = result.jobs[0]
    assert first.title == "Senior Python Engineer"
    assert first.company_name == "Acme Corp"
    assert first.location == "Remote, USA"
    assert first.job_url == "https://www.linkedin.com/jobs/view/1111111111/"
    assert first.company_url == "https://www.linkedin.com/company/acme/"
    assert first.posted_text == "2 days ago"
    assert first.easy_apply is True


def test_missing_optional_field_handled() -> None:
    result = _parse("search_results.html")
    # The C++ card intentionally omits location.
    cpp_card = next(job for job in result.jobs if job.title == "C++ Systems Programmer")
    assert cpp_card.location is None
    assert cpp_card.easy_apply is None


def test_relative_urls_converted_to_absolute() -> None:
    result = _parse("search_results.html")
    assert all(job.job_url.startswith("https://www.linkedin.com/") for job in result.jobs)


def test_job_ids_extracted() -> None:
    result = _parse("search_results.html")
    ids = [job.linkedin_job_id for job in result.jobs]
    assert ids == ["1111111111", "2222222222", "3333333333", "4444444444"]


def test_technical_terms_preserved() -> None:
    result = _parse("search_results.html")
    titles = {job.title for job in result.jobs}
    assert "C++ Systems Programmer" in titles
    assert "Backend Developer (Node.js)" in titles


def test_fallback_selectors_parsed() -> None:
    result = _parse("search_results_fallback_selectors.html")
    assert len(result.jobs) == 2
    assert result.jobs[0].title == "Machine Learning Engineer"
    assert result.jobs[0].company_name == "Stark Industries"
    assert result.jobs[1].title == ".NET Developer"
    # Job id derived from URL even without a data-job-id attribute.
    assert result.jobs[0].linkedin_job_id == "7777777777"


def test_duplicate_cards_removed() -> None:
    result = _parse("search_results_duplicate_cards.html")
    ids = [job.linkedin_job_id for job in result.jobs]
    assert ids == ["5555555555", "6666666666"]


def test_max_jobs_respected() -> None:
    result = _parse("search_results.html", max_jobs=2)
    assert len(result.jobs) == 2
    # Source order preserved: first two cards.
    assert [job.linkedin_job_id for job in result.jobs] == ["1111111111", "2222222222"]


def test_source_order_preserved() -> None:
    result = _parse("search_results.html")
    titles = [job.title for job in result.jobs]
    assert titles == [
        "Senior Python Engineer",
        "Backend Developer (Node.js)",
        "C++ Systems Programmer",
        "Data Engineer",
    ]


def test_empty_results_returns_empty_list() -> None:
    result = _parse("search_results_empty.html")
    assert result.jobs == []
    assert result.discovered_count == 0


def test_signin_wall_raises() -> None:
    with pytest.raises(AuthenticationRequiredError):
        parse_search_results(
            load_fixture("signin_wall.html"),
            "https://www.linkedin.com/authwall",
            25,
        )


def test_captcha_raises() -> None:
    with pytest.raises(CaptchaDetectedError):
        parse_search_results(
            load_fixture("captcha_page.html"),
            "https://www.linkedin.com/checkpoint/challenge/verify",
            25,
        )


def test_access_restricted_raises() -> None:
    with pytest.raises(AccessRestrictedError):
        parse_search_results(load_fixture("access_restricted.html"), SEARCH_URL, 25)


def test_malformed_and_incomplete_cards_skipped() -> None:
    # One valid card, one with no title, one with no job URL, one with an
    # off-domain URL. Only the valid card should survive.
    html = (
        '<html><body><ul>'
        '<li data-job-card><a data-test-job-link href="/jobs/view/1010101010/">'
        '<h3 data-test-job-title>Valid Role</h3></a></li>'
        '<li data-job-card><a data-test-job-link href="/jobs/view/2020202020/"></a></li>'
        '<li data-job-card><h3 data-test-job-title>No Link Role</h3></li>'
        '<li data-job-card><a data-test-job-link href="https://evil.example.com/jobs/view/3/">'
        '<h3 data-test-job-title>Evil Role</h3></a></li>'
        '</ul></body></html>'
    )
    result = parse_search_results(html, SEARCH_URL, 25)
    assert len(result.jobs) == 1
    assert result.jobs[0].title == "Valid Role"


def test_no_cards_returns_empty() -> None:
    html = "<html><body><main><p>Some unrelated content.</p></main></body></html>"
    result = parse_search_results(html, SEARCH_URL, 25)
    assert result.jobs == []
