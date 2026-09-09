"""Guardrail G7: the service must not boot on an unsigned or tampered corpus.

These are the tests behind the tamper demo. An operator must be able to fix a
failure from the error message alone.
"""

from copy import deepcopy

import pytest
import yaml

from bayyina.registry.loader import (
    CorpusError,
    EmptyCorpusError,
    MalformedRuleError,
    MissingCorpusError,
    TamperedRuleError,
    UnsignedRuleError,
    load_rules,
)
from bayyina.registry.schema import Rule
from bayyina.registry.signing import rule_digest
from tests.registry.test_schema import MINIMAL


def _unsigned(**overrides) -> dict:
    """A fresh unsigned rule.

    Deep-copied: MINIMAL is shared across three test modules, and these tests
    mutate nested values (`data["bands"][0]`) to simulate tampering. A shallow
    copy would tamper with the shared fixture itself and make later tests pass
    for the wrong reason, depending on execution order.
    """
    return {**deepcopy(MINIMAL), **overrides}


def _signed(data: dict) -> dict:
    signed = {
        **deepcopy(data),
        "approval": {
            "status": "provisional",
            "approved_by": "Bayyina team",
            "approved_at": "2026-09-09T00:00:00Z",
            "signature": None,
        },
    }
    signed["approval"]["signature"] = rule_digest(Rule.model_validate(signed))
    return signed


def _write(tmp_path, data: dict, name: str = "r.v1.yaml"):
    (tmp_path / name).write_text(yaml.safe_dump(data), encoding="utf-8")
    return tmp_path


def test_refuses_an_unsigned_rule(tmp_path):
    with pytest.raises(UnsignedRuleError):
        load_rules(_write(tmp_path, _unsigned()))


def test_refuses_a_tampered_rule(tmp_path):
    """One digit changed after signing. This is the stage demo."""
    data = _signed(_unsigned())
    data["bands"][0]["max_increase"] = 0.99
    with pytest.raises(TamperedRuleError):
        load_rules(_write(tmp_path, data))


def test_loads_a_signed_rule(tmp_path):
    rules = load_rules(_write(tmp_path, _signed(_unsigned())))
    assert "rent_increase.dubai.decree_43_2013" in rules
    assert rules["rent_increase.dubai.decree_43_2013"].version == 1


def test_unsigned_error_names_the_file_and_rule(tmp_path):
    """An operator fixes this from the message alone."""
    with pytest.raises(UnsignedRuleError, match=r"r\.v1\.yaml"):
        load_rules(_write(tmp_path, _unsigned()))
    with pytest.raises(UnsignedRuleError, match=r"rent_increase\.dubai\.decree_43_2013"):
        load_rules(_write(tmp_path, _unsigned()))


def test_tampered_error_names_the_file_and_rule(tmp_path):
    data = _signed(_unsigned())
    data["bands"][0]["max_increase"] = 0.99
    with pytest.raises(TamperedRuleError, match=r"r\.v1\.yaml"):
        load_rules(_write(tmp_path, data))


def test_one_bad_rule_fails_the_whole_corpus(tmp_path):
    """Partial loading would mean the service runs on unreviewed logic."""
    _write(tmp_path, _signed(_unsigned()), "good.v1.yaml")
    other = _unsigned(id="notice_validity.dubai.law_26_2007_a14")
    _write(tmp_path, other, "bad.v1.yaml")
    with pytest.raises(UnsignedRuleError):
        load_rules(tmp_path)


def test_empty_corpus_is_refused_by_default(tmp_path):
    """An empty corpus is the ultimate unverified corpus.

    A service with no rules answers nothing, so booting is worse than failing:
    it looks healthy while being useless. After T1.6 an empty rules/ directory
    means a deleted file, a bad checkout, or a Docker COPY that missed.
    """
    with pytest.raises(EmptyCorpusError):
        load_rules(tmp_path)


def test_empty_corpus_is_allowed_only_when_asked(tmp_path):
    """Explicit opt-in for the window before the first rule is signed."""
    assert load_rules(tmp_path, allow_empty=True) == {}


def test_directory_with_no_yaml_is_also_empty(tmp_path):
    (tmp_path / "notes.txt").write_text("not a rule", encoding="utf-8")
    with pytest.raises(EmptyCorpusError):
        load_rules(tmp_path)


# --- Malformed files: named, not a traceback ---------------------------------


def test_broken_yaml_is_a_named_corpus_error(tmp_path):
    """G7 promises an operator can fix a rejected corpus from the message alone.

    A parser traceback out of pydantic or pyyaml is not that message.
    """
    (tmp_path / "broken.v1.yaml").write_text("id: [unclosed", encoding="utf-8")
    with pytest.raises(MalformedRuleError, match=r"broken\.v1\.yaml"):
        load_rules(tmp_path)


def test_an_empty_file_is_a_named_corpus_error(tmp_path):
    (tmp_path / "empty.v1.yaml").write_text("", encoding="utf-8")
    with pytest.raises(MalformedRuleError, match="contains no rule"):
        load_rules(tmp_path)


def test_a_yaml_list_is_a_named_corpus_error(tmp_path):
    """A rule file must be a mapping. A list parses fine and is not a rule."""
    (tmp_path / "list.v1.yaml").write_text("- id: x\n", encoding="utf-8")
    with pytest.raises(MalformedRuleError, match="contains no rule"):
        load_rules(tmp_path)


def test_a_schema_violation_names_the_field(tmp_path):
    """The operator must not have to read a stack trace to find the typo."""
    broken = _unsigned(logic="nonsense")
    with pytest.raises(MalformedRuleError, match="logic"):
        load_rules(_write(tmp_path, broken))


def test_a_malformed_rule_is_a_corpus_error(tmp_path):
    """verify_corpus.py catches CorpusError. This must be caught by it."""
    (tmp_path / "broken.v1.yaml").write_text("id: [unclosed", encoding="utf-8")
    with pytest.raises(CorpusError):
        load_rules(tmp_path)


def test_a_missing_directory_is_not_reported_as_an_empty_one(tmp_path):
    """The fixes differ, so the messages must.

    A missing directory is a wrong working directory or a container COPY that
    did not happen - the failure T1.9 is most likely to hit. An empty one is a
    deleted file. Reporting both as "no rules found" makes an operator guess.
    """
    with pytest.raises(MissingCorpusError, match="does not exist"):
        load_rules(tmp_path / "no-such-directory")


def test_the_missing_directory_error_shows_the_resolved_path(tmp_path):
    """A relative path in the message is useless when the cwd is the problem."""
    with pytest.raises(MissingCorpusError, match=r"resolved to"):
        load_rules("rules-that-are-not-here")


def test_a_missing_directory_is_refused_even_when_empty_is_allowed(tmp_path):
    """allow_empty forgives an empty corpus, never a missing one."""
    with pytest.raises(MissingCorpusError):
        load_rules(tmp_path / "gone", allow_empty=True)
