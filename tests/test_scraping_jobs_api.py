"""Scraping jobs API endpoint tests."""

import uuid

from app.models.enums import ScrapingJobStatus


def _valid_payload(**overrides) -> dict:
    payload = {
        "keywords": "Artificial Intelligence Intern",
        "location": "Karachi, Pakistan",
        "experience_level": "internship",
        "employment_type": "internship",
        "workplace_type": "hybrid",
        "date_posted": "past_week",
        "easy_apply_only": False,
        "max_jobs": 30,
    }
    payload.update(overrides)
    return payload


def test_search_jobs_returns_201(client) -> None:
    response = client.post("/api/search-jobs", json=_valid_payload())
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "pending"
    assert data["message"] == "The LinkedIn job search was created successfully."
    assert data["search_url"].startswith("https://www.linkedin.com/jobs/search/")
    uuid.UUID(data["scraping_job_id"])


def test_invalid_request_returns_422(client) -> None:
    response = client.post("/api/search-jobs", json={"keywords": ""})
    assert response.status_code == 422


def test_list_scraping_jobs_pagination(client) -> None:
    client.post("/api/search-jobs", json=_valid_payload(keywords="Search One"))
    client.post("/api/search-jobs", json=_valid_payload(keywords="Search Two"))

    response = client.get("/api/scraping-jobs?page=1&page_size=1")
    assert response.status_code == 200

    data = response.json()
    assert data["pagination"]["total_records"] == 2
    assert data["pagination"]["total_pages"] == 2
    assert len(data["items"]) == 1


def test_get_scraping_job_by_id(client) -> None:
    create_response = client.post("/api/search-jobs", json=_valid_payload())
    job_id = create_response.json()["scraping_job_id"]

    response = client.get(f"/api/scraping-jobs/{job_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == job_id
    assert data["keywords"] == "Artificial Intelligence Intern"
    assert data["search_url"].startswith("https://www.linkedin.com/jobs/search/")


def test_missing_job_returns_404(client) -> None:
    missing_id = str(uuid.uuid4())
    response = client.get(f"/api/scraping-jobs/{missing_id}")
    assert response.status_code == 404


def test_invalid_uuid_returns_400(client) -> None:
    response = client.get("/api/scraping-jobs/not-a-valid-uuid")
    assert response.status_code == 400


def test_duplicate_recent_request_reuses_job(client) -> None:
    first = client.post("/api/search-jobs", json=_valid_payload())
    second = client.post("/api/search-jobs", json=_valid_payload())

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["scraping_job_id"] == second.json()["scraping_job_id"]
    assert second.json()["reused_existing"] is True


def test_health_endpoint_still_works(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}
