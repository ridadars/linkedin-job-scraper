"""Conservative applicant-count parsing.

Extracts a lower-bound integer from LinkedIn's applicant labels. "Over 100" and
"100+" return 100 flagged as a lower bound; unknown/unavailable/malformed values
return ``None``. Counts are never invented.
"""

import re

_NUMBER_PATTERN = re.compile(r"\d[\d,]*")
_LOWER_BOUND_HINTS = ("over", "+", "more than", "at least")


def parse_applicant_count_detailed(value: str | None) -> tuple[int | None, str | None]:
    """Return ``(count, warning)`` for an applicant-count string.

    ``warning`` is set when the returned count is a lower bound (e.g. "Over 100").
    """
    if value is None or not value.strip():
        return None, None

    lowered = value.lower()
    match = _NUMBER_PATTERN.search(lowered)
    if match is None:
        # "actively recruiting", "unknown", "not available", etc.
        return None, None

    try:
        count = int(match.group(0).replace(",", ""))
    except ValueError:
        return None, None

    if count < 0:
        return None, None

    if any(hint in lowered for hint in _LOWER_BOUND_HINTS):
        return count, "applicant_count is a lower bound"

    return count, None


def parse_applicant_count(value: str | None) -> int | None:
    """Return a conservative applicant count, or ``None`` if unavailable."""
    count, _ = parse_applicant_count_detailed(value)
    return count
