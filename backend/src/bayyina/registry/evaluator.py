"""Running a rule and recording what it decided.

The evaluator is the only thing in the system that produces a verdict, and an
`EvaluationRecord` is the only shape a verdict can take. Two guardrails are
therefore enforced by this module's types rather than by anyone's care:

  G1  a record cannot be constructed without a citation, so an answer with no
      clause behind it is not a thing the system can represent
  G5  a record in HUMAN_REVIEW_REQUIRED cannot carry a verdict, a computed
      figure, or a confidence number - below the evidence threshold the rule is
      never run, so there is no number to leak into speech or into a document

Everything here is deterministic. No model is consulted, and nothing is
interpreted; the language layer reads these records aloud and never produces one.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bayyina.registry.loader import TamperedRuleError, UnsignedRuleError
from bayyina.registry.schema import ApprovalStatus, InputKind, Rule, RuleInput, RuleLogic
from bayyina.registry.signing import verify_signature
from bayyina.rules_logic import banded_percentage, notice_period
from bayyina.settings import Settings, get_settings


class EvaluationError(ValueError):
    """Base for every reason an evaluation cannot be performed."""


class UnknownRuleError(EvaluationError):
    """No rule with that id is loaded."""


class MissingInputError(EvaluationError):
    """A required input was not supplied."""


class UndeclaredInputError(EvaluationError):
    """An input was supplied that the rule does not read.

    Dropping it silently would leave the caller believing a fact they stated had
    been taken into account.
    """


class InvalidInputError(EvaluationError):
    """An input was supplied in a form the rule cannot use."""


class MissingProvenanceError(EvaluationError):
    """An input arrived with no recorded origin, which breaks G9 lineage."""


class MissingMarketEvidenceError(EvaluationError):
    """A rule reading derived market data was called without the evidence behind it.

    Answering anyway would mean asserting a market comparison without knowing how
    many contracts support it - exactly the false precision G5 exists to prevent.
    """


class OutcomeState(StrEnum):
    """What the service is able to conclude.

    HUMAN_REVIEW_REQUIRED is an outcome, never an error. It means the rule was
    applied honestly and the evidence did not support an answer.
    """

    CLEAR = "CLEAR"
    CLEAR_WITH_CONDITIONS = "CLEAR_WITH_CONDITIONS"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class Condition(StrEnum):
    """Why an answer is contingent, as a key rather than a sentence.

    Keys, so that the voice script and the interface render them through the
    glossary in the caller's own language. `CLEAR_WITH_CONDITIONS` without a
    named condition is the failure this vocabulary prevents: the script and the
    engine once drifted into two different meanings for that state (D-038).
    """

    # The market figure was supplied to us, not computed by us. The arithmetic
    # holds; whether the figure applies to this property is unverified.
    MARKET_AVERAGE_NOT_DERIVED = "market_average_not_derived"

    # We derived it, from fewer comparable contracts than we would like.
    THIN_COMPARABLE_DATA = "thin_comparable_data"


class Citation(BaseModel):
    """The clause a verdict rests on, carried with the verdict.

    Every field has a minimum length. A citation that exists but says nothing
    would pass a null check and still leave the caller with an unsupported
    assertion, which is the failure G1 is meant to make impossible.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    clause: str = Field(min_length=1)
    url: str = Field(min_length=1)
    verbatim: str = Field(min_length=1)

    @classmethod
    def from_rule(cls, rule: Rule) -> Citation:
        """Built from the signed rule, so the words quoted are the words signed."""
        return cls(
            document_id=rule.source.document_id,
            title=rule.source.title,
            clause=rule.source.clause,
            url=rule.source.url,
            verbatim=rule.source.verbatim,
        )


