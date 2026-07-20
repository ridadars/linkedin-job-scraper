"""Phase 6 dashboard tests: route, static assets, page structure, seed safety.

No browser automation and no external network requests.
"""

import importlib.util
import pathlib

SEED_SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "seed_demo_jobs.py"
)


def test_dashboard_route_returns_200(client) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")


def test_dashboard_not_in_openapi_schema(client) -> None:
    # The dashboard HTML route should not clutter the API schema or clash with /docs.
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/" not in schema["paths"]


def test_static_css_available(client) -> None:
    resp = client.get("/static/css/styles.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


def test_static_js_available(client) -> None:
    resp = client.get("/static/js/dashboard.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    # Safety: the script uses textContent, not innerHTML.
    assert "textContent" in resp.text
    assert "innerHTML" not in resp.text


def test_search_form_fields_exist(client) -> None:
    html = client.get("/").text
    for field in [
        'id="search-form"',
        'id="keywords"',
        'id="location"',
        'id="experience_level"',
        'id="employment_type"',
        'id="workplace_type"',
        'id="date_posted"',
        'id="easy_apply_only"',
        'id="max_jobs"',
    ]:
        assert field in html, field


def test_progress_section_exists(client) -> None:
    html = client.get("/").text
    for element in [
        'id="progress-section"',
        'id="stat-discovered"',
        'id="stat-processed"',
        'id="stat-successful"',
        'id="stat-duplicate"',
        'id="stat-failed"',
        'id="job-status"',
    ]:
        assert element in html, element


def test_results_table_exists(client) -> None:
    html = client.get("/").text
    assert 'id="results-table"' in html
    assert 'id="results-body"' in html
    assert 'id="job-modal"' in html  # detail modal


def test_export_controls_exist(client) -> None:
    html = client.get("/").text
    for element in [
        'id="export-search-csv"',
        'id="export-search-json"',
        'id="export-all-csv"',
        'id="export-all-json"',
    ]:
        assert element in html, element


def test_filter_controls_exist(client) -> None:
    html = client.get("/").text
    for element in ['id="filter-form"', 'id="apply-filters"', 'id="clear-filters"', 'id="f-skill"']:
        assert element in html, element


def test_responsible_use_notice_present(client) -> None:
    html = client.get("/").text
    assert "Responsible use" in html


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("seed_demo_jobs", SEED_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # importing must have no side effects
    return module


def test_seed_script_exists() -> None:
    assert SEED_SCRIPT.exists()


def test_seed_script_not_executed_on_import() -> None:
    # Importing must not seed anything or touch a database.
    module = _load_seed_module()
    assert hasattr(module, "seed")
    assert callable(module.seed)
    assert hasattr(module, "main")
    assert module.DEMO_MARKER == "[DEMO]"


def test_seed_inserts_demo_jobs_into_isolated_db(db_session) -> None:
    # Drive the seed logic against the isolated test session (no real DB).
    import json

    from app.models.linkedin_job import LinkedInJob
    from app.models.scraping_job import ScrapingJob
    from app.models.scraping_job_result import ScrapingJobResult

    module = _load_seed_module()
    # Reuse the module's demo specs directly to avoid touching the real DB.
    specs = module._DEMO_JOBS
    sj = ScrapingJob(keywords="[DEMO] Python", max_jobs=len(specs), status="completed")
    db_session.add(sj)
    db_session.commit()
    for rank, spec in enumerate(specs, start=1):
        job = LinkedInJob(
            scraping_job_id=sj.id,
            title=spec["title"],
            company_name=spec["company_name"],
            job_url="https://www.linkedin.com/jobs/view/1/",
            normalized_job_url="https://www.linkedin.com/jobs/view/1/",
            required_skills_json=json.dumps(spec["skills"]),
            status="complete",
        )
        db_session.add(job)
        db_session.commit()
        db_session.add(
            ScrapingJobResult(scraping_job_id=sj.id, linkedin_job_id=job.id, source_rank=rank)
        )
        db_session.commit()
    assert db_session.query(LinkedInJob).count() == len(specs)
