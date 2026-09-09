"""A rule is a typed object, and a malformed rule must fail loudly.

Everything checked here is checked at load time, before the service accepts
traffic. A rule file is static data edited by hand; leaving any of it to be
discovered at evaluation time would mean failing while a caller is on the line.
"""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from bayyina.registry.schema import ApprovalStatus, Rule, RuleLogic

MONEY = {"type": "money", "currency": "AED", "required": True, "derived": False}

MINIMAL = {
    "id": "rent_increase.dubai.decree_43_2013",
    "version": 1,
    "jurisdiction": "AE-DU",
    "effective_from": "2013-12-09",
    "effective_to": None,
    "source": {
        "document_id": "dubai_decree_43_2013",
        "title": "Decree No. (43) of 2013",
        "clause": "Article 1",
        "url": "https://dubailand.gov.ae/",
        "verbatim": "Sets maximum permitted percentage increase in property rent.",
    },
    "logic": "banded_percentage",
    "inputs": {
        "current_annual_rent": dict(MONEY),
        "market_average_rent": {**MONEY, "derived": True},
        "proposed_annual_rent": dict(MONEY),
    },
    "bands": [
        {"gap_from": 0.0, "gap_to": 0.10, "max_increase": 0.0},
        {"gap_from": 0.10, "gap_to": None, "max_increase": 0.20},
    ],
    "review_notes": [],
    "approval": {
        "status": "unsigned",
        "approved_by": None,
        "approved_at": None,
        "signature": None,
    },
}

MINIMAL_NOTICE = {
    **deepcopy(MINIMAL),
    "id": "notice_validity.dubai.law_26_2007_a14",
    "logic": "notice_period",
    "inputs": {
        "contract_expiry": {"type": "date", "required": True, "derived": False},
        "notice_served": {"type": "date", "required": True, "derived": False},
    },
    "bands": None,
    "notice": {"required_days": 90},
}


def test_parses_minimal_rule():
    rule = Rule.model_validate(MINIMAL)
    assert rule.id == "rent_increase.dubai.decree_43_2013"
    assert rule.approval.status is ApprovalStatus.UNSIGNED
    assert rule.logic is RuleLogic.BANDED_PERCENTAGE


def test_parses_a_notice_rule():
    rule = Rule.model_validate(MINIMAL_NOTICE)
    assert rule.logic is RuleLogic.NOTICE_PERIOD
    assert rule.notice.required_days == 90
    assert rule.bands is None


def test_body_for_signing_excludes_approval():
    """The signature covers the rule, not its own metadata."""
    body = Rule.model_validate(MINIMAL).body_for_signing()
    assert "approval" not in body
    assert body["version"] == 1


def test_citation_clause_is_mandatory():
    """G1: no verdict without a citation, enforced at the type level."""
    broken = {**MINIMAL, "source": {**MINIMAL["source"], "clause": None}}
    with pytest.raises(ValidationError):
        Rule.model_validate(broken)


def test_verbatim_source_text_is_mandatory():
    """Provenance replaces authority, so the source text must always be present."""
    broken = {**MINIMAL, "source": {**MINIMAL["source"], "verbatim": None}}
    with pytest.raises(ValidationError):
        Rule.model_validate(broken)


def test_unknown_field_is_rejected():
    """A typo in a rule file must fail loudly, never be silently ignored."""
    with pytest.raises(ValidationError):
        Rule.model_validate({**MINIMAL, "band": []})


def test_unknown_field_in_source_is_rejected():
    broken = {**MINIMAL, "source": {**MINIMAL["source"], "clase": "Article 1"}}
    with pytest.raises(ValidationError):
        Rule.model_validate(broken)


# --- The logic name ----------------------------------------------------------


def test_unknown_logic_is_rejected_at_load():
    """A rule naming logic nobody implemented must never reach a caller."""
    with pytest.raises(ValidationError):
        Rule.model_validate({**deepcopy(MINIMAL), "logic": "banded_percentages"})


# --- The parameter block -----------------------------------------------------


