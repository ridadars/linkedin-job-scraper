"""Tests for the individual job-detail HTML parser."""

import pytest

from app.exceptions import JobPageNotFoundError
from app.services.linkedin_job_parser import parse_job_detail
from app.services.linkedin_search_parser import parse_search_results
from tests.conftest import load_fixture

JOB_URL = "https://www.linkedin.com/jobs/view/1111111111/"
MISSING_URL = "https://www.linkedin.com/jobs/view/9999999999/"


def test_full_detail_page_parsed() -> None:
    detail = parse_job_detail(load_fixture("job_detail.html"), JOB_URL)
    assert detail.title == "Senior Python Engineer"
    assert detail.company_name == "Acme Corp"
    assert detail.company_url == "https://www.linkedin.com/company/acme/"
    assert detail.job_url == JOB_URL
    assert detail.linkedin_job_id == "1111111111"
    assert detail.location == "Remote, USA"
    assert detail.workplace_type == "Remote"
    assert detail.employment_type == "Full-time"
    assert detail.experience_level == "Mid-Senior level"
    assert detail.posted_text == "2 days ago"


def test_missing_fields_return_none() -> None:
    detail = parse_job_detail(load_fixture("job_detail_missing_fields.html"), JOB_URL)
    assert detail.title == "Junior Developer"
    assert detail.salary_text is None
    assert detail.applicant_count_text is None
    assert detail.recruiter_name is None
    assert detail.recruiter_profile_url is None
    assert detail.workplace_type is None
    assert detail.easy_apply is None


def test_description_formatting_preserved() -> None:
    detail = parse_job_detail(load_fixture("job_detail.html"), JOB_URL)
    assert detail.job_description is not None
    # Line breaks between paragraphs are preserved.
    assert "\n" in detail.job_description
    # Technical terms are not damaged.
    assert "C++" in detail.job_description
    assert "Node.js" in detail.job_description
    assert ".NET" in detail.job_description


def test_easy_apply_detected() -> None:
    detail = parse_job_detail(load_fixture("job_detail.html"), JOB_URL)
    assert detail.easy_apply is True


def test_salary_text_extracted() -> None:
    detail = parse_job_detail(load_fixture("job_detail.html"), JOB_URL)
    assert detail.salary_text == "$140,000 - $180,000 a year"


def test_applicant_text_extracted() -> None:
    detail = parse_job_detail(load_fixture("job_detail.html"), JOB_URL)
    assert detail.applicant_count_text == "Over 200 applicants"


def test_recruiter_data_extracted_when_present() -> None:
    detail = parse_job_detail(load_fixture("job_detail.html"), JOB_URL)
    assert detail.recruiter_name == "Jordan Taylor"
    assert detail.recruiter_profile_url == (
        "https://www.linkedin.com/in/jordan-taylor-recruiter/"
    )


def test_missing_recruiter_does_not_fail() -> None:
    detail = parse_job_detail(load_fixture("job_detail_missing_fields.html"), JOB_URL)
    assert detail.recruiter_name is None
    assert detail.recruiter_profile_url is None


def test_removed_job_raises() -> None:
    with pytest.raises(JobPageNotFoundError):
        parse_job_detail(load_fixture("job_not_found.html"), MISSING_URL)


def test_normal_security_job_parses() -> None:
    detail = parse_job_detail(load_fixture("normal_security_job.html"), JOB_URL)
    assert detail.title == "Security Engineer"
    assert detail.job_description is not None


def test_company_url_off_domain_rejected() -> None:
    html = (
        '<html><body>'
        '<h1 data-test-job-title>Engineer</h1>'
        '<a data-test-company-link href="https://evil.example.com/company/x/">X</a>'
        '<div data-test-job-description>Some description text.</div>'
        '</body></html>'
    )
    detail = parse_job_detail(html, JOB_URL)
    assert detail.company_url is None


def test_search_result_job_urls_are_valid_for_detail_use() -> None:
    # URLs extracted by the search parser are accepted by the detail parser.
    search = parse_search_results(load_fixture("search_results.html"), JOB_URL, 25)
    detail = parse_job_detail(load_fixture("job_detail.html"), search.jobs[0].job_url)
    assert detail.linkedin_job_id == "1111111111"
