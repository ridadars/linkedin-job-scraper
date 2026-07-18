# LinkedIn Job Scraper

A modular FastAPI application for searching publicly available LinkedIn job listings, storing results in SQLite, and exporting data for personal job-search research.

> **Phase 5 (MVP) complete:** Background job execution via a `start` endpoint, results & jobs query APIs with filtering/sorting/pagination, and CSV/JSON exports (global and per scraping-job).

## Phase 5 API

| Method & path | Purpose |
| --- | --- |
| `POST /api/scraping-jobs/{job_id}/start` | Start a **pending** job; runs in the background, returns immediately |
| `GET /api/scraping-jobs/{job_id}/results` | Paginated jobs discovered by that scraping job |
| `GET /api/jobs` | Filter/sort/paginate all canonical jobs |
| `GET /api/jobs/{job_id}` | A single canonical job |
| `GET /api/export/csv` · `GET /api/export/json` | Export all (filtered) jobs |
| `GET /api/scraping-jobs/{job_id}/export/csv` · `.../export/json` | Export one scraping job's jobs |

### Start endpoint & background execution

The start endpoint transitions a **pending** job to `running` synchronously
(preventing duplicate starts and reporting status immediately), then schedules
the real scraping via the existing internal execution service using FastAPI
`BackgroundTasks`. It returns `202` right away and never blocks until scraping
completes. Non-startable states return readable `409`s (already running,
completed, failed, cancelled); a bad id is `400` and a missing job is `404`.

> **`BackgroundTasks` is an in-process MVP convenience, not a production-grade
> job queue** — tasks share the web process, don't survive a restart, and aren't
> distributed. Production would use a real worker/queue (still no Celery/Redis in
> this project by design).

### Jobs filtering

`GET /api/jobs` supports `keyword`, `company`, `location`, `country`,
`workplace_type`, `employment_type`, `experience_level`, `skill`, `easy_apply`,
and a `posted_after`/`posted_before` date range, plus `page`, `page_size`, and
`sort=newest|oldest`. String filters are case-insensitive substring matches;
categorical filters are exact. Ordering has a stable secondary key (`id`) so
responses are deterministic.

### Exports

CSV is UTF-8, one job per row, skills joined by `; `, with a safe timestamped
filename and a `Content-Disposition: attachment` header. JSON includes a
`generated_at` timestamp, `total_jobs`, `metadata` (active filters or scraping-job
info), and the `jobs` list. Both global and per-scraping-job variants share the
same filtering/serialization.

### Manual smoke-test finding

Running the optional live smoke test (Phase 4.1) against the public logged-out
`/jobs/search/` page returns a **sign-in wall**, which the scraper correctly
detects as `authentication_required` and stops on — validating blocked-page
detection against real LinkedIn markup. Because the logged-out page is walled,
no live job cards are observable, so selectors were **not** changed (and
blocked-page detection was **not** weakened to get around the wall).

> Automated tests (`pytest -v`) mock the execution runner: they make no external
> network requests, never launch Playwright, never require Chromium, and never
> touch the real development database. **The dashboard/UI phase has not started.**

> **Phase 4.1 hardening complete:** Salary-period persistence, indexed job-fingerprint duplicate lookup, stricter short-skill matching, clearer stale-schema detection, and an optional manual live smoke-test utility.

## Phase 4.1 Hardening