class MarketEvidence(BaseModel):
    """How much registered-contract data stood behind a derived market figure.

    Kept beside the record rather than inside `computed`, so that a
    HUMAN_REVIEW_REQUIRED outcome can still disclose how thin the data was
    without carrying any figure about the caller's rent.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # None means "not derived by us" - the figure was supplied. We cannot state a
    # confidence in evidence we did not gather, and inventing a count so the
    # arithmetic looks better supported would be exactly the fabrication G5
    # exists to prevent.
    contract_count: int | None = Field(default=None, ge=0)
    snapshot_id: str = Field(min_length=1)


class EvaluationRecord(BaseModel):
    """One evaluation, complete enough to reproduce and to defend.

    Immutable by construction: an audit record that can be edited afterwards is
    not an audit record.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    eval_id: str = Field(default_factory=lambda: f"ev_{uuid4().hex}")
    rule_id: str
    rule_version: int
    rule_signature: str = Field(min_length=1)
    review_status: ApprovalStatus
    state: OutcomeState
    verdict: str | None = None
    inputs: dict[str, Any]
    input_sources: dict[str, str]
    computed: dict[str, Any] = Field(default_factory=dict)
    citation: Citation
    evidence: MarketEvidence | None = None
    conditions: list[Condition] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _state_matches_what_was_computed(self) -> EvaluationRecord:
        """G5, enforced by the type.

        A record that says human review is required while carrying a percentage
        is the exact failure the guardrail exists to prevent, so it is made
        impossible to construct rather than forbidden by instruction.
        """
        if self.state is OutcomeState.HUMAN_REVIEW_REQUIRED:
            if self.verdict is not None:
                raise ValueError(
                    f"state is {self.state.value} but a verdict '{self.verdict}' is recorded; "
                    "below the evidence threshold there is nothing to conclude"
                )
            if self.computed:
                raise ValueError(
                    f"state is {self.state.value} but computed figures are recorded "
                    f"({sorted(self.computed)}); no number may be spoken or printed"
                )
            if self.confidence is not None:
                raise ValueError(
                    f"state is {self.state.value} but a confidence of {self.confidence} "
                    "is recorded; a confidence figure is itself a number we cannot stand behind"
                )
            if self.conditions:
                raise ValueError(
                    f"state is {self.state.value} but conditions are recorded; there is no "
                    "answer here for a condition to qualify"
                )
            return self

        if self.verdict is None:
            raise ValueError(f"state is {self.state.value} but no verdict was recorded")

        # A conditional answer must say what the condition is. Without this the
        # state means whatever each surface assumes it means, which is exactly
        # how the script and the engine drifted apart before (D-038).
        if self.state is OutcomeState.CLEAR_WITH_CONDITIONS and not self.conditions:
            raise ValueError(
                f"state is {self.state.value} but no condition is named; a caller cannot "
                "judge an answer whose condition is left implicit"
            )
        if self.state is OutcomeState.CLEAR and self.conditions:
            raise ValueError(
                f"state is {self.state.value} but conditions are recorded "
                f"({[c.value for c in self.conditions]}); a clear answer has none"
            )
        if self.state is OutcomeState.CLEAR and self.confidence is None:
            raise ValueError(f"state is {self.state.value} but no confidence was recorded")
        return self


