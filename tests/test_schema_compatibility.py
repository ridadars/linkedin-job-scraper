"""Tests for fresh-schema completeness and stale-schema detection.

All tests use isolated temporary/in-memory SQLite databases; the real
development database is never touched.
"""

import sqlite3

import pytest
from sqlalchemy import create_engine, inspect

import app.database as database_module
import app.models  # noqa: F401  (register models on Base.metadata)
from app.database import Base, IncompatibleDatabaseSchemaError, _verify_schema


def _fresh_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'fresh.db'}")
    Base.metadata.create_all(engine)
    return engine


def test_fresh_database_contains_salary_period(tmp_path) -> None:
    engine = _fresh_engine(tmp_path)
    columns = {c["name"] for c in inspect(engine).get_columns("linkedin_jobs")}
    assert "salary_period" in columns
    engine.dispose()


def test_fresh_database_contains_job_fingerprint(tmp_path) -> None:
    engine = _fresh_engine(tmp_path)
    columns = {c["name"] for c in inspect(engine).get_columns("linkedin_jobs")}
    assert "job_fingerprint" in columns
    engine.dispose()


def test_fingerprint_index_exists(tmp_path) -> None:
    engine = _fresh_engine(tmp_path)
    indexed_columns = {
        tuple(idx["column_names"])
        for idx in inspect(engine).get_indexes("linkedin_jobs")
    }
    assert ("job_fingerprint",) in indexed_columns
    engine.dispose()


def test_stale_schema_reports_missing_columns_clearly(tmp_path, monkeypatch) -> None:
    stale_path = tmp_path / "stale.db"
    # A scraping_jobs table missing every later column.
    conn = sqlite3.connect(stale_path)
    conn.execute("CREATE TABLE scraping_jobs (id TEXT PRIMARY KEY, keywords TEXT)")
    conn.commit()
    conn.close()

    stale_engine = create_engine(f"sqlite:///{stale_path}")
    monkeypatch.setattr(database_module, "engine", stale_engine)

    with pytest.raises(IncompatibleDatabaseSchemaError) as exc_info:
        _verify_schema()
    message = str(exc_info.value)
    assert "scraping_jobs" in message
    assert "out of date" in message.lower()

    # The check must NOT delete the database file.
    assert stale_path.exists()
    stale_engine.dispose()


def test_fresh_database_passes_verification(tmp_path, monkeypatch) -> None:
    fresh_path = tmp_path / "ok.db"
    fresh_engine = create_engine(f"sqlite:///{fresh_path}")
    Base.metadata.create_all(fresh_engine)
    monkeypatch.setattr(database_module, "engine", fresh_engine)
    # Should not raise.
    _verify_schema()
    fresh_engine.dispose()


def test_health_and_search_endpoints_work_on_fresh_db(client) -> None:
    # The `client` fixture provides an isolated in-memory database.
    assert client.get("/api/health").status_code == 200
    resp = client.post(
        "/api/search-jobs",
        json={"keywords": "Python Developer", "location": "Karachi, Pakistan"},
    )
    assert resp.status_code == 201
    assert client.get("/api/scraping-jobs").status_code == 200
