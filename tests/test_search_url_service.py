"""LinkedIn job search URL builder tests."""

from urllib.parse import parse_qs, urlparse

import pytest

from app.schemas.job_search import (
    DatePosted,
    EmploymentType,
    ExperienceLevel,
    JobSearchRequest,
    WorkplaceType,
)
from app.services.search_url_service import build_linkedin_jobs_url


def _build(**kwargs) -> str:
    payload = {"keywords": kwargs.pop("keywords", "Engineer")}
    payload.update(kwargs)
    return build_linkedin_jobs_url(JobSearchRequest(**payload))


def test_keywords_only() -> None:
    url = _build(keywords="Python Developer")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "www.linkedin.com"
    assert parsed.path == "/jobs/search/"
    assert params["keywords"] == ["Python Developer"]
    assert "location" not in params


def test_keywords_with_location() -> None:
    url = _build(keywords="Data Scientist", location="Karachi, Pakistan")
    params = parse_qs(urlparse(url).query)

    assert params["keywords"] == ["Data Scientist"]
    assert params["location"] == ["Karachi, Pakistan"]


def test_all_filters_enabled() -> None:
    url = _build(
        keywords="AI Intern",
        location="London",
        experience_level=ExperienceLevel.INTERNSHIP,
        employment_type=EmploymentType.INTERNSHIP,
        workplace_type=WorkplaceType.HYBRID,
        date_posted=DatePosted.PAST_WEEK,
        easy_apply_only=True,
    )
    params = parse_qs(urlparse(url).query)

    assert params["f_E"] == ["1"]
    assert params["f_JT"] == ["I"]
    assert params["f_WT"] == ["3"]
    assert params["f_TPR"] == ["r604800"]
    assert params["f_AL"] == ["true"]


def test_cpp_keyword_encoding() -> None:
    url = _build(keywords="C++ Developer")
    assert "keywords=C%2B%2B+Developer" in url or "C%2B%2B" in url


def test_location_with_commas_encoded() -> None:
    url = _build(keywords="Engineer", location="Karachi, Pakistan")
    assert "Karachi%2C+Pakistan" in url


def test_empty_optional_fields_omitted() -> None:
    url = _build(keywords="Engineer")
    params = parse_qs(urlparse(url).query)

    assert set(params.keys()) == {"keywords"}


def test_any_time_date_posted_omitted() -> None:
    url = _build(keywords="Engineer", date_posted=DatePosted.ANY_TIME)
    params = parse_qs(urlparse(url).query)
    assert "f_TPR" not in params


def test_easy_apply_only_when_enabled() -> None:
    url_disabled = _build(keywords="Engineer", easy_apply_only=False)
    url_enabled = _build(keywords="Engineer", easy_apply_only=True)

    assert "f_AL" not in parse_qs(urlparse(url_disabled).query)
    assert parse_qs(urlparse(url_enabled).query)["f_AL"] == ["true"]


def test_deterministic_parameter_order() -> None:
    request = JobSearchRequest(
        keywords="Engineer",
        experience_level=ExperienceLevel.ENTRY_LEVEL,
        employment_type=EmploymentType.FULL_TIME,
        workplace_type=WorkplaceType.REMOTE,
        date_posted=DatePosted.PAST_MONTH,
        easy_apply_only=True,
    )
    url_one = build_linkedin_jobs_url(request)
    url_two = build_linkedin_jobs_url(request)
    assert url_one == url_two

    query = urlparse(url_one).query
    assert query.index("f_E=") < query.index("f_JT=")
    assert query.index("f_JT=") < query.index("f_WT=")
    assert query.index("f_WT=") < query.index("f_TPR=")
    assert query.index("f_TPR=") < query.index("f_AL=")


def test_url_uses_https_and_linkedin_domain() -> None:
    url = _build(keywords="Engineer")
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "www.linkedin.com"