def _run_banded(rule: Rule, values: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    assert rule.bands is not None  # guaranteed by Rule._validate_parameter_block
    result = banded_percentage.evaluate(
        current_annual_rent=values["current_annual_rent"],
        market_average_rent=values["market_average_rent"],
        proposed_annual_rent=values["proposed_annual_rent"],
        bands=rule.bands,
    )
    return result.verdict, {
        "gap_pct": round(result.gap_pct, 6),
        "band_matched": result.band_matched,
        "max_increase_pct": result.max_increase_pct,
        "max_lawful_rent": result.max_lawful_rent,
        "proposed_increase_pct": round(result.proposed_increase_pct, 6),
    }


def _run_notice(rule: Rule, values: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    assert rule.notice is not None  # guaranteed by Rule._validate_parameter_block
    result = notice_period.evaluate(
        contract_expiry=values["contract_expiry"],
        notice_served=values["notice_served"],
        required_days=rule.notice.required_days,
    )
    return result.verdict, {
        "days_notice": result.days_notice,
        "required_days": result.required_days,
        "shortfall_days": result.shortfall_days,
    }


# Every member of RuleLogic must appear here. A logic added to the schema with no
# evaluator behind it is caught by a test, not by a caller on the phone.
_DISPATCH: dict[RuleLogic, Callable[[Rule, dict[str, Any]], tuple[str, dict[str, Any]]]] = {
    RuleLogic.BANDED_PERCENTAGE: _run_banded,
    RuleLogic.NOTICE_PERIOD: _run_notice,
}


def _coerce_money(name: str, value: Any) -> Decimal:
    if isinstance(value, bool):
        raise InvalidInputError(f"'{name}' is money and cannot be a boolean")
    if isinstance(value, float):
        raise InvalidInputError(
            f"'{name}' was given as a float ({value!r}). Rent is currency, and binary "
            "floating point cannot represent it exactly. Pass a Decimal or a string."
        )
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | str):
        try:
            return Decimal(str(value).strip())
        except InvalidOperation as exc:
            raise InvalidInputError(f"'{name}' is not a valid amount: {value!r}") from exc
    raise InvalidInputError(f"'{name}' is money but arrived as {type(value).__name__}")


def _coerce_date(name: str, value: Any) -> date:
    if isinstance(value, datetime):
        # Notice periods are counted in calendar days, so the time of day is not
        # part of the answer and dropping it is the correct reading.
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise InvalidInputError(f"'{name}' is not an ISO date (YYYY-MM-DD): {value!r}") from exc
    raise InvalidInputError(f"'{name}' is a date but arrived as {type(value).__name__}")


_COERCE: dict[InputKind, Callable[[str, Any], Any]] = {
    InputKind.MONEY: _coerce_money,
    InputKind.DATE: _coerce_date,
}


class Evaluator:
    """Applies signed rules to supplied inputs and returns evaluation records.

    Holds no state beyond the corpus, so it is safe to construct once at boot and
    share across requests.
    """

    def __init__(self, rules: Mapping[str, Rule], *, settings: Settings | None = None) -> None:
        """Refuses to hold a rule that is unsigned or no longer matches its signature.

        G7's second boundary. The loader already checks this at boot, and in
        production the loader is the only way rules are obtained - but the
        evaluator is the thing that produces verdicts, so the invariant belongs
        here too. Without it, any caller assembling rules by hand could obtain a
        verdict, with a citation attached, from logic nobody attested to.
        """
        for rule in rules.values():
            if rule.approval.status is ApprovalStatus.UNSIGNED:
                raise UnsignedRuleError(
                    f"rule '{rule.id}' v{rule.version} is unsigned and cannot produce a "
                    f"verdict. Sign it: python scripts/sign_rule.py rules/<file>.yaml"
                )
            if not verify_signature(rule):
                raise TamperedRuleError(
                    f"rule '{rule.id}' v{rule.version} does not match its recorded "
                    f"signature and cannot produce a verdict. The body was edited after "
                    f"signing. Review the change, then re-sign it."
                )

        self._rules = dict(rules)
        self._settings = settings or get_settings()

    @property
    def rule_ids(self) -> list[str]:
        return sorted(self._rules)

    def evaluate(
        self,
        rule_id: str,
        inputs: Mapping[str, Any],
        input_sources: Mapping[str, str],
        *,
        market: MarketEvidence | None = None,
    ) -> EvaluationRecord:
        """Apply one rule.

        `input_sources` records where each value came from, per field: the string
        `caller_stated` for a fact the caller gave us, or the name of the dataset
        that produced a derived one. This is guardrail G9, and it is required
        rather than optional because a value with no recorded origin cannot be
        defended later.
        """
        rule = self._rules.get(rule_id)
        if rule is None:
            raise UnknownRuleError(
                f"no rule '{rule_id}' is loaded. Available: {', '.join(self.rule_ids) or 'none'}"
            )

        values = self._coerce_inputs(rule, inputs)
        sources = self._provenance(values, input_sources)

        if rule.requires_market_evidence():
            if market is None:
                raise MissingMarketEvidenceError(
                    f"rule '{rule.id}' reads a derived market figure, so it cannot be "
                    "evaluated without the market evidence behind it. Pass "
                    "market=MarketEvidence(contract_count=..., snapshot_id=...)."
                )
            state, confidence, conditions = self._grade(market)
            sources["market_snapshot"] = market.snapshot_id
        else:
            # Nothing derived: the answer rests only on the caller's own facts
            # and the signed rule, so thin market data cannot weaken it.
            state, confidence, conditions = OutcomeState.CLEAR, 1.0, []

        if state is OutcomeState.HUMAN_REVIEW_REQUIRED:
            # The rule is not run at all. This is what makes G5 structural: there
            # is no figure held anywhere that a later step could decide to speak.
            verdict, computed, confidence, conditions = None, {}, None, []
        else:
            verdict, computed = _DISPATCH[rule.logic](rule, values)

        return EvaluationRecord(
            rule_id=rule.id,
            rule_version=rule.version,
            # Never None: __init__ refuses an unsigned rule.
            rule_signature=rule.approval.signature,
            review_status=rule.approval.status,
            state=state,
            verdict=verdict,
            inputs=values,
            input_sources=sources,
            computed=computed,
            citation=Citation.from_rule(rule),
            evidence=market,
            conditions=conditions,
            confidence=confidence,
        )

    def _coerce_inputs(self, rule: Rule, inputs: Mapping[str, Any]) -> dict[str, Any]:
        undeclared = sorted(set(inputs) - set(rule.inputs))
        if undeclared:
            raise UndeclaredInputError(
                f"rule '{rule.id}' does not read {undeclared}. Accepting it would let a "
                f"caller believe a fact they stated had been taken into account. "
                f"It reads: {sorted(rule.inputs)}"
            )

        values: dict[str, Any] = {}
        for name, spec in rule.inputs.items():
            if name not in inputs:
                if spec.required:
                    raise MissingInputError(
                        f"rule '{rule.id}' requires '{name}' and it was not supplied"
                    )
                continue
            values[name] = self._coerce_one(name, spec, inputs[name])
        return values

    @staticmethod
    def _coerce_one(name: str, spec: RuleInput, value: Any) -> Any:
        return _COERCE[spec.type](name, value)

    @staticmethod
    def _provenance(values: Mapping[str, Any], input_sources: Mapping[str, str]) -> dict[str, str]:
        missing = sorted(name for name in values if not input_sources.get(name))
        if missing:
            raise MissingProvenanceError(
                f"no source recorded for {missing}. Every input must say where it came "
                "from - 'caller_stated' or the dataset that derived it - because a value "
                "with no origin cannot be defended on the evidence pack."
            )
        return {name: input_sources[name] for name in values}

    def _grade(self, market: MarketEvidence) -> tuple[OutcomeState, float | None, list[Condition]]:
        """Turn evidence depth into an outcome state and a confidence figure.

        `confidence` is a defined quantity, not an estimate: the proportion of
        the full-confidence comparable threshold that this evidence reaches,
        capped at 1.0. It describes the depth of the market data behind a derived
        input. It is not a probability that the verdict is correct, and nothing
        in the system presents it as one.
        """
        if market.contract_count is None:
            # Supplied to us, not computed by us. The arithmetic is exact; whether
            # the figure applies to this property is the caller's to stand behind,
            # so the answer is conditional and carries no confidence of ours.
            return (
                OutcomeState.CLEAR_WITH_CONDITIONS,
                None,
                [Condition.MARKET_AVERAGE_NOT_DERIVED],
            )

        floor = self._settings.min_contracts_for_answer
        full = self._settings.min_contracts_for_full_confidence

        if market.contract_count < floor:
            return OutcomeState.HUMAN_REVIEW_REQUIRED, None, []
        if market.contract_count < full:
            return (
                OutcomeState.CLEAR_WITH_CONDITIONS,
                round(market.contract_count / full, 4),
                [Condition.THIN_COMPARABLE_DATA],
            )
        return OutcomeState.CLEAR, 1.0, []
