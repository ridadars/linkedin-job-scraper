"""Tests for merging card and detail data."""

from app.schemas.parsed_job import JobCardData, JobDetailData
from app.services.job_merge_service import merge_job_data

CARD_URL = "https://www.linkedin.com/jobs/view/111/"
DETAIL_URL = "https://www.linkedin.com/jobs/view/111/"


def _card(**kwargs) -> JobCardData:
    base = {
        "linkedin_job_id": "111",
        "title": "Engineer",
        "company_name": "Acme",
        "location": "Berlin",
        "job_url": CARD_URL,
    }
    base.update(kwargs)
    return JobCardData(**base)


def test_detail_values_override_card_values() -> None:
    card = _card(title="Engineer", company_name="Acme")
    detail = JobDetailData(title="Senior Engineer", company_name="Acme Corp", job_url=DETAIL_URL)
    merged = merge_job_data(card, detail)
    assert merged["title"] == "Senior Engineer"
    assert merged["company_name"] == "Acme Corp"


def test_card_values_kept_when_detail_missing() -> None:
    card = _card(title="Engineer", location="Berlin")
    detail = JobDetailData(job_url=DETAIL_URL)  # title/location absent
    merged = merge_job_data(card, detail)
    assert merged["title"] == "Engineer"
    assert merged["location"] == "Berlin"


def test_valid_card_url_preserved_when_detail_url_absent() -> None:
    card = _card(job_url=CARD_URL)
    detail = JobDetailData()  # no url
    merged = merge_job_data(card, detail)
    assert merged["job_url"] == CARD_URL


def test_conflicting_job_ids_create_warning_and_prefer_detail() -> None:
    card = _card(linkedin_job_id="111")
    detail = JobDetailData(linkedin_job_id="999", job_url="https://www.linkedin.com/jobs/view/999/")
    merged = merge_job_data(card, detail)
    assert merged["linkedin_job_id"] == "999"
    assert any("conflict" in w.lower() for w in merged["warnings"])


def test_missing_detail_object_supported() -> None:
    card = _card()
    merged = merge_job_data(card, None)
    assert merged["title"] == "Engineer"
    assert merged["job_url"] == CARD_URL


def test_empty_optional_fields_do_not_crash() -> None:
    card = JobCardData(title="Engineer", job_url=CARD_URL)
    merged = merge_job_data(card, None)
    assert merged["company_name"] is None
    assert merged["location"] is None


def test_detail_never_overwrites_card_with_none() -> None:
    card = _card(company_name="Acme")
    detail = JobDetailData(company_name=None, job_url=DETAIL_URL)
    merged = merge_job_data(card, detail)
    assert merged["company_name"] == "Acme"
