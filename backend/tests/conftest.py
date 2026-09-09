"""Fixtures shared across the suite."""

from pathlib import Path

import pytest

from bayyina.registry.loader import load_rules
from bayyina.registry.schema import Rule

RULES_DIR = Path(__file__).resolve().parents[1] / "rules"


@pytest.fixture(scope="session")
def signed_rules() -> dict[str, Rule]:
    """The production corpus, loaded and signature-verified.

    Deliberately not a stub. These tests assert what the deployed service will
    actually answer, so if a rule file is edited without re-signing, or a band
    boundary moves, the evaluator tests fail rather than passing against a
    convenient fiction.
    """
    return load_rules(RULES_DIR)
