# LinkedIn Job Scraper

A modular FastAPI application for searching publicly available LinkedIn job listings, storing results in SQLite, and exporting data for personal job-search research.

> **Phase 2 complete:** Search validation, LinkedIn URL builder, scraping-job creation, and API endpoints.

## Phase 2 Features

- Pydantic schemas with enum-based filter validation
- Centralized LinkedIn filter mappings (`app/linkedin_filters.py`)
- LinkedIn job search URL builder with HTTPS/domain safety checks
- Search input normalization (preserves `C++`, `C#`, `.NET`, `Node.js`)
- Scraping job creation service (no browser automation)
- Duplicate pending-search detection within configurable time window
- API endpoints:
  - `POST /api/search-jobs`
  - `GET /api/scraping-jobs`
  - `GET /api/scraping-jobs/{job_id}`

## Phase 1 Features

- Modular project structure
- Environment-based configuration via `python-dotenv` and Pydantic Settings
- SQLAlchemy database setup with SQLite
- Database models: `ScrapingJob`, `LinkedInJob`, `ScrapingError`
- FastAPI application with restricted CORS
- Health check endpoint at `GET /api/health`

## Installation

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

## Run the Application

```bash
uvicorn app.main:app --reload
```

Or:

```bash
python run.py
```

## Test Phase 2

```bash
pytest -v
```

## API Examples

### Create a search job

```bash
curl -X POST http://127.0.0.1:8000/api/search-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "Artificial Intelligence Intern",
    "location": "Karachi, Pakistan",
    "experience_level": "internship",
    "employment_type": "internship",
    "workplace_type": "hybrid",
    "date_posted": "past_week",
    "easy_apply_only": false,
    "max_jobs": 30
  }'
```

### List scraping jobs

```bash
curl "http://127.0.0.1:8000/api/scraping-jobs?page=1&page_size=20"
```

### Get scraping job details

```bash
curl "http://127.0.0.1:8000/api/scraping-jobs/{job_id}"
```

## Test Phase 1

```bash
pytest tests/test_health.py -v
```

## Health Check

```bash
curl http://127.0.0.1:8000/api/health
```

Example response:

```json
{
  "status": "ok",
  "app_name": "LinkedIn Job Scraper",
  "timestamp": "2026-07-17T00:00:00Z",
  "database": "connected"
}
```

## Responsible Use

This tool is intended for responsible research and personal job-search assistance. Only collect publicly available information that you are authorized to access. Do not use it to bypass LinkedIn restrictions or collect private personal data.

## Next Phases

- **Phase 3:** Playwright browser automation and HTML parsers
- **Phase 4:** Skill extraction, duplicate detection, job storage
- **Phase 5:** Full job result API endpoints and export services
- **Phase 6:** Dashboard UI
- **Phase 7:** Final review and complete documentation
