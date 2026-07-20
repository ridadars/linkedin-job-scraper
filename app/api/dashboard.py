"""Dashboard route serving the Jinja2 single-page UI.

The dashboard is a thin server-rendered shell; all data is fetched client-side
from the existing Phase 5 JSON APIs. This router only returns the HTML page and
does not interfere with `/docs` or the `/api/*` routes.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

dashboard_router = APIRouter(tags=["dashboard"])


@dashboard_router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(request: Request) -> HTMLResponse:
    """Render the main dashboard page."""
    settings = get_settings()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"app_name": settings.app_name},
    )
