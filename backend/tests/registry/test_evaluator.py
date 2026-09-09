"""The evaluator, run against the production corpus.

Two guardrails are enforced by the record type rather than by discipline:

  G1  an EvaluationRecord cannot exist without a citation
  G5  a record in HUMAN_REVIEW_REQUIRED cannot carry a verdict, a computed
      figure, or a confidence number

Both are tested by trying to construct the forbidden record and failing.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from bayyina.registry.evaluator import (
    Citation,
    EvaluationRecord,
    Evaluator,
    MarketEvidence,
    MissingInputError,
    MissingProvenanceError,
    OutcomeState,
    UndeclaredInputError,
    UnknownRuleError,
)
from bayyina.registry.schema import RuleLogic
from bayyina.settings import Settings

RENT = "rent_increase.dubai.decree_43_2013"
NOTICE = "notice_validity.dubai.law_26_2007_a14"

# The verified demo case: a two-bedroom flat in Al Barsha First. The market
# average is our own figure derived from 5,557 registered contracts.
RENT_INPUTS = {
    "current_annual_rent": Decimal("80000"),
    "market_average_rent": Decimal("87000"),
    "proposed_annual_rent": Decimal("96000"),
}
RENT_SOURCES = {
    "current_annual_rent": "caller_stated",
    "market_average_rent": "dld_open_rent_contracts_derived",
    "proposed_annual_rent": "caller_stated",
}
DEEP_MARKET = MarketEvidence(contract_count=5557, snapshot_id="2026-Q3")

NOTICE_INPUTS = {
    "contract_expiry": date(2026, 12, 31),
    "notice_served": date(2026, 11, 1),
}
NOTICE_SOURCES = {
    "contract_expiry": "caller_stated",
    "notice_served": "caller_stated",
}

# Fixed thresholds, so a developer's local .env cannot change what these assert.
THRESHOLDS = Settings(min_contracts_for_answer=10, min_contracts_for_full_confidence=30)


def _rent(signed_rules, **kwargs) -> EvaluationRecord:
    return Evaluator(signed_rules, settings=THRESHOLDS).evaluate(
        RENT, RENT_INPUTS, RENT_SOURCES, market=kwargs.pop("market", DEEP_MARKET), **kwargs
    )


# --- G1: a verdict always carries its citation -------------------------------


def test_a_verdict_always_carries_a_citation(signed_rules):
    record = _rent(signed_rules)
    assert record.citation.clause == "Article 1"
    assert record.citation.document_id == "dubai_decree_43_2013"
    assert record.verdict == "not_permitted"


def test_the_citation_carries_the_verbatim_clause(signed_rules):
    """Provenance replaces authority, so the words themselves travel with it."""
    record = _rent(signed_rules)
    assert "average rental value of similar units" in record.citation.verbatim


def test_citation_cannot_be_null(signed_rules):
    """G1 enforced by the schema, not by convention."""
    valid = _rent(signed_rules).model_dump()
    with pytest.raises(ValidationError):
        EvaluationRecord(**{**valid, "citation": None})


def test_a_citation_cannot_be_blank(signed_rules):
    """A present-but-empty citation would satisfy a null check and say nothing."""
    with pytest.raises(ValidationError):
        Citation(
            document_id="d",
            title="t",
            clause="",
            url="https://example.test/",
            verbatim="text",
        )


# --- Provenance and lineage (G9) ---------------------------------------------


def test_review_status_is_carried_from_the_rule(signed_rules):
    assert _rent(signed_rules).review_status == "provisional"


def test_rule_signature_is_recorded(signed_rules):
    record = _rent(signed_rules)
    assert record.rule_signature == signed_rules[RENT].approval.signature
    assert record.rule_signature.startswith("sha256:")


def test_rule_version_is_recorded(signed_rules):
    assert _rent(signed_rules).rule_version == 1


def test_input_sources_distinguish_stated_from_derived(signed_rules):
    record = _rent(signed_rules)
    assert record.input_sources["market_average_rent"] == "dld_open_rent_contracts_derived"
    assert record.input_sources["current_annual_rent"] == "caller_stated"


def test_the_market_snapshot_is_recorded(signed_rules):
    """A past answer must reproduce exactly, which needs the snapshot it used."""
    assert _rent(signed_rules).input_sources["market_snapshot"] == "2026-Q3"


def test_every_input_must_carry_a_source(signed_rules):
    """G9 is per-field provenance. A value with no recorded origin breaks it."""
    incomplete = {k: v for k, v in RENT_SOURCES.items() if k != "current_annual_rent"}
    with pytest.raises(MissingProvenanceError, match="current_annual_rent"):
        Evaluator(signed_rules).evaluate(RENT, RENT_INPUTS, incomplete, market=DEEP_MARKET)


def test_each_evaluation_has_its_own_id(signed_rules):
    first, second = _rent(signed_rules), _rent(signed_rules)
    assert first.eval_id != second.eval_id
    assert first.eval_id.startswith("ev_")


def test_created_at_is_timezone_aware_utc(signed_rules):
    created = _rent(signed_rules).created_at
    assert created.tzinfo is not None
    assert created.utcoffset() == datetime.now(UTC).utcoffset()


def test_a_record_is_immutable(signed_rules):
    """An audit record that can be edited after the fact is not an audit record."""
    record = _rent(signed_rules)
    with pytest.raises(ValidationError):
        record.verdict = "permitted"


# --- The computation ---------------------------------------------------------


def test_the_demo_case_computes_the_verified_numbers(signed_rules):
    """Al Barsha First, two-bedroom. Verified against the live dataset."""
    record = _rent(signed_rules)
    assert record.computed["gap_pct"] == pytest.approx(0.0805, abs=0.0001)
    assert record.computed["band_matched"] == 0
    assert record.computed["max_increase_pct"] == 0.0
    assert record.computed["max_lawful_rent"] == Decimal("80000.00")
    assert record.verdict == "not_permitted"


def test_a_permitted_increase_is_reported_as_permitted(signed_rules):
    """The rule says yes as readily as it says no."""
    inputs = {**RENT_INPUTS, "proposed_annual_rent": Decimal("80000")}
    record = Evaluator(signed_rules, settings=THRESHOLDS).evaluate(
        RENT, inputs, RENT_SOURCES, market=DEEP_MARKET
    )
    assert record.verdict == "permitted"


def test_the_notice_rule_needs_no_market_data(signed_rules):
    """G5's escape hatch: a thin-data caller still leaves with this answer."""
    record = Evaluator(signed_rules, settings=THRESHOLDS).evaluate(
        NOTICE, NOTICE_INPUTS, NOTICE_SOURCES
    )
    assert record.state is OutcomeState.CLEAR
    assert record.verdict == "invalid"
    assert record.computed["days_notice"] == 60
    assert record.computed["shortfall_days"] == 30
    assert record.computed["required_days"] == 90
    assert record.citation.clause == "Article 14"


