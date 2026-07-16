"""Search normalizer utility tests."""

import pytest

from app.utils.search_normalizer import (
    normalize_keywords,
    normalize_location,
    reject_control_characters,
)


def test_normalize_keywords_trims_and_collapses_spaces() -> None:
    assert normalize_keywords("  Python   Developer  ") == "Python Developer"


def test_normalize_keywords_preserves_cpp() -> None:
    assert normalize_keywords("C++ Engineer") == "C++ Engineer"


def test_normalize_keywords_preserves_csharp() -> None:
    assert normalize_keywords("C# Developer") == "C# Developer"


def test_normalize_keywords_preserves_dotnet() -> None:
    assert normalize_keywords(".NET Developer") == ".NET Developer"


def test_normalize_keywords_preserves_nodejs() -> None:
    assert normalize_keywords("Node.js Engineer") == "Node.js Engineer"


def test_normalize_location_returns_none_for_blank() -> None:
    assert normalize_location("   ") is None


def test_reject_control_characters() -> None:
    with pytest.raises(ValueError):
        reject_control_characters("hello\x07world", "keywords")
