"""Phase 4.1: stricter Go/R/C short-skill boundaries."""

import pytest

from app.services.skill_extraction_service import extract_skills


@pytest.mark.parametrize("text", [
    "Go developer",
    "experience with Go",
    "Go programming language",
    "backend services in Go",
    "Golang microservices",
])
def test_go_positive(text: str) -> None:
    assert "Go" in extract_skills(text)


@pytest.mark.parametrize("text", [
    "our go-to-market strategy",
    "we will go live soon",
    "go ahead and apply",
    "We run on Google Cloud",
    "ongoing projects",
])
def test_go_negative(text: str) -> None:
    assert "Go" not in extract_skills(text)


@pytest.mark.parametrize("text", [
    "R programming",
    "R language",
    "experience with R",
    "Python and R",
    "RStudio workflows",
])
def test_r_positive(text: str) -> None:
    assert "R" in extract_skills(text)


@pytest.mark.parametrize("text", [
    "R&D team",
    "recruiter role",
    "required experience",
    "React frontend",
    "random requirements",
])
def test_r_negative(text: str) -> None:
    assert "R" not in extract_skills(text)


@pytest.mark.parametrize("text", [
    "C programming",
    "C language",
    "C/C++ codebase",
    "experience in C",
    "C and C++",
])
def test_c_positive(text: str) -> None:
    assert "C" in extract_skills(text)


@pytest.mark.parametrize("text", [
    "communication skills",
    "computer science",
    "cloud infrastructure",
    "React frontend",
])
def test_c_negative(text: str) -> None:
    assert "C" not in extract_skills(text)


def test_cpp_does_not_duplicate_c() -> None:
    skills = extract_skills("C++ only shop")
    assert "C++" in skills and "C" not in skills


def test_csharp_does_not_duplicate_c() -> None:
    skills = extract_skills("C# developer")
    assert "C#" in skills and "C" not in skills


def test_plain_c_with_cpp() -> None:
    skills = extract_skills("Strong in C and C++")
    assert "C" in skills and "C++" in skills


def test_existing_cases_preserved() -> None:
    assert "JavaScript" in extract_skills("JavaScript developer")
    assert "Java" not in extract_skills("JavaScript developer")
    assert ".NET" in extract_skills("experience with .NET")
    assert "Node.js" in extract_skills("Node.js backend")