def test_the_notice_period_comes_from_the_signed_rule(signed_rules):
    """Not from settings, not from a constant. D-027, checked end to end."""
    assert signed_rules[NOTICE].notice.required_days == 90
    record = Evaluator(signed_rules).evaluate(NOTICE, NOTICE_INPUTS, NOTICE_SOURCES)
    assert record.computed["required_days"] == 90


def test_every_rule_logic_has_an_evaluator(signed_rules):
    """Adding a logic to the schema without wiring it must fail here, not on a call."""
    from bayyina.registry.evaluator import _DISPATCH

    assert set(_DISPATCH) == set(RuleLogic)


# --- Input handling ----------------------------------------------------------


def test_unknown_rule_raises(signed_rules):
    with pytest.raises(UnknownRuleError):
        Evaluator(signed_rules).evaluate("nope", {}, {})


def test_unknown_rule_names_what_is_available(signed_rules):
    """An operator fixes a typo from the message alone."""
    with pytest.raises(UnknownRuleError, match=RENT.replace(".", r"\.")):
        Evaluator(signed_rules).evaluate("rent_increase.dubai", {}, {})


def test_a_missing_required_input_is_refused(signed_rules):
    partial = {k: v for k, v in RENT_INPUTS.items() if k != "proposed_annual_rent"}
    with pytest.raises(MissingInputError, match="proposed_annual_rent"):
        Evaluator(signed_rules).evaluate(RENT, partial, RENT_SOURCES, market=DEEP_MARKET)


