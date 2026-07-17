"""Deterministic, dictionary-based skill extraction.

Matches catalogue skills (and their aliases) against free text using
boundary-aware regular expressions so that short skills never produce substring
false positives — ``R`` does not match "random", ``Go`` does not match
"Google", ``Java`` does not match "JavaScript", and ``C`` does not match every
word containing a "c". Skills with punctuation (``C++``, ``C#``, ``.NET``,
``Node.js``, ``CI/CD``) are detected correctly.

No LLM or paid API is used. Output is de-duplicated and returned in a stable
catalogue order for reproducibility.
"""

import re

from app.skill_catalog import (
    SKILL_ALIASES,
    SKILL_CATEGORIES,
    all_catalog_skills,
    canonical_skill,
)
from app.utils.search_normalizer import collapse_spaces

# Characters that, when present in a skill, mean the token carries its own
# punctuation (C++, C#, .NET, Node.js, CI/CD, Scikit-learn). Such skills use a
# plain alphanumeric boundary so the punctuation is matched literally.
_SPECIAL_CHARS = set("+#/.-")


def _boundaries(term: str) -> tuple[str, str]:
    """Return (left, right) boundary assertions appropriate for the term.

    Plain alphanumeric skills additionally forbid a neighbouring ``+`` or ``#``
    so that ``C`` never matches inside ``C++`` or ``C#`` — while still allowing a
    trailing period (sentence punctuation) so ``NLP.`` matches. Skills that
    already contain punctuation use a plain alphanumeric boundary.
    """
    if any(char in _SPECIAL_CHARS for char in term):
        return r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])"
    return r"(?<![A-Za-z0-9+#])", r"(?![A-Za-z0-9+#])"


def _compile(term: str) -> re.Pattern[str]:
    """Compile a boundary-aware, case-insensitive pattern for a term."""
    left, right = _boundaries(term)
    return re.compile(left + re.escape(term) + right, re.IGNORECASE)


# Precompile patterns once at import time.
_CATALOG_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (skill, _compile(skill)) for skill in all_catalog_skills()
]
_ALIAS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (canonical_skill(alias), _compile(alias)) for alias in SKILL_ALIASES
]

# Reverse index: canonical skill -> category (first category wins).
_SKILL_CATEGORY: dict[str, str] = {}
for _category, _skills in SKILL_CATEGORIES.items():
    for _skill in _skills:
        _SKILL_CATEGORY.setdefault(_skill, _category)


def extract_skills(text: str | None) -> list[str]:
    """Return the de-duplicated catalogue skills mentioned in ``text``.

    Order is deterministic (catalogue order), independent of where terms appear.
    """
    if not text:
        return []

    haystack = collapse_spaces(text)
    matched: set[str] = set()

    for skill, pattern in _CATALOG_PATTERNS:
        if pattern.search(haystack):
            matched.add(canonical_skill(skill))

    for canonical, pattern in _ALIAS_PATTERNS:
        if pattern.search(haystack):
            matched.add(canonical)

    # Stable catalogue order, collapsing aliases to their canonical skill.
    ordered: list[str] = []
    seen: set[str] = set()
    for skill in all_catalog_skills():
        canonical = canonical_skill(skill)
        if canonical in matched and canonical not in seen:
            seen.add(canonical)
            ordered.append(canonical)
    return ordered


def extract_skills_by_category(text: str | None) -> dict[str, list[str]]:
    """Return matched skills grouped by their catalogue category."""
    skills = extract_skills(text)
    grouped: dict[str, list[str]] = {}
    for skill in skills:
        category = _SKILL_CATEGORY.get(canonical_skill(skill), "other")
        grouped.setdefault(category, []).append(skill)
    return grouped
