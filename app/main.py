"""FastAPI application factory and lifecycle hooks."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.jobs import export_router, jobs_router
from app.api.scraping_jobs import scraping_jobs_router, search_router
from app.config import get_settings
from app.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize resources on startup and clean up on shutdown."""
    settings = get_settings()
    settings.export_path.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Responsible LinkedIn job search scraper and dashboard for "
            "publicly available job listings."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(search_router, prefix="/api")
    app.include_router(scraping_jobs_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    app.include_router(export_router, prefix="/api")

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app


app = create_app()
