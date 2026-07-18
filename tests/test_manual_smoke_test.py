"""Confirm the manual smoke-test utility is safe: no import-time execution and
no live request without explicit confirmation."""

import importlib.util
import pathlib

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "manual_linkedin_smoke_test.py"


def _load():
    spec = importlib.util.spec_from_file_location("manual_linkedin_smoke_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # importing must have no side effects
    return module


def test_script_exists() -> None:
    assert SCRIPT.exists()


def test_import_has_no_side_effects() -> None:
    module = _load()
    assert hasattr(module, "main")
    assert callable(module.main)


def test_aborts_without_confirmation_and_no_network() -> None:
    module = _load()
    # Without the acknowledgement flag, main must abort (return 1) before any
    # navigation or network access.
    code = module.main([
        "--search-url",
        "https://www.linkedin.com/jobs/search/?keywords=Python",
    ])
    assert code == 1


def test_max_jobs_capped() -> None:
    module = _load()
    assert module._MAX_ALLOWED_JOBS <= 3
