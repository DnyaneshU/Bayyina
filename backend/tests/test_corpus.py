"""The production corpus itself.

These assert facts about the rules we actually ship, not about a fixture. If a
rule file is edited, moved, or loses its provenance, this is what turns red.
"""

from pathlib import Path

from bayyina.registry.loader import load_rules
from bayyina.registry.schema import ApprovalStatus, RuleLogic

RULES = Path(__file__).resolve().parents[1] / "rules"


def test_the_production_corpus_loads():
    assert set(load_rules(RULES)) == {
        "rent_increase.dubai.decree_43_2013",
        "notice_validity.dubai.law_26_2007_a14",
    }


def test_every_rule_is_publicly_verifiable():
    """Provenance replaces authority - so provenance must be complete."""
    for rule in load_rules(RULES).values():
        assert rule.source.clause
        assert rule.source.verbatim.strip()
        assert rule.source.url.startswith("https://")
        assert rule.approval.signature.startswith("sha256:")


def test_we_ship_provisional_and_say_so():
    """We hold no retained counsel. Claiming certified would be a lie told in code."""
    for rule in load_rules(RULES).values():
        assert rule.approval.status is ApprovalStatus.PROVISIONAL


def test_every_rule_records_what_a_reviewer_must_check():
    """A provisional rule with no open questions is a rule nobody examined."""
    for rule in load_rules(RULES).values():
        assert rule.review_notes, f"{rule.id} records no review notes"


def test_the_rent_bands_match_the_decree():
    """Five bands, 0/5/10/15/20 percent, boundaries at each tenth."""
    rule = load_rules(RULES)["rent_increase.dubai.decree_43_2013"]
    assert rule.logic is RuleLogic.BANDED_PERCENTAGE
    assert [band.max_increase for band in rule.bands] == [0.00, 0.05, 0.10, 0.15, 0.20]
    assert [band.gap_to for band in rule.bands] == [0.10, 0.20, 0.30, 0.40, None]


def test_the_notice_period_is_ninety_days_and_lives_in_the_rule():
    """D-027: the law is not an environment variable."""
    rule = load_rules(RULES)["notice_validity.dubai.law_26_2007_a14"]
    assert rule.logic is RuleLogic.NOTICE_PERIOD
    assert rule.notice.required_days == 90


def test_only_the_market_figure_is_derived():
    """Everything else is the caller's own account, and G5 applies only to this."""
    rules = load_rules(RULES)
    rent = rules["rent_increase.dubai.decree_43_2013"]
    notice = rules["notice_validity.dubai.law_26_2007_a14"]

    assert [name for name, spec in rent.inputs.items() if spec.derived] == ["market_average_rent"]
    assert rent.requires_market_evidence()
    assert not notice.requires_market_evidence()
