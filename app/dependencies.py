"""FastAPI dependency injection helpers."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db


def get_settings_dependency() -> Settings:
    """Provide application settings to route handlers."""
    return get_settings()


def get_db_session() -> Generator[Session, None, None]:
    """Provide a database session to route handlers."""
    yield from get_db()
