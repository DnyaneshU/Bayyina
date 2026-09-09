"""The shape of a rule.

Every model sets `extra="forbid"` so that a typo in a rule file fails loudly at
load time rather than being silently ignored. A silently ignored field in a legal
rule encoding is a wrong verdict waiting to happen.

The same argument drives the rest of this module. A rule file is static data
edited by hand, so every property of it that can be checked before the service
accepts traffic is checked here: the logic name, the parameter block that logic
needs, the inputs it declares, and the band table itself. What is left to fail at
call time is only what genuinely depends on the caller.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RuleLogic(StrEnum):
    """The deterministic functions a rule may name.

    An enum, not a free string. A rule naming logic nobody implemented is
    knowable the moment the file is read; leaving it to dispatch time would turn
    a typo into a failure while a caller is on the line.
    """

    BANDED_PERCENTAGE = "banded_percentage"
    NOTICE_PERIOD = "notice_period"


class InputKind(StrEnum):
    """How an input is interpreted before the rule sees it.

    Money becomes Decimal and never float: a rent is currency, and binary
    floating point cannot represent it exactly.
    """

    MONEY = "money"
    DATE = "date"


class ApprovalStatus(StrEnum):
    """How far a rule encoding has been reviewed.

    UNSIGNED    the loader refuses it and the service does not boot (G7)
    PROVISIONAL loads, and the agent discloses it aloud on every call
    CERTIFIED   a qualified reviewer has signed it
    """

    UNSIGNED = "unsigned"
    PROVISIONAL = "provisional"
    CERTIFIED = "certified"


class RuleSource(BaseModel):
    """Where the rule comes from. Every field is required.

    `clause` and `verbatim` carry guardrail G1: a verdict is never produced
    without a citation, and provenance replaces authority (see DESIGN.md §9), so
    the source text must always be present and quotable.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: str
    title: str
    clause: str
    url: str
    verbatim: str


class RuleApproval(BaseModel):
    """The signing block. Excluded from the signature it carries."""

    model_config = ConfigDict(extra="forbid")

    status: ApprovalStatus = ApprovalStatus.UNSIGNED
    approved_by: str | None = None
    approved_at: datetime | None = None
    signature: str | None = None


class RuleInput(BaseModel):
    """One declared input of a rule.

    The declaration is load-bearing rather than documentation. The evaluator
    coerces values by `type`, refuses a call that omits a required input, and
    reads `derived` to decide whether guardrail G5 applies to this rule at all.
    """

    model_config = ConfigDict(extra="forbid")

    type: InputKind
    currency: str | None = None
    required: bool = True

    # False when the caller states the value, True when we computed it from
    # market data. A rule with any derived input can only be answered as well as
    # the evidence behind it, which is the thing G5 measures.
    derived: bool = False

    @model_validator(mode="after")
    def _currency_matches_type(self) -> RuleInput:
        if self.type is InputKind.MONEY and not self.currency:
            raise ValueError("a money input must name its currency")
        if self.type is not InputKind.MONEY and self.currency:
            raise ValueError(f"a '{self.type.value}' input must not carry a currency")
        return self


class Band(BaseModel):
    """One row of a banded-percentage table.

    `gap_to` of None means the band is unbounded above. Bands are evaluated in
    order, and the first whose upper bound covers the gap matches.

    Every value is a proportion between 0 and 1, never a percentage. The
    likeliest encoding mistake is writing 20 where 0.20 was meant, which would
    permit a 2000% increase with a citation attached, so the bound is enforced
    rather than trusted.
    """

    model_config = ConfigDict(extra="forbid")

    gap_from: float = Field(ge=0.0, le=1.0)
    gap_to: float | None = Field(default=None, ge=0.0, le=1.0)
    max_increase: float = Field(ge=0.0, le=1.0)


class NoticeParams(BaseModel):
    """Parameters of a notice-period rule.

    `required_days` is a property of the law, so it lives here, inside the bytes
    the signature covers - never in configuration, where an operator could change
    what the law says while the signature still verified (D-027).
    """

    model_config = ConfigDict(extra="forbid")

    # The upper bound catches a units mistake - months entered as days, or 90
    # typed as 9000 - the same way the 0-1 bound on bands catches 20 for 0.20.
    required_days: int = Field(gt=0, le=1095)


# Which parameter block each logic needs, and by omission which it must not
# carry. A rule holding the wrong block would look configured and be ignored.
_PARAMETER_BLOCK: dict[RuleLogic, str] = {
    RuleLogic.BANDED_PERCENTAGE: "bands",
    RuleLogic.NOTICE_PERIOD: "notice",
}