- **Salary-period persistence.** The parsed pay period (`hour`/`day`/`week`/`month`/`year`) is now stored on `LinkedInJob.salary_period`. It is **never annualized** and currencies are **never converted** — the original `salary_text` is preserved verbatim. When no period can be identified the field is left `None` (chosen over a sentinel `"unknown"` for consistency). An existing period is never erased by a later partial update.
- **Indexed job fingerprint.** `LinkedInJob.job_fingerprint` stores a deterministic SHA-256 of normalized title + company + location, with a database index. Duplicate detection priority is unchanged — (1) LinkedIn job ID, (2) normalized job URL, (3) fingerprint — but the fingerprint step is now a **direct indexed query** instead of a full-table Python scan. Legacy rows with a `NULL` fingerprint (and only those) are recomputed as a bounded compatibility path, so old data never crashes lookups. The fingerprint is written on creation and recomputed when title/company/location meaningfully change; a missing value never erases a valid one. The field is intentionally **not unique** (incomplete records may legitimately collide).
- **Stricter short-skill matching.** The one/two-letter language names get context-aware patterns: `Go` is rejected in "go-to-market"/"go live"/"go ahead" (and still not matched in "Google"/"ongoing"), `R` is rejected in "R&D" (and "React"/"required"/"recruiter"), and bare `C` is never emitted for "C++"/"C#" (but is detected in "C/C++", "C and C++", "C programming"). `Golang` and `RStudio` are aliases for `Go` and `R`. Existing support for `C++`, `C#`, `.NET`, `Node.js`, `CI/CD`, `Java`, and `JavaScript` is preserved.
- **Clearer schema compatibility.** A fresh database created via `create_all` includes the new columns and index. An out-of-date database produces a readable developer error (naming the missing columns) instead of an opaque SQL error. **No database is ever automatically deleted or migrated.**

### Development database reset (destructive)

If the compatibility check reports a stale schema, reset your **development** database. This is destructive and only appropriate for the local dev database:

```bash
cp linkedin_jobs.db linkedin_jobs_backup.db   # optional backup
rm linkedin_jobs.db
uvicorn app.main:app --reload                 # recreates a fresh schema
```

Production deployments must use a real migration system (**Alembic**) rather than this manual reset.

### Optional manual live smoke test

Selectors are synthetic and validated only against fixtures, so **real LinkedIn selectors may need manual tuning**. An opt-in utility can sanity-check them against a live page. It is never imported by the app and never runs during `pytest`, requires a manually installed Chromium, and must be explicitly acknowledged:

```bash
playwright install chromium
python scripts/manual_linkedin_smoke_test.py \
  --search-url "https://www.linkedin.com/jobs/search/?keywords=Python&location=Pakistan" \
  --max-jobs 1 \
  --i-understand-this-makes-a-live-request
```

It caps at 3 jobs, validates the URL first, prints only a safe summary (page state, card count, title, company, location, validated job URL — never full HTML), stops immediately on a CAPTCHA/sign-in/access-restriction without retrying, never logs in or stores cookies, and never writes to the database.

> Automated tests (`pytest -v`) make no external network requests, never launch Playwright, and never touch the real development database. **Phase 5 has not started** — there is still no public `/start` or `/cancel` endpoint and no export/dashboard.

## Phase 4 Features

Phase 4 connects the Phase 3 scraping/parsing foundation to the database.

### Processing pipeline

For each discovered job the pipeline runs: **merge** (card + optional detail) →
**normalize** (title, company, location, URL, categorical values) → **validate**
required fields → **enrich** (skills, salary, applicant count, posting date,
country) → **classify** (`complete` / `partial` / `failed`) → **persist** (upsert
canonical job + search association) → **update counters**. Orchestration lives in
`app/services/scraping_job_execution_service.py` (internal only — see below).

### Skill extraction

Dictionary-based and deterministic (`app/skill_catalog.py` +
`app/services/skill_extraction_service.py`). No LLM or paid API. Boundary-aware
matching avoids substring false positives (`R` ≠ "random", `Go` ≠ "Google",
`Java` ≠ "JavaScript", `C` ≠ every word with a "c") while still detecting `C++`,
`C#`, `.NET`, `Node.js`, and `CI/CD`. Aliases collapse to one canonical skill
(`NLP` → Natural Language Processing, `LLM` → Large Language Models, `GCP` →
Google Cloud). Skills are stored as a JSON list.

### Salary parsing (conservative)

`app/services/salary_parser_service.py` extracts `salary_min`, `salary_max`,
`salary_currency`, and preserves `salary_text`. It detects USD/PKR/GBP/EUR and a
pay period, supports `k` suffixes and "from"/"up to". It **never** converts
currencies, **never** annualizes monthly/hourly pay, and **never** invents a
missing end of a range — ambiguous input leaves numeric fields `None`. The pay
period is not stored (no column); a warning is emitted for monthly/hourly pay.

