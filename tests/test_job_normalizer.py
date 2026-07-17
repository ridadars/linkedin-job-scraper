"""Tests for job field normalization."""

import pytest

from app.exceptions import InvalidLinkedInUrlError
from app.utils.job_normalizer import (
    infer_country,
    normalize_company_name,
    normalize_employment_type,
    normalize_experience_level,
    normalize_job_title,
    normalize_job_url,
    normalize_location,
    normalize_workplace_type,
)


def test_extra_spaces_removed() -> None:
    assert normalize_job_title("  Senior   Engineer  ") == "Senior Engineer"
    assert normalize_company_name("Acme   Corp") == "Acme Corp"
    assert normalize_location("  Berlin,   Germany ") == "Berlin, Germany"


def test_meaningful_punctuation_preserved() -> None:
    assert normalize_job_title("C++ Developer") == "C++ Developer"
    assert normalize_job_title("C# Engineer") == "C# Engineer"
    assert normalize_job_title(".NET Developer") == ".NET Developer"
    assert normalize_job_title("Node.js Engineer") == "Node.js Engineer"


def test_empty_values_return_none() -> None:
    assert normalize_job_title("   ") is None
    assert normalize_location(None) is None


def test_url_tracking_parameters_removed() -> None:
    url = "https://www.linkedin.com/jobs/view/12345/?refId=abc&trackingId=xyz"
    assert normalize_job_url(url) == "https://www.linkedin.com/jobs/view/12345/"


def test_invalid_linkedin_url_rejected() -> None:
    with pytest.raises(InvalidLinkedInUrlError):
        normalize_job_url("https://www.linkedin.com/feed/")
    with pytest.raises(InvalidLinkedInUrlError):
        normalize_job_url("https://evil.example.com/jobs/view/1/")


def test_workplace_type_normalized() -> None:
    assert normalize_workplace_type("Remote") == "remote"
    assert normalize_workplace_type("On-site") == "onsite"
    assert normalize_workplace_type("Hybrid") == "hybrid"
    assert normalize_workplace_type("Something") is None


def test_employment_type_normalized() -> None:
    assert normalize_employment_type("Full-time") == "full_time"
    assert normalize_employment_type("Part time") == "part_time"
    assert normalize_employment_type("Contract") == "contract"
    assert normalize_employment_type("Unknown") is None


def test_experience_level_normalized() -> None:
    assert normalize_experience_level("Mid-Senior level") == "mid_senior"
    assert normalize_experience_level("Entry level") == "entry_level"
    assert normalize_experience_level("Director") == "director"
    assert normalize_experience_level("Wizard") is None


def test_country_inferred_from_pakistani_cities() -> None:
    assert infer_country("Karachi, Pakistan") == "Pakistan"
    assert infer_country("Lahore") == "Pakistan"
    assert infer_country("Islamabad, Pakistan") == "Pakistan"
    assert infer_country("Pakistan") == "Pakistan"


def test_unknown_country_returns_none() -> None:
    assert infer_country("Paris, France") is None
    assert infer_country("Remote") is None
    assert infer_country(None) is None
