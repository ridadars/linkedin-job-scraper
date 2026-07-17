"""Tests for relative posting-date parsing with a fixed reference time."""

from datetime import UTC, datetime, timedelta

from app.services.date_parser_service import parse_posted_date

REFERENCE = datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC)


def _parse(text: str):
    return parse_posted_date(text, REFERENCE)


def test_just_now() -> None:
    assert _parse("Just now") == REFERENCE


def test_minutes_ago() -> None:
    assert _parse("30 minutes ago") == REFERENCE - timedelta(minutes=30)


def test_hours_ago() -> None:
    assert _parse("2 hours ago") == REFERENCE - timedelta(hours=2)


def test_one_day_ago() -> None:
    assert _parse("1 day ago") == REFERENCE - timedelta(days=1)


def test_multiple_days_ago() -> None:
    assert _parse("3 days ago") == REFERENCE - timedelta(days=3)


def test_one_week_ago() -> None:
    assert _parse("1 week ago") == REFERENCE - timedelta(weeks=1)


def test_multiple_weeks_ago() -> None:
    assert _parse("2 weeks ago") == REFERENCE - timedelta(weeks=2)


def test_one_month_ago_approximated() -> None:
    assert _parse("1 month ago") == REFERENCE - timedelta(days=30)


def test_reposted_prefix_stripped() -> None:
    assert _parse("Reposted 2 days ago") == REFERENCE - timedelta(days=2)


def test_posted_today() -> None:
    assert _parse("Posted today") == REFERENCE


def test_posted_yesterday() -> None:
    assert _parse("Posted yesterday") == REFERENCE - timedelta(days=1)


def test_missing_value() -> None:
    assert _parse("") is None
    assert parse_posted_date(None, REFERENCE) is None


def test_unsupported_value() -> None:
    assert _parse("5 years ago") is None
    assert _parse("some day") is None


def test_result_is_utc_aware() -> None:
    result = _parse("2 hours ago")
    assert result is not None and result.tzinfo is not None


def test_default_reference_is_now() -> None:
    # Without a reference time, "just now" is close to the current UTC moment.
    result = parse_posted_date("just now")
    assert result is not None
    assert abs((datetime.now(UTC) - result).total_seconds()) < 5
