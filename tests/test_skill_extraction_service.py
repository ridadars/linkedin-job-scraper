"""Tests for deterministic skill extraction."""

from app.services.skill_extraction_service import extract_skills


def test_common_skills_detected() -> None:
    skills = extract_skills("We use Python and PyTorch for Machine Learning.")
    assert "Python" in skills
    assert "PyTorch" in skills
    assert "Machine Learning" in skills


def test_nlp_alias_normalized() -> None:
    skills = extract_skills("Strong NLP background required.")
    assert "Natural Language Processing" in skills
    assert "NLP" not in skills  # alias collapsed


def test_punctuation_skills_detected() -> None:
    skills = extract_skills("Experience with C++, C#, .NET and Node.js.")
    assert "C++" in skills
    assert "C#" in skills
    assert ".NET" in skills
    assert "Node.js" in skills


def test_java_does_not_match_javascript() -> None:
    skills = extract_skills("Strong JavaScript developer wanted.")
    assert "JavaScript" in skills
    assert "Java" not in skills


def test_go_does_not_match_google() -> None:
    skills = extract_skills("We run on Google Cloud infrastructure.")
    assert "Go" not in skills
    assert "Google Cloud" in skills


def test_r_does_not_match_random_words() -> None:
    skills = extract_skills("Great collaboration and creativity required.")
    assert "R" not in skills


def test_c_does_not_match_every_word_with_c() -> None:
    skills = extract_skills("Cloud connectivity and communication.")
    assert "C" not in skills


def test_standalone_c_detected() -> None:
    skills = extract_skills("Proficiency in C and assembly.")
    assert "C" in skills


def test_duplicate_skills_removed() -> None:
    skills = extract_skills("Python python PYTHON Python.")
    assert skills.count("Python") == 1


def test_case_insensitive() -> None:
    assert "Python" in extract_skills("python developer")
    assert "FastAPI" in extract_skills("experience with fastapi")


def test_deterministic_order() -> None:
    text = "TensorFlow, Python, Docker, React"
    assert extract_skills(text) == extract_skills(text)


def test_empty_and_none_input() -> None:
    assert extract_skills("") == []
    assert extract_skills(None) == []


def test_alias_examples_collapse() -> None:
    skills = extract_skills("Experience with LLM, GCP and ML pipelines.")
    assert "Large Language Models" in skills
    assert "Google Cloud" in skills
    assert "Machine Learning" in skills
    assert "LLM" not in skills
    assert "GCP" not in skills
