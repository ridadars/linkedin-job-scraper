"""Conservative salary-text parsing.

Extracts a minimum, maximum, currency, and pay period from human-written salary
strings. It never converts currencies, never annualizes monthly/hourly pay, and
never invents a missing end of a range. When the text is ambiguous (no currency
or no numbers), numeric fields are left as ``None`` and the raw text is
preserved.
"""

import re
from dataclasses import dataclass


@dataclass
class ParsedSalary:
    """Structured salary information parsed from free text."""

    minimum: float | None = None
    maximum: float | None = None
    currency: str | None = None
    period: str | None = None
    raw_text: str | None = None


# Currency detection: symbols and ISO-ish codes (word-boundary for codes).
_CURRENCY_SYMBOLS = {
    "£": "GBP",
    "€": "EUR",
    "$": "USD",
}
_CURRENCY_CODE_PATTERNS = [
    (re.compile(r"\bUSD\b|\bUS\$", re.IGNORECASE), "USD"),
    (re.compile(r"\bPKR\b|\bRs\.?\b|\brupees?\b", re.IGNORECASE), "PKR"),
    (re.compile(r"\bGBP\b", re.IGNORECASE), "GBP"),
    (re.compile(r"\bEUR\b", re.IGNORECASE), "EUR"),
]

# Pay-period detection. Normalized lowercase values: hour/day/week/month/year.
# Order matters: more specific/short periods are checked before year.
_PERIOD_PATTERNS = [
    (re.compile(r"hour|hourly|/hr\b|\bhr\b|an hour", re.IGNORECASE), "hour"),
    (re.compile(r"daily|per day|/day\b|a day", re.IGNORECASE), "day"),
    (re.compile(r"weekly|per week|/wk\b|a week", re.IGNORECASE), "week"),
    (re.compile(r"month|monthly|/mo\b|a month|per mo\b", re.IGNORECASE), "month"),
    (re.compile(r"year|yearly|annual|annum|/yr\b|a year|p\.?a\.?", re.IGNORECASE), "year"),
]

# A number, optionally followed by a 'k' thousands suffix.
_NUMBER_PATTERN = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k)?", re.IGNORECASE)


def _detect_currency(text: str) -> str | None:
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code
    for pattern, code in _CURRENCY_CODE_PATTERNS:
        if pattern.search(text):
            return code
    return None


def _detect_period(text: str) -> str | None:
    for pattern, period in _PERIOD_PATTERNS:
        if pattern.search(text):
            return period
    return None


def _extract_numbers(text: str) -> list[float]:
    numbers: list[float] = []
    for match in _NUMBER_PATTERN.finditer(text):
        raw = match.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        if match.group(2):  # 'k' suffix
            value *= 1000
        numbers.append(value)
    return numbers


def parse_salary_text(salary_text: str | None) -> ParsedSalary:
    """Parse a salary string conservatively into a :class:`ParsedSalary`."""
    if salary_text is None or not salary_text.strip():
        return ParsedSalary(raw_text=None)

    raw = salary_text.strip()
    result = ParsedSalary(raw_text=raw)

    currency = _detect_currency(raw)
    result.currency = currency
    result.period = _detect_period(raw)

    numbers = _extract_numbers(raw)

    # Ambiguous unless we have both a currency and at least one number.
    if currency is None or not numbers:
        return result

    lowered = raw.lower()
    has_up_to = "up to" in lowered
    has_from = "from" in lowered and not has_up_to

    if has_up_to:
        result.maximum = numbers[-1]
    elif has_from:
        result.minimum = numbers[0]
    elif len(numbers) >= 2:
        low, high = numbers[0], numbers[1]
        result.minimum = min(low, high)
        result.maximum = max(low, high)
    else:
        # A single stated amount: represent as an exact point (min == max).
        result.minimum = numbers[0]
        result.maximum = numbers[0]

    return result
