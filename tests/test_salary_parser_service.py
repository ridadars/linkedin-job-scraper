"""Tests for conservative salary parsing."""

from app.services.salary_parser_service import parse_salary_text


def test_usd_yearly_range() -> None:
    result = parse_salary_text("$80,000 - $120,000 per year")
    assert result.minimum == 80000
    assert result.maximum == 120000
    assert result.currency == "USD"
    assert result.period == "year"


def test_usd_k_range() -> None:
    result = parse_salary_text("USD 80k–120k annually")
    assert result.minimum == 80000
    assert result.maximum == 120000
    assert result.currency == "USD"
    assert result.period == "year"


def test_pkr_monthly() -> None:
    result = parse_salary_text("PKR 100,000 per month")
    assert result.minimum == 100000
    assert result.maximum == 100000
    assert result.currency == "PKR"
    assert result.period == "month"


def test_rs_monthly_range() -> None:
    result = parse_salary_text("Rs. 80,000 - 120,000 a month")
    assert result.currency == "PKR"
    assert result.minimum == 80000
    assert result.maximum == 120000
    assert result.period == "month"


def test_gbp_salary() -> None:
    result = parse_salary_text("£50,000 a year")
    assert result.currency == "GBP"
    assert result.minimum == 50000
    assert result.period == "year"


def test_eur_hourly_range() -> None:
    result = parse_salary_text("€40 - €60 per hour")
    assert result.currency == "EUR"
    assert result.minimum == 40
    assert result.maximum == 60
    assert result.period == "hour"


def test_from_salary() -> None:
    result = parse_salary_text("From $70,000 per year")
    assert result.minimum == 70000
    assert result.maximum is None
    assert result.currency == "USD"


def test_up_to_salary() -> None:
    result = parse_salary_text("Up to PKR 250,000 per month")
    assert result.maximum == 250000
    assert result.minimum is None
    assert result.currency == "PKR"


def test_missing_salary() -> None:
    result = parse_salary_text(None)
    assert result.raw_text is None
    assert result.minimum is None and result.maximum is None


def test_ambiguous_salary_unparsed() -> None:
    result = parse_salary_text("Competitive salary")
    assert result.raw_text == "Competitive salary"
    assert result.minimum is None
    assert result.maximum is None
    assert result.currency is None


def test_no_currency_conversion() -> None:
    result = parse_salary_text("PKR 100,000 per month")
    # Values are stored as-is, never converted to another currency.
    assert result.currency == "PKR"
    assert result.minimum == 100000


def test_monthly_not_annualized() -> None:
    result = parse_salary_text("PKR 100,000 per month")
    assert result.maximum == 100000  # not multiplied by 12


def test_hourly_not_annualized() -> None:
    result = parse_salary_text("€60 per hour")
    assert result.maximum == 60
    assert result.period == "hour"
