"""Pytest configuration with isolated in-memory database."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.database import Base
from app.dependencies import get_db_session, get_settings_dependency
from app.main import app

TEST_DATABASE_URL = "sqlite://"


@pytest.fixture
def test_settings() -> Settings:
    """Return test settings with predictable limits."""
    return Settings(
        DATABASE_URL=TEST_DATABASE_URL,
        MAX_JOBS_PER_SEARCH=50,
        DEFAULT_MAX_JOBS=20,
        DUPLICATE_SEARCH_WINDOW_SECONDS=60,
    )


@pytest.fixture
def test_engine():
    """Create an isolated in-memory SQLite engine for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Provide a database session bound to the in-memory test engine."""
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session, test_settings: Settings) -> Generator[TestClient, None, None]:
    """Provide a FastAPI test client with overridden dependencies."""

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    def override_get_settings() -> Settings:
        return test_settings

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_settings_dependency] = override_get_settings

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