def test_a_notice_rule_may_not_carry_a_band_table():
    """It would read as configured and never be consulted."""
    broken = {**deepcopy(MINIMAL_NOTICE), "bands": MINIMAL["bands"]}
    with pytest.raises(ValidationError, match="must not carry"):
        Rule.model_validate(broken)


def test_a_banded_rule_may_not_carry_a_notice_block():
    broken = {**deepcopy(MINIMAL), "notice": {"required_days": 90}}
    with pytest.raises(ValidationError, match="must not carry"):
        Rule.model_validate(broken)


def test_a_notice_rule_requires_its_notice_block():
    broken = {**deepcopy(MINIMAL_NOTICE), "notice": None}
    with pytest.raises(ValidationError, match="requires a 'notice' block"):
        Rule.model_validate(broken)


@pytest.mark.parametrize("bad", [0, -90, 5000])
def test_a_notice_period_must_be_a_plausible_number_of_days(bad):
    """Catches a units mistake: months entered as days, or 90 typed as 9000."""
    broken = {**deepcopy(MINIMAL_NOTICE), "notice": {"required_days": bad}}
    with pytest.raises(ValidationError):
        Rule.model_validate(broken)


# --- Declared inputs ---------------------------------------------------------


def test_a_rule_must_declare_every_input_its_logic_reads():
    broken = deepcopy(MINIMAL)
    del broken["inputs"]["proposed_annual_rent"]
    with pytest.raises(ValidationError, match="does not declare"):
        Rule.model_validate(broken)


def test_a_rule_may_not_declare_an_input_its_logic_never_reads():
    """We would ask a caller for it on the phone and then throw it away."""
    broken = deepcopy(MINIMAL)
    broken["inputs"]["tenant_name"] = {"type": "date", "required": True}
    with pytest.raises(ValidationError, match="never used"):
        Rule.model_validate(broken)


def test_a_money_input_must_name_its_currency():
    broken = deepcopy(MINIMAL)
    broken["inputs"]["current_annual_rent"] = {"type": "money", "required": True}
    with pytest.raises(ValidationError, match="currency"):
        Rule.model_validate(broken)


def test_a_date_input_must_not_carry_a_currency():
    broken = deepcopy(MINIMAL_NOTICE)
    broken["inputs"]["contract_expiry"] = {"type": "date", "currency": "AED"}
    with pytest.raises(ValidationError, match="currency"):
        Rule.model_validate(broken)


def test_an_unknown_input_type_is_rejected():
    broken = deepcopy(MINIMAL)
    broken["inputs"]["current_annual_rent"] = {"type": "amount", "currency": "AED"}
    with pytest.raises(ValidationError):
        Rule.model_validate(broken)


def test_market_dependence_is_read_from_the_declaration():
    """G5 applies to a rule because of what it reads, not because of its name."""
    assert Rule.model_validate(MINIMAL).requires_market_evidence()
    assert not Rule.model_validate(MINIMAL_NOTICE).requires_market_evidence()


# --- Effective dates ---------------------------------------------------------


def test_a_rule_cannot_expire_before_it_begins():
    broken = {**deepcopy(MINIMAL), "effective_to": "2013-01-01"}
    with pytest.raises(ValidationError, match="never in force"):
        Rule.model_validate(broken)


# --- Totality ----------------------------------------------------------------


def test_every_logic_declares_a_parameter_block():
    """Adding a logic without wiring it must fail here, not with a KeyError."""
    from bayyina.registry.schema import _PARAMETER_BLOCK

    assert set(_PARAMETER_BLOCK) == set(RuleLogic)


def test_every_logic_declares_the_inputs_it_reads():
    from bayyina.registry.schema import _CONSUMED_INPUTS

    assert set(_CONSUMED_INPUTS) == set(RuleLogic)


def test_every_declared_parameter_block_is_a_real_field():
    from bayyina.registry.schema import _PARAMETER_BLOCK

    for field in _PARAMETER_BLOCK.values():
        assert field in Rule.model_fields, f"'{field}' is not a field of Rule"
