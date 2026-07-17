"""Association between a scraping search and a canonical LinkedIn job.

The canonical ``LinkedInJob`` row represents the job itself. A
``ScrapingJobResult`` row represents the fact that a particular scraping search
discovered that job, along with per-search metadata (rank in the results,
whether detail was fetched, and any per-job error). This makes the relationship
a true many-to-many:

* one canonical job can appear in many scraping searches, and
* one scraping search can discover many canonical jobs.

The legacy ``LinkedInJob.scraping_job_id`` column is preserved for backward
compatibility and records the search that first created the canonical record.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.linkedin_job import LinkedInJob
    from app.models.scraping_job import ScrapingJob


class ScrapingJobResult(Base):
    """Records that a scraping search discovered a specific canonical job."""

    __tablename__ = "scraping_job_results"
    __table_args__ = (
        UniqueConstraint(
            "scraping_job_id",
            "linkedin_job_id",
            name="uq_scraping_job_result_pair",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    scraping_job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("scraping_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linkedin_job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("linkedin_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_rank: Mapped[int | None] = mapped_column(Integer)
    result_status: Mapped[str | None] = mapped_column(String(32))
    detail_fetched: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
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

    scraping_job: Mapped[ScrapingJob] = relationship(
        "ScrapingJob",
        back_populates="results",
    )
    linkedin_job: Mapped[LinkedInJob] = relationship(
        "LinkedInJob",
        back_populates="search_results",
    )

    def __repr__(self) -> str:
        return (
            f"<ScrapingJobResult scraping_job_id={self.scraping_job_id!r} "
            f"linkedin_job_id={self.linkedin_job_id!r}>"
        )
