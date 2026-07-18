"""Centralized technical-skill catalogue.

Keeping the skill dictionary in one place makes it easy to extend without
touching extraction logic. ``SKILL_CATEGORIES`` groups canonical skill display
names; ``SKILL_ALIASES`` maps common alternative spellings/abbreviations to a
single canonical display name so that, for example, ``NLP`` and ``Natural
Language Processing`` collapse to one extracted skill.
"""

SKILL_CATEGORIES: dict[str, list[str]] = {
    "programming_languages": [
        "Python",
        "Java",
        "JavaScript",
        "TypeScript",
        "C",
        "C++",
        "C#",
        "Go",
        "Rust",
        "R",
        "Dart",
        "PHP",
        "Ruby",
        "Kotlin",
        "Swift",
    ],
    "ai_ml": [
        "Artificial Intelligence",
        "Machine Learning",
        "Deep Learning",
        "Natural Language Processing",
        "NLP",
        "Computer Vision",
        "Generative AI",
        "LLM",
        "Large Language Models",
        "RAG",
        "Prompt Engineering",
        "TensorFlow",
        "PyTorch",
        "Keras",
        "Scikit-learn",
        "Hugging Face",
        "LangChain",
        "OpenCV",
        "Pandas",
        "NumPy",
    ],
    "backend": [
        "FastAPI",
        "Django",
        "Flask",
        "Node.js",
        "Express.js",
        "Spring Boot",
        ".NET",
        "REST API",
        "GraphQL",
    ],
    "frontend": [
        "React",
        "Next.js",
        "Vue.js",
        "Angular",
        "HTML",
        "CSS",
        "Tailwind CSS",
        "Bootstrap",
        "Flutter",
    ],
    "databases": [
        "SQL",
        "PostgreSQL",
        "MySQL",
        "SQLite",
        "MongoDB",
        "Redis",
        "Firebase",
        "Supabase",
        "Oracle",
    ],
    "cloud_devops": [
        "AWS",
        "Azure",
        "Google Cloud",
        "GCP",
        "Docker",
        "Kubernetes",
        "Git",
        "GitHub",
        "CI/CD",
        "Linux",
        "Terraform",
    ],
    "data_analytics": [
        "Power BI",
        "Tableau",
        "Matplotlib",
        "Data Analysis",
        "Data Visualization",
        "ETL",
        "Apache Spark",
        "Hadoop",
    ],
    "soft_skills": [
        "Communication",
        "Problem Solving",
        "Teamwork",
        "Leadership",
        "Agile",
        "Scrum",
    ],
}

# Map alternative surface forms to a single canonical display skill. The keys
# are matched (case-insensitively) in text; the value is what gets stored.
SKILL_ALIASES: dict[str, str] = {
    "NLP": "Natural Language Processing",
    "LLM": "Large Language Models",
    "LLMs": "Large Language Models",
    "GCP": "Google Cloud",
    "Gen AI": "Generative AI",
    "GenAI": "Generative AI",
    "AI": "Artificial Intelligence",
    "ML": "Machine Learning",
    "scikit-learn": "Scikit-learn",
    "sklearn": "Scikit-learn",
    "node": "Node.js",
    "nodejs": "Node.js",
    "postgres": "PostgreSQL",
    "k8s": "Kubernetes",
    "reactjs": "React",
    "vue": "Vue.js",
    "nextjs": "Next.js",
    # Short-language aliases / contextual evidence.
    "Golang": "Go",
    "RStudio": "R",
}


def all_catalog_skills() -> list[str]:
    """Return every canonical skill across all categories (de-duplicated)."""
    seen: dict[str, None] = {}
    for skills in SKILL_CATEGORIES.values():
        for skill in skills:
            seen.setdefault(skill, None)
    return list(seen.keys())


def canonical_skill(name: str) -> str:
    """Resolve a surface form to its canonical display skill via aliases."""
    return SKILL_ALIASES.get(name, name)
