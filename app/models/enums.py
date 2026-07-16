"""Shared model enumerations."""

from enum import StrEnum


class ScrapingJobStatus(StrEnum):
    """Lifecycle states for a scraping job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
