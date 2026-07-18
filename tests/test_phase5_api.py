"""Phase 5 API tests: start, results, jobs, and exports.

The background execution runner is mocked, so no Playwright launches and no
network access occurs. All data lives in the isolated in-memory test database.
"""

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app.models.linkedin_job import LinkedInJob
from app.models.scraping_job import ScrapingJob
from app.models.scraping_job_result import ScrapingJobResult


def _scraping_job(db, status="pending", **kwargs) -> ScrapingJob:
    base = {"keywords": "python", "location": "Berlin", "max_jobs": 10, "status": status,
            "search_url": "https://www.linkedin.com/jobs/search/"}
    base.update(kwargs)
    job = ScrapingJob(**base)
    db.add(job)
    db.commit()
    return job


def _job(db, sj_id, rank=1, associate=True, **kwargs) -> LinkedInJob:
    n = kwargs.pop("n", rank)
    base = {
        "scraping_job_id": sj_id,
        "linkedin_job_id": f"{n}00{n}",
        "title": "Python Engineer",
        "company_name": "Acme",
        "location": "Berlin",
        "country": "Germany",
        "workplace_type": "remote",
        "employment_type": "full_time",
        "experience_level": "mid_senior",
        "salary_text": "$80,000 - $120,000 per year",
        "salary_period": "year",
        "salary_min": 80000,
        "salary_max": 120000,
        "salary_currency": "USD",
        "required_skills_json": json.dumps(["Python", "FastAPI"]),
        "applicant_count": 42,
        "easy_apply": True,
        "job_url": f"https://www.linkedin.com/jobs/view/{n}00{n}/",
        "normalized_job_url": f"https://www.linkedin.com/jobs/view/{n}00{n}/",
        "status": "complete",
    }
    base.update(kwargs)
    job = LinkedInJob(**base)
    db.add(job)
    db.commit()
    if associate:
        db.add(ScrapingJobResult(scraping_job_id=sj_id, linkedin_job_id=job.id, source_rank=rank))
        db.commit()
    return job


# --- Start endpoint ----------------------------------------------------------


def test_successful_start(client, db_session) -> None:
    sj = _scraping_job(db_session)
    with patch("app.api.scraping_jobs.run_scraping_job_sync") as mock_runner:
        resp = client.post(f"/api/scraping-jobs/{sj.id}/start")
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    assert body["scraping_job_id"] == sj.id
    assert "BackgroundTasks" in body["note"]
    # The background runner was scheduled and executed by the TestClient.
    assert mock_runner.called
    db_session.refresh(sj)
    assert sj.status == "running"


def test_start_invalid_job_id(client) -> None:
    with patch("app.api.scraping_jobs.run_scraping_job_sync"):
        resp = client.post("/api/scraping-jobs/not-a-uuid/start")
    assert resp.status_code == 400


def test_start_missing_job(client) -> None:
    import uuid
    with patch("app.api.scraping_jobs.run_scraping_job_sync"):
        resp = client.post(f"/api/scraping-jobs/{uuid.uuid4()}/start")
    assert resp.status_code == 404


def test_duplicate_start_rejected(client, db_session) -> None:
    sj = _scraping_job(db_session)
    with patch("app.api.scraping_jobs.run_scraping_job_sync"):
        first = client.post(f"/api/scraping-jobs/{sj.id}/start")
        second = client.post(f"/api/scraping-jobs/{sj.id}/start")
    assert first.status_code == 202
    assert second.status_code == 409


