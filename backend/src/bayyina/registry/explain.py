"""The encoded rule, written out so a lawyer can check it against the source.

A provenance page is only worth having if the encoding it shows is **the
encoding that runs**. A hand-written summary beside a band table is a second
copy of the law that drifts the first time someone edits one and not the other,
and it drifts silently, because nothing executes prose.

So every sentence here is generated from the same fields the evaluator reads.
`banded_percentage` matches the first band whose `gap_to` covers the gap, upper
bound inclusive; that is what these sentences say, in those words, derived from
that list. Change the table and the page changes with it. There is no path by
which the page can describe a rule we do not apply.

What this is not: an explanation of the *law*. It is an explanation of **our
encoding of it**, placed beside the verbatim clause so the two can be compared.
The difference matters — the review notes on each rule exist precisely because
those two things are not always the same, and a reviewer's job is to find where.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .schema import Rule, RuleLogic


class UnexplainableLogicError(RuntimeError):
    """A logic kind reached the provenance page with no way to describe it.

    Raised rather than falling back to a generic sentence. A rule whose encoding
    cannot be stated in words cannot be reviewed, and a page that quietly says
    nothing about it would look like a page that had nothing to say.
    """


class EncodedStep(BaseModel):
    """One row of the encoded rule: the case, and what follows from it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Position in the table, from 1. The evaluator reports `band_matched` as a
    #: zero-based index; a reader counting rows on a page starts at one, and the
    #: evidence pack already writes it as "step 2" for the same reason.
    step: int

    #: The circumstance, as the code tests for it.
    condition: str

    #: What the rule then permits or determines.
    outcome: str


def percent(proportion: float) -> str:
    """`0.05` becomes `5%`.

    Proportions throughout, percentages only at the edge. The schema bounds
    every band to 0-1 exactly because writing 20 where 0.20 was meant would
    permit a 2000% increase, so the conversion happens here, once, at the point
    where a person reads it.
    """
    value = proportion * 100
    if abs(value - round(value)) < 1e-9:
        return f"{round(value)}%"
    return f"{value:.1f}%"


def _banded_percentage(rule: Rule) -> list[EncodedStep]:
    """The band table, row by row.

    The lower bound of each row is the previous row's upper bound. `gap_from`
    carries the same number and the schema refuses a file where the two
    disagree, but the evaluator reads only `gap_to`, so these sentences are
    built from `gap_to` as well. A page describing a bound nothing enforces
    would be worse than no page.
    """
    assert rule.bands is not None  # guaranteed by the schema for this logic
    steps: list[EncodedStep] = []
    previous: float = 0.0

    for index, band in enumerate(rule.bands):
        if band.gap_to is None:
            condition = f"the rent is more than {percent(previous)} below the market average"
        elif index == 0:
            # The first row is closed at the bottom: a rent at or above the
            # market average has a gap of zero and matches here.
            condition = (
                f"the rent is up to {percent(band.gap_to)} below the market average, "
                f"including exactly {percent(band.gap_to)}"
            )
        else:
            condition = (
                f"the rent is more than {percent(previous)} and up to "
                f"{percent(band.gap_to)} below the market average, including "
                f"exactly {percent(band.gap_to)}"
            )

        if band.max_increase == 0:
            outcome = "no increase is permitted"
        else:
            outcome = (
                f"the increase may not exceed {percent(band.max_increase)} of the current rent"
            )

        steps.append(EncodedStep(step=index + 1, condition=condition, outcome=outcome))
        if band.gap_to is not None:
            previous = band.gap_to

    return steps


def _notice_period(rule: Rule) -> list[EncodedStep]:
    """Two outcomes, stated as the code tests for them."""
    assert rule.notice is not None  # guaranteed by the schema for this logic
    days = rule.notice.required_days
    return [
        EncodedStep(
            step=1,
            condition=(
                f"the notice reached the tenant {days} days or more before the contract ends"
            ),
            outcome="the notice period is satisfied",
        ),
        EncodedStep(
            step=2,
            condition=(
                f"the notice reached the tenant fewer than {days} days before the contract ends"
            ),
            outcome=("the notice period is not satisfied, and the shortfall is reported in days"),
        ),
    ]


#: One writer per logic kind. Registered rather than branched, so that adding a
#: logic without a description fails at the door instead of producing a rule
#: that runs and cannot be reviewed.
_WRITERS = {
    RuleLogic.BANDED_PERCENTAGE: _banded_percentage,
    RuleLogic.NOTICE_PERIOD: _notice_period,
}


def explain(rule: Rule) -> list[EncodedStep]:
    """The rule's encoded logic, in order, as sentences."""
    try:
        writer = _WRITERS[rule.logic]
    except KeyError:
        # `getattr`, not `.value`: whatever reached here is by definition not a
        # logic we know, so it need not be a member of the enum. An error path
        # that raises a different error hides the diagnostic it exists to give.
        name = getattr(rule.logic, "value", rule.logic)
        raise UnexplainableLogicError(
            f"no description for the logic {name!r}. A rule that "
            f"cannot be stated in words cannot be reviewed - add a writer to "
            f"bayyina/registry/explain.py before shipping the logic."
        ) from None
    return writer(rule)
