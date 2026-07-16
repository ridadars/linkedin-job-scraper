"""Scraping job database model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ScrapingJobStatus

if TYPE_CHECKING:
    from app.models.linkedin_job import LinkedInJob
    from app.models.scraping_error import ScrapingError


class ScrapingJob(Base):
    """Tracks a single LinkedIn job search and scraping run."""

    __tablename__ = "scraping_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    keywords: Mapped[str] = mapped_column(String(512), nullable=False)
    location: Mapped[str | None] = mapped_column(String(512))
    experience_level: Mapped[str | None] = mapped_column(String(64))
    employment_type: Mapped[str | None] = mapped_column(String(64))
    workplace_type: Mapped[str | None] = mapped_column(String(64))
    date_posted: Mapped[str | None] = mapped_column(String(64))
    easy_apply_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    search_url: Mapped[str | None] = mapped_column(String(4096))

    status: Mapped[str] = mapped_column(
        String(32),
        default=ScrapingJobStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    discovered_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    jobs: Mapped[list[LinkedInJob]] = relationship(
        "LinkedInJob",
        back_populates="scraping_job",
        cascade="all, delete-orphan",
    )
    errors: Mapped[list[ScrapingError]] = relationship(
        "ScrapingError",
        back_populates="scraping_job",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ScrapingJob id={self.id!r} status={self.status!r}>"
