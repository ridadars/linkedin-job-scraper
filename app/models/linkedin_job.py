"""LinkedIn job listing database model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.scraping_job import ScrapingJob


class LinkedInJob(Base):
    """Persisted LinkedIn job listing with optional metadata fields."""

    __tablename__ = "linkedin_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    linkedin_job_id: Mapped[str | None] = mapped_column(String(64), index=True)
    scraping_job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("scraping_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str | None] = mapped_column(String(512))
    company_name: Mapped[str | None] = mapped_column(String(512), index=True)
    company_url: Mapped[str | None] = mapped_column(String(2048))
    job_url: Mapped[str | None] = mapped_column(String(2048))
    normalized_job_url: Mapped[str | None] = mapped_column(String(2048), index=True)

    location: Mapped[str | None] = mapped_column(String(512), index=True)
    country: Mapped[str | None] = mapped_column(String(128), index=True)
    workplace_type: Mapped[str | None] = mapped_column(String(64), index=True)
    employment_type: Mapped[str | None] = mapped_column(String(64), index=True)
    experience_level: Mapped[str | None] = mapped_column(String(64), index=True)

    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(16))
    salary_text: Mapped[str | None] = mapped_column(String(256))

    description: Mapped[str | None] = mapped_column(Text)
    required_skills_json: Mapped[str | None] = mapped_column(Text)
    required_qualifications_json: Mapped[str | None] = mapped_column(Text)
    preferred_qualifications_json: Mapped[str | None] = mapped_column(Text)

    applicant_count: Mapped[int | None] = mapped_column(Integer)
    easy_apply: Mapped[bool | None] = mapped_column(Boolean, index=True)
    posted_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    relative_posted_time: Mapped[str | None] = mapped_column(String(128))
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company_industry: Mapped[str | None] = mapped_column(String(256))
    company_size: Mapped[str | None] = mapped_column(String(128))
    company_website: Mapped[str | None] = mapped_column(String(2048))

    recruiter_name: Mapped[str | None] = mapped_column(String(256))
    recruiter_profile_url: Mapped[str | None] = mapped_column(String(2048))

    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    status: Mapped[str | None] = mapped_column(String(64), default="saved")
    error_message: Mapped[str | None] = mapped_column(Text)

    scraping_job: Mapped[ScrapingJob] = relationship("ScrapingJob", back_populates="jobs")

    def __repr__(self) -> str:
        return f"<LinkedInJob id={self.id!r} title={self.title!r}>"