def test_start_completed_job_rejected(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    with patch("app.api.scraping_jobs.run_scraping_job_sync"):
        resp = client.post(f"/api/scraping-jobs/{sj.id}/start")
    assert resp.status_code == 409


def test_start_does_not_launch_playwright(client, db_session) -> None:
    # Guard: the runner must be the only path to Playwright, and it is mocked.
    sj = _scraping_job(db_session)
    with patch("app.api.scraping_jobs.run_scraping_job_sync") as mock_runner:
        client.post(f"/api/scraping-jobs/{sj.id}/start")
    # Runner invoked with the job id and settings; no real browser started.
    args = mock_runner.call_args[0]
    assert args[0] == sj.id


# --- Results endpoint --------------------------------------------------------


def test_results_pagination(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    for i in range(1, 6):
        _job(db_session, sj.id, rank=i, n=i)
    resp = client.get(f"/api/scraping-jobs/{sj.id}/results?page=1&page_size=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["total_records"] == 5
    assert body["pagination"]["total_pages"] == 3
    assert len(body["items"]) == 2
    # Ordered by discovery rank.
    assert body["items"][0]["linkedin_job_id"] == "1001"


def test_results_fields_present(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    _job(db_session, sj.id)
    resp = client.get(f"/api/scraping-jobs/{sj.id}/results")
    item = resp.json()["items"][0]
    assert item["skills"] == ["Python", "FastAPI"]
    assert item["salary_period"] == "year"
    assert item["processing_status"] == "complete"
    assert item["easy_apply"] is True


def test_results_empty(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    resp = client.get(f"/api/scraping-jobs/{sj.id}/results")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["pagination"]["total_records"] == 0


def test_results_missing_job(client) -> None:
    import uuid
    resp = client.get(f"/api/scraping-jobs/{uuid.uuid4()}/results")
    assert resp.status_code == 404


# --- Jobs API ----------------------------------------------------------------


def test_jobs_list_and_pagination(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    for i in range(1, 4):
        _job(db_session, sj.id, rank=i, n=i)
    resp = client.get("/api/jobs?page=1&page_size=2")
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total_records"] == 3
    assert len(resp.json()["items"]) == 2


def test_jobs_filter_by_company(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    _job(db_session, sj.id, rank=1, n=1, company_name="Acme")
    _job(db_session, sj.id, rank=2, n=2, company_name="Globex")
    resp = client.get("/api/jobs?company=Globex")
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["company_name"] == "Globex"


def test_jobs_filter_by_skill(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    _job(db_session, sj.id, rank=1, n=1, required_skills_json=json.dumps(["Python", "Django"]))
    _job(db_session, sj.id, rank=2, n=2, required_skills_json=json.dumps(["Java", "Spring Boot"]))
    resp = client.get("/api/jobs?skill=Django")
    items = resp.json()["items"]
    assert len(items) == 1
    assert "Django" in items[0]["skills"]


def test_jobs_filter_easy_apply(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    _job(db_session, sj.id, rank=1, n=1, easy_apply=True)
    _job(db_session, sj.id, rank=2, n=2, easy_apply=False)
    resp = client.get("/api/jobs?easy_apply=false")
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["easy_apply"] is False


def test_jobs_sort_deterministic(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    for i in range(1, 4):
        _job(db_session, sj.id, rank=i, n=i)
    a = client.get("/api/jobs?sort=oldest").json()["items"]
    b = client.get("/api/jobs?sort=oldest").json()["items"]
    assert [x["id"] for x in a] == [x["id"] for x in b]


def test_job_detail(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    job = _job(db_session, sj.id)
    resp = client.get(f"/api/jobs/{job.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job.id
    assert resp.json()["skills"] == ["Python", "FastAPI"]


def test_job_detail_missing(client) -> None:
    resp = client.get("/api/jobs/nonexistent-id")
    assert resp.status_code == 404


def test_jobs_empty(client) -> None:
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["pagination"]["total_records"] == 0


# --- Exports -----------------------------------------------------------------


def test_global_csv_export(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    _job(db_session, sj.id)
    resp = client.get("/api/export/csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    assert ".csv" in resp.headers["content-disposition"]
    lines = resp.text.strip().splitlines()
    assert lines[0].startswith("id,linkedin_job_id,title")
    assert len(lines) == 2  # header + one job
    assert "Python; FastAPI" in resp.text


def test_global_json_export(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    _job(db_session, sj.id)
    resp = client.get("/api/export/json")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    payload = json.loads(resp.text)
    assert "generated_at" in payload
    assert payload["total_jobs"] == 1
    assert len(payload["jobs"]) == 1
    assert payload["jobs"][0]["skills"] == ["Python", "FastAPI"]


def test_scraping_job_csv_export(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    _job(db_session, sj.id)
    resp = client.get(f"/api/scraping-jobs/{sj.id}/export/csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert len(resp.text.strip().splitlines()) == 2


def test_scraping_job_json_export(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    _job(db_session, sj.id)
    resp = client.get(f"/api/scraping-jobs/{sj.id}/export/json")
    assert resp.status_code == 200
    payload = json.loads(resp.text)
    assert payload["metadata"]["scraping_job_id"] == sj.id
    assert payload["total_jobs"] == 1


def test_export_empty(client) -> None:
    resp = client.get("/api/export/csv")
    assert resp.status_code == 200
    # Header only, no data rows.
    assert len(resp.text.strip().splitlines()) == 1


def test_export_filtered(client, db_session) -> None:
    sj = _scraping_job(db_session, status="completed")
    _job(db_session, sj.id, rank=1, n=1, company_name="Acme")
    _job(db_session, sj.id, rank=2, n=2, company_name="Globex")
    resp = client.get("/api/export/json?company=Acme")
    payload = json.loads(resp.text)
    assert payload["total_jobs"] == 1
    assert payload["jobs"][0]["company_name"] == "Acme"
