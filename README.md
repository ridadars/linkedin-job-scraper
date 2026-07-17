# LinkedIn Job Scraper

A modular FastAPI application for searching publicly available LinkedIn job listings, storing results in SQLite, and exporting data for personal job-search research.

> **Phase 3 complete:** Async Playwright browser automation, LinkedIn HTML parsers, safe URL validation, and blocked-page detection.

## Phase 3 Features

- Async Playwright browser lifecycle (`app/services/browser_service.py`) with an isolated, non-persistent context — no cookies, sessions, or automatic login
- Safe LinkedIn URL validation (`app/utils/linkedin_url_validator.py`) applied before navigation **and** after redirects
- Search-results HTML parser (`app/services/linkedin_search_parser.py`)
- Individual job-detail HTML parser (`app/services/linkedin_job_parser.py`)
- Blocked-page detection (`app/services/page_state_service.py`): CAPTCHA, sign-in wall, access restriction, removed/expired job, and empty results — with false-positive protection for legitimate jobs mentioning "security"/"login"/"authentication"
- Centralized selectors with fallback lists (`app/linkedin_selectors.py`)
- Structured exceptions (`app/exceptions.py`)
- Reusable HTML/text utilities that preserve `C++`, `C#`, `.NET`, `Node.js`
- Local synthetic HTML fixtures and comprehensive unit tests that make **no external network requests**

### Playwright setup

Install the Python packages and then the Chromium browser binary (browser binaries are **not** installed automatically from Python code):

```bash
pip install -r requirements.txt
playwright install chromium
```

### Browser configuration

Configured via environment variables (see `.env.example`):

| Variable | Default | Meaning |
| --- | --- | --- |
| `HEADLESS` | `true` | Run Chromium headless |
| `BROWSER_NAME` | `chromium` | Only `chromium` is supported for now |
| `PAGE_TIMEOUT_SECONDS` | `30` | Default page timeout (must be > 0) |
| `NAVIGATION_TIMEOUT_SECONDS` | `30` | Navigation timeout (must be > 0) |
| `REQUEST_DELAY_SECONDS` | `8` | Delay/backoff base between requests (≥ 0) |
| `MAX_RETRIES` | `3` | Retry budget for transient navigation errors (0–5) |
| `MAX_SCROLL_ATTEMPTS` | `5` | Bounded scrolls to load lazy cards (0–10) |
| `SCROLL_WAIT_SECONDS` | `1` | Wait between scrolls (≥ 0) |

### Parser architecture

The scraper service validates a URL, uses the browser service to capture a page
snapshot (`final_url`, `title`, `html`), re-validates the final redirected URL,
detects the page state, and passes the HTML to the correct parser. Parsers use
BeautifulSoup with centralized fallback selectors and return plain Pydantic
models (`JobCardData`, `JobDetailData`, `SearchPageResult`) — never SQLAlchemy
models. Each search card is parsed independently, so one malformed card never
fails the whole page, and page-level duplicates are removed by job id, then
normalized URL, then title/company/location.

### Supported LinkedIn URL formats

Only these public URL shapes are permitted (HTTPS, host exactly
`www.linkedin.com`, no credentials, no custom ports):

```text
https://www.linkedin.com/jobs/search/
https://www.linkedin.com/jobs/view/{numeric-job-id}/
```

Everything else — HTTP, external/lookalike domains, embedded credentials,
non-standard ports, unrelated LinkedIn paths, and `javascript:`/`file:`/`data:`
schemes — is rejected.

### Blocked-page behavior

When a fetched page is a CAPTCHA/challenge, sign-in wall, or rate-limit/access-denied
page, the parsers raise a structured exception (`CaptchaDetectedError`,
`AuthenticationRequiredError`, `AccessRestrictedError`). Removed/expired job pages
raise `JobPageNotFoundError`. Valid searches with zero results return an empty list.
These blocked states are **never** retried; only transient navigation errors are
retried with limited exponential backoff bounded by `MAX_RETRIES`.

### Responsible use restrictions

This tool only collects permitted, publicly available job listings. It does **not**
and will **not**: solve CAPTCHAs, automatically log into LinkedIn, store credentials
or cookies, rotate proxies, spoof fingerprints, click verification/challenge
controls, or otherwise bypass access restrictions. Exception messages and logs never
include full HTML, cookies, tokens, credentials, or browser storage.

### Selector-maintenance limitation

LinkedIn's markup is not a stable public contract. Selectors are centralized in
`app/linkedin_selectors.py` with fallback lists to make updates easy, but they will
need periodic maintenance when LinkedIn changes its HTML.

### Local fixture-based testing

All Phase 3 tests run against synthetic HTML fixtures in
`tests/fixtures/linkedin/` with a mocked browser and mocked Playwright objects.
`pytest -v` does **not** contact LinkedIn or any external site or API.

> **Scope note:** Phase 3 does not add a scraping-execution endpoint — there is no
> `/start` or `/cancel` — and no extracted jobs are persisted to the database yet.
> Those arrive in later phases.

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

- **Phase 4:** Skill extraction, duplicate detection, job storage
- **Phase 5:** Full job result API endpoints and export services
- **Phase 6:** Dashboard UI
- **Phase 7:** Final review and complete documentation
