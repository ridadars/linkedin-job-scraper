"""Relative posting-date parsing.

Converts LinkedIn's relative posting strings ("2 days ago", "Reposted 1 week
ago", "Posted yesterday") into UTC-aware datetimes relative to a reference time.
A fixed ``reference_time`` can be supplied for deterministic tests. One month is
approximated as 30 days. Unrecognized values return ``None`` and never parse
stray numbers from unrelated text.
"""

import re
from datetime import UTC, datetime, timedelta

_UNIT_TO_TIMEDELTA = {
    "minute": lambda n: timedelta(minutes=n),
    "min": lambda n: timedelta(minutes=n),
    "hour": lambda n: timedelta(hours=n),
    "hr": lambda n: timedelta(hours=n),
    "day": lambda n: timedelta(days=n),
    "week": lambda n: timedelta(weeks=n),
    "month": lambda n: timedelta(days=30 * n),
}

# Anchor at the start so a description's stray "5 years experience" is ignored.
_RELATIVE_PATTERN = re.compile(
    r"^(?:reposted|posted)?\s*"
    r"(\d+)\s*(minute|min|hour|hr|day|week|month)s?\s*ago\b",
    re.IGNORECASE,
)


def _now(reference_time: datetime | None) -> datetime:
    if reference_time is None:
        return datetime.now(UTC)
    if reference_time.tzinfo is None:
        return reference_time.replace(tzinfo=UTC)
    return reference_time.astimezone(UTC)


def parse_posted_date(
    posted_text: str | None,
    reference_time: datetime | None = None,
) -> datetime | None:
    """Parse a relative posting string into a UTC-aware datetime, or None."""
    if posted_text is None or not posted_text.strip():
        return None

    now = _now(reference_time)
    text = posted_text.strip().lower()

    # Same-day phrasings.
    if "just now" in text or text in {"today", "posted today"} or text.endswith("today"):
        return now
    if "yesterday" in text:
        return now - timedelta(days=1)

    match = _RELATIVE_PATTERN.search(text)
    if match is None:
        return None

    amount = int(match.group(1))
    unit = match.group(2).lower()
    delta_factory = _UNIT_TO_TIMEDELTA.get(unit)
    if delta_factory is None:
        return None

    return now - delta_factory(amount)
