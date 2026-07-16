"""Normalization utilities for job search input fields."""

import re
from typing import TypeVar

from pydantic import BaseModel

TEnum = TypeVar("TEnum", bound=BaseModel)

_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE_PATTERN = re.compile(r"\s+")

MAX_KEYWORDS_LENGTH = 150
MAX_LOCATION_LENGTH = 150


def trim_text(value: str) -> str:
    """Remove leading and trailing whitespace."""
    return value.strip()


def collapse_spaces(value: str) -> str:
    """Replace repeated internal whitespace with a single space."""
    return _MULTI_SPACE_PATTERN.sub(" ", value)


def reject_control_characters(value: str, field_name: str = "value") -> str:
    """Raise ValueError if control characters are present."""
    if _CONTROL_CHAR_PATTERN.search(value):
        raise ValueError(f"{field_name} must not contain control characters.")
    return value


def normalize_keywords(keywords: str) -> str:
    """Normalize job search keywords while preserving meaningful symbols."""
    cleaned = reject_control_characters(trim_text(keywords), "keywords")
    cleaned = collapse_spaces(cleaned)
    if not cleaned:
        raise ValueError("keywords must not be empty or contain only whitespace.")
    if len(cleaned) > MAX_KEYWORDS_LENGTH:
        raise ValueError(
            f"keywords must not exceed {MAX_KEYWORDS_LENGTH} characters."
        )
    return cleaned


def normalize_location(location: str | None) -> str | None:
    """Normalize optional location text."""
    if location is None:
        return None
    cleaned = reject_control_characters(trim_text(location), "location")
    cleaned = collapse_spaces(cleaned)
    if not cleaned:
        return None
    if len(cleaned) > MAX_LOCATION_LENGTH:
        raise ValueError(
            f"location must not exceed {MAX_LOCATION_LENGTH} characters."
        )
    return cleaned


def enum_to_storage_value(enum_value: object | None) -> str | None:
    """Convert a Pydantic enum member to its string storage value."""
    if enum_value is None:
        return None
    return str(getattr(enum_value, "value", enum_value))
