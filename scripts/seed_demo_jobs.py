"""Seed synthetic DEMO jobs so the dashboard can be demonstrated offline.

Unauthenticated LinkedIn returns a sign-in wall, so live scraping cannot be
shown end-to-end. This script inserts a handful of clearly-labelled synthetic
jobs (and one demo scraping job that "discovered" them) directly into the
database. It is:

* manual only — never imported by the app and never run during tests;
* non-destructive — it never overwrites or deletes existing rows, and it skips
  seeding if demo data is already present;
* not a production seed endpoint — there is no HTTP route for this.

Usage::

    python scripts/seed_demo_jobs.py            # seed if not already seeded
    python scripts/seed_demo_jobs.py --force    # add another demo batch

Run against your development database only.
"""

import argparse
import json
import pathlib
import sys
import uuid
from datetime import UTC, datetime, timedelta

# Make the project root importable when run as `python scripts/...`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

DEMO_MARKER = "[DEMO]"

_DEMO_JOBS = [
    {
        "title": "Senior Python Engineer",
        "company_name": "Acme Analytics",
        "location": "Karachi, Pakistan",
        "country": "Pakistan",
        "workplace_type": "remote",
        "employment_type": "full_time",
        "experience_level": "mid_senior",
        "salary_text": "PKR 400,000 - 600,000 per month",
        "salary_min": 400000,
        "salary_max": 600000,
        "salary_currency": "PKR",
        "salary_period": "month",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "applicant_count": 87,
        "easy_apply": True,
        "posted_days_ago": 2,
    },
    {
        "title": "Machine Learning Engineer",
        "company_name": "Globex AI",
        "location": "Lahore, Pakistan",
        "country": "Pakistan",
        "workplace_type": "hybrid",
        "employment_type": "full_time",
        "experience_level": "associate",
        "salary_text": "PKR 300,000 - 450,000 per month",
        "salary_min": 300000,
        "salary_max": 450000,
        "salary_currency": "PKR",
        "salary_period": "month",
        "skills": ["Python", "PyTorch", "Machine Learning", "Natural Language Processing"],
        "applicant_count": 142,
        "easy_apply": False,
        "posted_days_ago": 5,
    },
    {
        "title": "Frontend Developer (React)",
        "company_name": "Initech",
        "location": "Islamabad, Pakistan",
        "country": "Pakistan",
        "workplace_type": "onsite",
        "employment_type": "contract",
        "experience_level": "entry_level",
        "salary_text": None,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "salary_period": None,
        "skills": ["JavaScript", "React", "CSS", "HTML"],
        "applicant_count": 34,
        "easy_apply": True,
        "posted_days_ago": 1,
    },
    {
        "title": "Data Engineer",
        "company_name": "Umbrella Data",
        "location": "Remote, EU",
        "country": None,
        "workplace_type": "remote",
        "employment_type": "full_time",
        "experience_level": "mid_senior",
        "salary_text": "€60,000 - €80,000 per year",
        "salary_min": 60000,
        "salary_max": 80000,
        "salary_currency": "EUR",
        "salary_period": "year",
        "skills": ["Python", "SQL", "Apache Spark", "AWS"],
        "applicant_count": 61,
        "easy_apply": False,
        "posted_days_ago": 9,
    },
    {
        "title": "Junior Backend Developer (Node.js)",
        "company_name": "Stark Systems",
        "location": "Karachi, Pakistan",
        "country": "Pakistan",
        "workplace_type": "hybrid",
        "employment_type": "internship",
        "experience_level": "internship",
        "salary_text": "PKR 60,000 per month",
        "salary_min": 60000,
        "salary_max": 60000,
        "salary_currency": "PKR",
        "salary_period": "month",
        "skills": ["Node.js", "Express.js", "MongoDB"],
        "applicant_count": 5,
        "easy_apply": True,
        "posted_days_ago": 0,
    },
]


def _already_seeded(db, ScrapingJob) -> bool:
    from sqlalchemy import select

    return db.scalar(
        select(ScrapingJob).where(ScrapingJob.keywords.like(f"{DEMO_MARKER}%")).limit(1)
    ) is not None


def seed(force: bool = False) -> int:
    """Insert one batch of demo jobs. Returns the number of jobs inserted."""
    from app.database import SessionLocal, init_db
    from app.models.enums import ScrapingJobStatus
    from app.models.linkedin_job import LinkedInJob
    from app.models.scraping_job import ScrapingJob
    from app.models.scraping_job_result import ScrapingJobResult

    init_db()
    db = SessionLocal()
    try:
        if not force and _already_seeded(db, ScrapingJob):
            print("Demo data already present. Use --force to add another batch.")
            return 0

        now = datetime.now(UTC)
        scraping_job = ScrapingJob(
            keywords=f"{DEMO_MARKER} Python Developer",
            location="Pakistan",
            max_jobs=len(_DEMO_JOBS),
            status=ScrapingJobStatus.COMPLETED.value,
            search_url="https://www.linkedin.com/jobs/search/",
            discovered_jobs=len(_DEMO_JOBS),
            processed_jobs=len(_DEMO_JOBS),
            successful_jobs=len(_DEMO_JOBS),
            duplicate_jobs=0,
            failed_jobs=0,
            started_at=now,
            completed_at=now,
        )
        db.add(scraping_job)
        db.commit()

        inserted = 0
        for rank, spec in enumerate(_DEMO_JOBS, start=1):
            job_id = uuid.uuid4().hex[:10]
            job = LinkedInJob(
                scraping_job_id=scraping_job.id,
                linkedin_job_id=job_id,
                title=spec["title"],
                company_name=spec["company_name"],
                location=spec["location"],
                country=spec["country"],
                workplace_type=spec["workplace_type"],
                employment_type=spec["employment_type"],
                experience_level=spec["experience_level"],
                salary_text=spec["salary_text"],
                salary_min=spec["salary_min"],
                salary_max=spec["salary_max"],
                salary_currency=spec["salary_currency"],
                salary_period=spec["salary_period"],
                required_skills_json=json.dumps(spec["skills"]),
                applicant_count=spec["applicant_count"],
                easy_apply=spec["easy_apply"],
                posted_date=now - timedelta(days=spec["posted_days_ago"]),
                relative_posted_time=f"{spec['posted_days_ago']} days ago",
                job_url=f"https://www.linkedin.com/jobs/view/{job_id}/",
                normalized_job_url=f"https://www.linkedin.com/jobs/view/{job_id}/",
                status="complete",
                description=(
                    f"{DEMO_MARKER} Synthetic demo listing for dashboard testing. "
                    f"This role focuses on {', '.join(spec['skills'])}."
                ),
            )
            db.add(job)
            db.commit()
            db.add(
                ScrapingJobResult(
                    scraping_job_id=scraping_job.id,
                    linkedin_job_id=job.id,
                    source_rank=rank,
                    result_status="complete",
                    detail_fetched=True,
                )
            )
            db.commit()
            inserted += 1

        print(f"Seeded demo scraping job {scraping_job.id} with {inserted} jobs.")
        print("Open http://127.0.0.1:8000/ and click 'Apply' to browse them.")
        return inserted
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed synthetic demo jobs (manual only).")
    parser.add_argument("--force", action="store_true", help="Add another demo batch even if one exists.")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    seed(force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