### Applicant-count and date parsing

`parse_applicant_count` returns a conservative lower-bound integer ("Over 100" /
"100+" → 100 with a lower-bound warning; unknown/malformed → `None`).
`parse_posted_date` converts relative strings ("2 days ago", "Reposted 1 week
ago", "Posted yesterday") to UTC-aware datetimes against a reference time (one
month ≈ 30 days); the raw relative text is kept in `relative_posted_time`.

### Global duplicate detection & the canonical job

`app/services/duplicate_service.py` matches by priority: (1) LinkedIn job ID,
(2) normalized job URL, (3) a deterministic **SHA-256** fingerprint of
normalized title + company + location. Different companies or different
locations never collide via the fingerprint alone. The **canonical
`LinkedInJob`** row represents the job itself; it is created once and updated
with better/newer data on later encounters.

### Search-to-job association

A new association model `app/models/scraping_job_result.py`
(`ScrapingJobResult`) records that a particular search discovered a particular
canonical job, with a unique `(scraping_job_id, linkedin_job_id)` constraint.
This makes the relationship a true many-to-many: one canonical job can appear in
many searches, and one search can discover many jobs. The legacy
`LinkedInJob.scraping_job_id` column is **preserved** for backward compatibility
and records the search that first created the canonical record.

### Scraping-job counters

| Counter | Meaning |
| --- | --- |
| `discovered_jobs` | Unique job cards returned by the search parser |
| `processed_jobs` | Discovered cards for which processing was attempted |
| `successful_jobs` | Jobs successfully inserted/updated and associated |
| `duplicate_jobs` | Processed jobs matched to an existing canonical job |
| `failed_jobs` | Discovered jobs that could not be saved/associated |

Invariants: counters never go negative; `processed_jobs ≤ discovered_jobs`; and
`successful_jobs + failed_jobs == processed_jobs`. A duplicate that is
successfully associated counts as **one successful and one duplicate** — never a
failure.

### Final status rules

- `completed` — search finished and no individual job failed (an empty but valid
  search is still `completed`).
- `partially_completed` — at least one job saved **and** at least one failed, or
  the run stopped after some results due to a later restriction.
- `failed` — the search page itself could not be collected, or a blocking page
  (CAPTCHA / sign-in / access restriction) appeared before any useful results.
- `cancelled` — the run was cancelled; completed results are preserved.

### Error recording

`app/services/scraping_error_service.py` stores stable error types with short,
sanitized messages, committed independently so a later failure never erases
earlier error rows. It never stores HTML, cookies, tokens, credentials, or
CAPTCHA content, truncates long messages, and de-duplicates identical errors.

### Transaction strategy

The run is **not** one giant transaction. Running-state changes commit up front;
each job is persisted in its own unit of work and rolled back on failure so one
bad job never corrupts the run or the counters. Individual job failures are
recorded and skipped; only search-level blocking conditions stop the run.

### Internal execution only

Phase 4 exposes **no public `/start` or `/cancel` endpoint** — execution is an
internal service. **No extracted jobs are persisted via any HTTP route yet.**
Those, plus result APIs and exports, arrive in Phase 5.

### Development database reset

The app fails fast with a clear message if the local SQLite schema is out of
date (rather than a confusing SQL error). Reset your development database with:

```bash
rm linkedin_jobs.db
uvicorn app.main:app --reload
```

No automatic destructive migration is performed. For production, use **Alembic**
migrations, **background workers** with **distributed locking** for concurrent/
scheduled runs, and **approved LinkedIn API access**. Selectors in
`app/linkedin_selectors.py` are synthetic and still require real-world tuning.
`pytest -v` never contacts LinkedIn or launches a browser.

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

- **Phase 5:** Public `/start` & `/cancel` execution endpoints, job result API endpoints, and export services
- **Phase 6:** Dashboard UI
- **Phase 7:** Final review and complete documentation
