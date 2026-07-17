"""Tests for safe LinkedIn URL validation."""

import pytest

from app.exceptions import InvalidLinkedInUrlError
from app.utils.linkedin_url_validator import (
    is_allowed_linkedin_url,
    is_linkedin_domain_url,
    validate_linkedin_job_url,
    validate_linkedin_search_url,
)

VALID_SEARCH_URL = "https://www.linkedin.com/jobs/search/"
VALID_JOB_URL = "https://www.linkedin.com/jobs/view/1234567890/"


def test_valid_search_url() -> None:
    assert validate_linkedin_search_url(VALID_SEARCH_URL) == VALID_SEARCH_URL


def test_valid_job_url() -> None:
    assert validate_linkedin_job_url(VALID_JOB_URL) == VALID_JOB_URL


def test_search_url_without_trailing_slash_allowed() -> None:
    url = "https://www.linkedin.com/jobs/search"
    assert validate_linkedin_search_url(url) == url


def test_http_rejected() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_search_url("http://www.linkedin.com/jobs/search/")


def test_external_domain_rejected() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_search_url("https://fake-linkedin.com/jobs/search/")


def test_lookalike_domain_rejected() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_search_url("https://linkedin.com.example.org/jobs/search/")


def test_bare_linkedin_domain_rejected() -> None:
    # Host must be exactly www.linkedin.com.
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_search_url("https://linkedin.com/jobs/search/")


def test_embedded_credentials_rejected() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_search_url("https://user:pass@www.linkedin.com/jobs/search/")


def test_nonstandard_port_rejected() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_search_url("https://www.linkedin.com:8080/jobs/search/")


def test_unrelated_linkedin_path_rejected() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_search_url("https://www.linkedin.com/feed/")


def test_job_path_not_valid_as_search() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_search_url(VALID_JOB_URL)


def test_search_path_not_valid_as_job() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_job_url(VALID_SEARCH_URL)


def test_non_numeric_job_id_rejected() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_job_url("https://www.linkedin.com/jobs/view/abc/")


def test_javascript_url_rejected() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_search_url("javascript:alert(1)")


def test_file_url_rejected() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_search_url("file:///etc/passwd")


def test_data_url_rejected() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_search_url("data:text/html;base64,PHNjcmlwdD4=")


@pytest.mark.parametrize("url", ["", "   ", "not a url", "https://", "://missing"])
def test_malformed_url_rejected(url: str) -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        validate_linkedin_search_url(url)


def test_is_allowed_linkedin_url_true_for_both_types() -> None:
    assert is_allowed_linkedin_url(VALID_SEARCH_URL) is True
    assert is_allowed_linkedin_url(VALID_JOB_URL) is True


def test_is_allowed_linkedin_url_false_for_other() -> None:
    assert is_allowed_linkedin_url("https://www.linkedin.com/feed/") is False
    assert is_allowed_linkedin_url("https://evil.example.com/jobs/view/1/") is False


def test_is_linkedin_domain_url_allows_company_and_profile_paths() -> None:
    assert is_linkedin_domain_url("https://www.linkedin.com/company/acme/") is True
    assert is_linkedin_domain_url("https://www.linkedin.com/in/some-recruiter/") is True


def test_is_linkedin_domain_url_rejects_other_hosts() -> None:
    assert is_linkedin_domain_url("https://example.com/in/x/") is False
    assert is_linkedin_domain_url("http://www.linkedin.com/company/acme/") is False
