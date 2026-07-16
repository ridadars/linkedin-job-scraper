"""Scraping error database model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.scraping_job import ScrapingJob


class ScrapingError(Base):
    """Records errors encountered while processing individual job listings."""

    __tablename__ = "scraping_errors"

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
    job_url: Mapped[str | None] = mapped_column(String(2048))
    error_type: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    scraping_job: Mapped[ScrapingJob] = relationship("ScrapingJob", back_populates="errors")

    def __repr__(self) -> str:
        return f"<ScrapingError id={self.id!r} error_type={self.error_type!r}>"