def test_an_undeclared_input_is_refused(signed_rules):
    """Silently dropping an input the caller believed mattered is a wrong answer."""
    extra = {**RENT_INPUTS, "tenant_name": "someone"}
    sources = {**RENT_SOURCES, "tenant_name": "caller_stated"}
    with pytest.raises(UndeclaredInputError, match="tenant_name"):
        Evaluator(signed_rules).evaluate(RENT, extra, sources, market=DEEP_MARKET)


def test_money_given_as_a_string_is_accepted(signed_rules):
    inputs = {k: str(v) for k, v in RENT_INPUTS.items()}
    record = Evaluator(signed_rules, settings=THRESHOLDS).evaluate(
        RENT, inputs, RENT_SOURCES, market=DEEP_MARKET
    )
    assert record.computed["max_lawful_rent"] == Decimal("80000.00")


def test_money_given_as_a_float_is_refused(signed_rules):
    """Rent is currency. Binary floating point cannot hold it exactly."""
    inputs = {**RENT_INPUTS, "current_annual_rent": 80000.0}
    with pytest.raises(ValueError, match="float"):
        Evaluator(signed_rules).evaluate(RENT, inputs, RENT_SOURCES, market=DEEP_MARKET)


def test_a_date_given_as_an_iso_string_is_accepted(signed_rules):
    inputs = {"contract_expiry": "2026-12-31", "notice_served": "2026-11-01"}
    record = Evaluator(signed_rules).evaluate(NOTICE, inputs, NOTICE_SOURCES)
    assert record.computed["days_notice"] == 60


def test_an_unparseable_date_is_refused(signed_rules):
    inputs = {**NOTICE_INPUTS, "notice_served": "last Tuesday"}
    with pytest.raises(ValueError, match="notice_served"):
        Evaluator(signed_rules).evaluate(NOTICE, inputs, NOTICE_SOURCES)


# --- G5: insufficient data over false precision ------------------------------


def test_deep_market_data_is_clear_and_fully_confident(signed_rules):
    record = _rent(signed_rules)
    assert record.state is OutcomeState.CLEAR
    assert record.confidence == 1.0


def test_thin_market_data_answers_with_conditions(signed_rules):
    record = _rent(signed_rules, market=MarketEvidence(contract_count=12, snapshot_id="2026-Q3"))
    assert record.state is OutcomeState.CLEAR_WITH_CONDITIONS
    assert record.confidence < 1.0
    assert record.verdict == "not_permitted"


def test_below_threshold_produces_no_number_at_all(signed_rules):
    """G5. There is nothing to speak because nothing was computed."""
    record = _rent(signed_rules, market=MarketEvidence(contract_count=4, snapshot_id="2026-Q3"))
    assert record.state is OutcomeState.HUMAN_REVIEW_REQUIRED
    assert record.verdict is None
    assert record.computed == {}
    assert record.confidence is None


def test_below_threshold_still_carries_a_citation(signed_rules):
    """Human review is an outcome, not an error. The caller still gets the rule."""
    record = _rent(signed_rules, market=MarketEvidence(contract_count=4, snapshot_id="2026-Q3"))
    assert record.citation.clause == "Article 1"
    assert record.evidence.contract_count == 4


@pytest.mark.parametrize(
    ("count", "state"),
    [
        (9, OutcomeState.HUMAN_REVIEW_REQUIRED),
        (10, OutcomeState.CLEAR_WITH_CONDITIONS),
        (29, OutcomeState.CLEAR_WITH_CONDITIONS),
        (30, OutcomeState.CLEAR),
    ],
)
def test_the_threshold_boundaries_are_explicit(signed_rules, count, state):
    record = _rent(signed_rules, market=MarketEvidence(contract_count=count, snapshot_id="s"))
    assert record.state is state


def test_a_market_rule_without_evidence_is_refused(signed_rules):
    """Answering without knowing how thin the data is would be false precision."""
    with pytest.raises(ValueError, match="market"):
        Evaluator(signed_rules).evaluate(RENT, RENT_INPUTS, RENT_SOURCES)


def test_a_record_cannot_require_review_and_still_carry_a_verdict(signed_rules):
    """G5 at the type level: the forbidden record does not construct."""
    valid = _rent(signed_rules).model_dump()
    with pytest.raises(ValidationError):
        EvaluationRecord(**{**valid, "state": OutcomeState.HUMAN_REVIEW_REQUIRED})


