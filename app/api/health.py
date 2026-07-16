"""Health check API endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db_session, get_settings_dependency

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str
    app_name: str
    timestamp: datetime
    database: str


@router.get("/health", response_model=HealthResponse)
def health_check(
    settings: Settings = Depends(get_settings_dependency),
    db: Session = Depends(get_db_session),
) -> HealthResponse:
    """Return application and database health status."""
    database_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "disconnected"

    return HealthResponse(
        status="ok" if database_status == "connected" else "degraded",
        app_name=settings.app_name,
        timestamp=datetime.now(UTC),
        database=database_status,
    )
