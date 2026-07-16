"""Job search schema validation tests."""

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas.job_search import (
    DatePosted,
    EmploymentType,
    ExperienceLevel,
    JobSearchRequest,
    WorkplaceType,
)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Ensure settings cache does not leak between schema tests."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_valid_request() -> None:
    request = JobSearchRequest(
        keywords="Artificial Intelligence Intern",
        location="Karachi, Pakistan",
        experience_level=ExperienceLevel.INTERNSHIP,
        employment_type=EmploymentType.INTERNSHIP,
        workplace_type=WorkplaceType.HYBRID,
        date_posted=DatePosted.PAST_WEEK,
        easy_apply_only=False,
        max_jobs=30,
    )
    assert request.keywords == "Artificial Intelligence Intern"
    assert request.max_jobs == 30


def test_empty_keywords_rejected() -> None:
    with pytest.raises(ValidationError):
        JobSearchRequest(keywords="")


def test_whitespace_only_keywords_rejected() -> None:
    with pytest.raises(ValidationError):
        JobSearchRequest(keywords="   ")


def test_keywords_over_max_length_rejected() -> None:
    with pytest.raises(ValidationError):
        JobSearchRequest(keywords="a" * 151)


def test_invalid_experience_level_rejected() -> None:
    with pytest.raises(ValidationError):
        JobSearchRequest.model_validate(
            {"keywords": "Engineer", "experience_level": "senior"}
        )


def test_invalid_employment_type_rejected() -> None:
    with pytest.raises(ValidationError):
        JobSearchRequest.model_validate(
            {"keywords": "Engineer", "employment_type": "freelance"}
        )


def test_invalid_workplace_type_rejected() -> None:
    with pytest.raises(ValidationError):
        JobSearchRequest.model_validate(
            {"keywords": "Engineer", "workplace_type": "office"}
        )


def test_invalid_date_posted_rejected() -> None:
    with pytest.raises(ValidationError):
        JobSearchRequest.model_validate(
            {"keywords": "Engineer", "date_posted": "last_year"}
        )


def test_max_jobs_below_one_rejected() -> None:
    with pytest.raises(ValidationError):
        JobSearchRequest(keywords="Engineer", max_jobs=0)


def test_max_jobs_above_configured_maximum_rejected(monkeypatch) -> None:
    monkeypatch.setenv("MAX_JOBS_PER_SEARCH", "50")
    from app.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        JobSearchRequest(keywords="Engineer", max_jobs=51)


def test_default_max_jobs_applied(monkeypatch) -> None:
    monkeypatch.setenv("DEFAULT_MAX_JOBS", "20")
    from app.config import get_settings

    get_settings.cache_clear()

    request = JobSearchRequest(keywords="Engineer")
    assert request.max_jobs == 20


def test_keywords_trimmed() -> None:
    request = JobSearchRequest(keywords="  Python Developer  ")
    assert request.keywords == "Python Developer"


def test_cpp_keyword_preserved() -> None:
    request = JobSearchRequest(keywords="C++ Developer")
    assert request.keywords == "C++ Developer"
