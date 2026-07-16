"""Shared Pydantic schemas for pagination and API errors."""

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Validated pagination query parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-based).")
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of records per page.",
    )


class PaginatedResponse(BaseModel):
    """Pagination metadata included in list responses."""

    page: int
    page_size: int
    total_records: int
    total_pages: int


class ErrorResponse(BaseModel):
    """Standard API error payload."""

    detail: str
