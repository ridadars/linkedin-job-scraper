"""Tests for applicant-count parsing."""

from app.services.applicant_parser_service import (
    parse_applicant_count,
    parse_applicant_count_detailed,
)


def test_single_applicant() -> None:
    assert parse_applicant_count("1 applicant") == 1


def test_exact_applicants() -> None:
    assert parse_applicant_count("25 applicants") == 25


def test_plus_applicants_lower_bound() -> None:
    count, warning = parse_applicant_count_detailed("100+ applicants")
    assert count == 100
    assert warning is not None


def test_over_applicants_lower_bound() -> None:
    count, warning = parse_applicant_count_detailed("Over 100 applicants")
    assert count == 100
    assert warning is not None


def test_first_applicants() -> None:
    assert parse_applicant_count("Be among the first 25 applicants") == 25


def test_missing_input() -> None:
    assert parse_applicant_count(None) is None
    assert parse_applicant_count("") is None


def test_unknown_value() -> None:
    assert parse_applicant_count("actively recruiting") is None
    assert parse_applicant_count("not available") is None


def test_malformed_value() -> None:
    assert parse_applicant_count("applicants") is None
    assert parse_applicant_count("N/A") is None