def test_a_record_cannot_be_clear_with_no_verdict(signed_rules):
    """The mirror image: a clear state that answers nothing is incoherent."""
    valid = _rent(signed_rules).model_dump()
    with pytest.raises(ValidationError):
        EvaluationRecord(**{**valid, "verdict": None, "computed": {}})


# --- G7 at the second boundary -----------------------------------------------


def test_the_evaluator_refuses_an_unsigned_rule(signed_rules):
    """The loader checks this at boot. The thing producing verdicts checks it too.

    Without this, any caller assembling rules by hand obtains a verdict, with a
    citation attached, from logic nobody attested to.
    """
    from copy import deepcopy

    from bayyina.registry.loader import UnsignedRuleError
    from bayyina.registry.schema import ApprovalStatus

    rule = deepcopy(signed_rules[RENT])
    rule.approval.status = ApprovalStatus.UNSIGNED
    with pytest.raises(UnsignedRuleError, match=RENT.replace(".", r"\.")):
        Evaluator({rule.id: rule})


def test_the_evaluator_refuses_a_tampered_rule(signed_rules):
    """One band edited after signing. It must not be able to answer at all."""
    from copy import deepcopy

    from bayyina.registry.loader import TamperedRuleError

    rule = deepcopy(signed_rules[RENT])
    rule.bands[0].max_increase = 0.99
    with pytest.raises(TamperedRuleError, match="does not match its recorded signature"):
        Evaluator({rule.id: rule})


def test_one_tampered_rule_blocks_the_whole_evaluator(signed_rules):
    """Partial trust is not a thing. The same stance the loader takes."""
    from copy import deepcopy

    from bayyina.registry.loader import TamperedRuleError

    rules = {rule_id: deepcopy(rule) for rule_id, rule in signed_rules.items()}
    rules[NOTICE].notice.required_days = 1
    with pytest.raises(TamperedRuleError):
        Evaluator(rules)


# --- A conditional answer must name its condition ----------------------------


def test_a_supplied_market_average_is_answered_with_a_named_condition(signed_rules):
    """The web checker's figure is typed by a person, not derived by us.

    Inventing a contract count so the answer looked better supported would be
    the fabrication G5 exists to prevent. We answer, and we say what the answer
    rests on.
    """
    from bayyina.registry.evaluator import Condition

    record = _rent(signed_rules, market=MarketEvidence(snapshot_id="user_supplied"))

    assert record.state is OutcomeState.CLEAR_WITH_CONDITIONS
    assert record.conditions == [Condition.MARKET_AVERAGE_NOT_DERIVED]
    assert record.verdict == "not_permitted"
    # We gathered no evidence, so we state no confidence in it.
    assert record.confidence is None
    assert record.evidence.contract_count is None


def test_thin_data_names_its_condition_too(signed_rules):
    from bayyina.registry.evaluator import Condition

    record = _rent(signed_rules, market=MarketEvidence(contract_count=12, snapshot_id="s"))
    assert record.conditions == [Condition.THIN_COMPARABLE_DATA]


def test_a_clear_answer_carries_no_conditions(signed_rules):
    assert _rent(signed_rules).conditions == []


def test_a_conditional_record_must_name_a_condition(signed_rules):
    """D-038 again, this time as a type. The drift was the state meaning two
    different things on two surfaces; an unnamed condition is how that starts.
    """
    valid = _rent(signed_rules).model_dump()
    with pytest.raises(ValidationError, match="no condition is named"):
        EvaluationRecord(**{**valid, "state": OutcomeState.CLEAR_WITH_CONDITIONS})


def test_a_clear_record_cannot_carry_conditions(signed_rules):
    valid = _rent(signed_rules, market=MarketEvidence(contract_count=12, snapshot_id="s"))
    with pytest.raises(ValidationError, match="a clear answer has none"):
        EvaluationRecord(**{**valid.model_dump(), "state": OutcomeState.CLEAR, "confidence": 1.0})


def test_human_review_carries_no_conditions(signed_rules):
    """There is no answer here for a condition to qualify."""
    record = _rent(signed_rules, market=MarketEvidence(contract_count=4, snapshot_id="s"))
    assert record.conditions == []