# Exactly what each logic function reads. Declared here so that a rule file and
# the code that runs it are proven compatible at load rather than at call time.
_CONSUMED_INPUTS: dict[RuleLogic, frozenset[str]] = {
    RuleLogic.BANDED_PERCENTAGE: frozenset(
        {"current_annual_rent", "market_average_rent", "proposed_annual_rent"}
    ),
    RuleLogic.NOTICE_PERIOD: frozenset({"contract_expiry", "notice_served"}),
}


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: int
    jurisdiction: str
    effective_from: date
    effective_to: date | None = None
    source: RuleSource
    logic: RuleLogic
    inputs: dict[str, RuleInput]
    bands: list[Band] | None = None
    notice: NoticeParams | None = None
    review_notes: list[str] = Field(default_factory=list)
    approval: RuleApproval = Field(default_factory=RuleApproval)

    @model_validator(mode="after")
    def _validate_effective_dates(self) -> Rule:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError(
                f"effective_to ({self.effective_to}) precedes effective_from "
                f"({self.effective_from}); this rule was never in force"
            )
        return self

    @model_validator(mode="after")
    def _validate_parameter_block(self) -> Rule:
        """Exactly the parameter block this logic needs, and no other.

        A notice rule carrying a band table is not a harmless extra: it reads as
        configured, and the value it appears to set is never consulted.
        """
        expected = _PARAMETER_BLOCK[self.logic]
        if getattr(self, expected) is None:
            raise ValueError(f"logic '{self.logic.value}' requires a '{expected}' block")

        for logic, field in _PARAMETER_BLOCK.items():
            if field != expected and getattr(self, field) is not None:
                raise ValueError(
                    f"logic '{self.logic.value}' must not carry a '{field}' block; "
                    f"'{field}' belongs to '{logic.value}' and would be silently ignored"
                )
        return self

    @model_validator(mode="after")
    def _validate_declared_inputs(self) -> Rule:
        """The rule must declare exactly what its logic reads.

        A missing declaration means the evaluator cannot coerce or require the
        value. A surplus one means we ask a caller for something on a phone call
        and then never use it.
        """
        declared = set(self.inputs)
        consumed = set(_CONSUMED_INPUTS[self.logic])

        missing = consumed - declared
        if missing:
            raise ValueError(
                f"logic '{self.logic.value}' reads {sorted(consumed)} but the rule "
                f"does not declare {sorted(missing)}"
            )

        unused = declared - consumed
        if unused:
            raise ValueError(
                f"logic '{self.logic.value}' reads only {sorted(consumed)}; "
                f"{sorted(unused)} would be collected from the caller and never used"
            )
        return self

    @model_validator(mode="after")
    def _validate_band_table(self) -> Rule:
        """Reject a malformed band table at load, not mid-call.

        Band tables are static data in a signed file, so every property of them
        is knowable now. Catching this at evaluation time instead would mean the
        service boots happily and fails while a caller is on the line.
        """
        if self.bands is None:
            return self

        if not self.bands:
            raise ValueError("'bands' must not be empty")

        if self.bands[0].gap_from != 0.0:
            raise ValueError(
                f"bands must start at 0.0 so that a rent at market matches; "
                f"first band starts at {self.bands[0].gap_from}"
            )

        for index, (lower, upper) in enumerate(zip(self.bands, self.bands[1:], strict=False)):
            if lower.gap_to is None:
                raise ValueError(
                    f"band {index} is unbounded but is not last; every band after it is unreachable"
                )
            if lower.gap_to != upper.gap_from:
                raise ValueError(
                    f"bands must be contiguous: band {index} ends at {lower.gap_to} "
                    f"but band {index + 1} starts at {upper.gap_from}"
                )

        if self.bands[-1].gap_to is not None:
            raise ValueError(
                f"the last band must be unbounded (gap_to: null); it ends at "
                f"{self.bands[-1].gap_to}, so any larger gap would match no band"
            )

        return self

    def requires_market_evidence(self) -> bool:
        """True when any declared input is derived rather than caller-stated.

        This is what makes G5 a property of the rule rather than a special case
        in the evaluator: the notice rule reads only dates the caller gives us,
        so thin market data cannot make its answer less reliable.
        """
        return any(spec.derived for spec in self.inputs.values())

    def body_for_signing(self) -> dict[str, object]:
        """The rule minus its approval block - the bytes the signature covers.

        Excluding approval is what makes a signature verifiable: signing writes
        into that block, so including it would change the thing being signed.
        """
        return self.model_dump(mode="json", exclude={"approval"})
