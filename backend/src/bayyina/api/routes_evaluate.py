"""POST /evaluate - run one signed rule and record what it decided.

The request shape is the agent's tool contract. It is `extra="forbid"`, so a
misspelled field in a tool call fails loudly instead of being dropped and
answered as though the caller had never mentioned it.

**Amounts cross the wire as strings or integers, never as JSON floats.** A rent
is currency; binary floating point cannot represent it exactly, and the one place
where a rounding artefact is unacceptable is the number someone is about to act
on. `"80000.50"` is how a fractional amount is sent.
"""

from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from bayyina.market.comparables import Comparable, ComparableStatus, ComparableStore
from bayyina.market.normalise import area_key
from bayyina.registry.evaluator import EvaluationRecord, MarketEvidence

router = APIRouter()


class MarketEvidenceIn(BaseModel):
    """How much registered-contract data stands behind a derived market figure."""

    model_config = ConfigDict(extra="forbid")

    # Omit when the figure was supplied rather than derived by us. We will not
    # invent a count to make an answer look better supported than it is; the
    # outcome becomes CLEAR_WITH_CONDITIONS and names the condition instead.
    contract_count: int | None = Field(default=None, ge=0)
    snapshot_id: str = Field(min_length=1)


#: What DLD publishes, in the words a caller would use. Two kinds, because two
#: is the split that changes the answer: a 2-bed villa rents for AED 105,000
#: where a 2-bed flat rents for 67,680.
PROPERTY_KINDS = ("flat", "villa")


class DwellingIn(BaseModel):
    """Where the caller lives, so we can derive the market figure ourselves."""

    model_config = ConfigDict(extra="forbid")

    area: str = Field(min_length=1, max_length=120)
    kind: str = Field(pattern="^(flat|villa)$")
    bedrooms: int = Field(ge=0, le=20)


class EvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(min_length=1)

    # `str | int` and not `float`: see the module docstring. A JSON float is
    # refused here rather than silently converted, which is the whole point.
    inputs: dict[str, str | int]

    # G9. Per-field provenance, required rather than optional: a value with no
    # recorded origin cannot be defended on the evidence pack later.
    input_sources: dict[str, str]

    # Required for any rule reading a derived market figure; absent otherwise.
    # The evaluator decides which case applies by reading the rule's own input
    # declarations, so this endpoint does not need to know one rule from another.
    market: MarketEvidenceIn | None = None

    # Supply this *instead of* a market figure and we derive one from registered
    # contracts. Supplying both is refused rather than silently preferring one:
    # the caller would have no way to know which number the answer used.
    dwelling: DwellingIn | None = None


@router.post(
    "/evaluate",
    response_model=EvaluationRecord,
    summary="Run a rule and return the evaluation record",
)
def evaluate(request: Request, body: EvaluateRequest) -> EvaluationRecord:
    """Evaluate one rule.

    Returns **200 with a HUMAN_REVIEW_REQUIRED record** when the evidence does
    not support an answer. That is an outcome, not a failure: returning it as a
    4xx would teach every client to treat the honest case as an error.
    """
    market = MarketEvidence(**body.market.model_dump()) if body.market else None
    inputs = dict(body.inputs)
    sources = dict(body.input_sources)

    if body.dwelling is not None:
        if body.market is not None or "market_average_rent" in inputs:
            raise HTTPException(
                status_code=422,
                detail=(
                    "supply either a market figure or a dwelling to derive one from, "
                    "not both. With both, nobody could tell which number the answer used."
                ),
            )
        found = _comparables(request).lookup(
            _resolvable(body.dwelling.area), body.dwelling.kind, body.dwelling.bedrooms
        )
        if found.status is ComparableStatus.OK:
            # A figure of ours, so it is recorded as ours. G9 is per-field, and
            # this is the field where the distinction matters most.
            inputs["market_average_rent"] = str(found.median_annual_rent)
            sources["market_average_rent"] = "dld_open_rent_contracts_derived"
            market = MarketEvidence(
                contract_count=found.contract_count,
                snapshot_id=found.snapshot_id,
                age_days=found.age_days,
            )
        else:
            # No figure, and none invented. `contract_count` counts contracts we
            # are willing to stand behind, which for a stale release is none of
            # them however many there are - so the evaluator declines to run the
            # rule and the outcome is HUMAN_REVIEW_REQUIRED.
            market = MarketEvidence(contract_count=0, snapshot_id=found.snapshot_id)

    record = request.app.state.evaluator.evaluate(
        body.rule_id,
        inputs,
        sources,
        market=market,
    )

    # G9: written before the response leaves. An evaluation the caller acted on
    # but the log never saw would be exactly the gap the log exists to close.
    request.app.state.audit.append(record)
    return record


def _resolvable(area: str) -> str:
    """Refuse a place-name that normalises to nothing.

    `"   "` and `"!!!"` both pass `min_length=1` and then normalise to the empty
    key, which came back as `unknown_area` — technically true and useless. A
    caller who sent punctuation has made a mistake we can name, and a 422 says
    so where "we don't know that area" implies we looked.
    """
    if not area_key(area):
        raise HTTPException(
            status_code=422,
            detail=(
                "that is not a place name. Try an area as it would be spoken, "
                "for example 'Al Barsha First'. GET /areas lists every one we know."
            ),
        )
    return area


def _comparables(request: Request) -> ComparableStore:
    """The comparables store, or a 503 that says what is missing.

    Market data is optional at boot: the notice rule and a caller-supplied figure
    both work without it. Asking for a derived figure when there is none is a
    503 rather than a 500, because the service is working and one dataset is not
    loaded - and the message says how to load it.
    """
    store = request.app.state.comparables
    if store is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "market comparables are not loaded, so no market figure can be derived. "
                "Supply `market_average_rent` in `inputs` instead, or build the database "
                "with `python scripts/ingest_market.py <release.parquet>`."
            ),
        )
    return store


class AreasResponse(BaseModel):
    """Every area we can resolve, for a caller who has to disambiguate."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    count: int
    areas: list[str]


@router.get(
    "/areas",
    response_model=AreasResponse,
    summary="Every area a comparable can be looked up for",
)
def areas(request: Request) -> AreasResponse:
    """The areas we know, by display name.

    `/comparables` answers `unknown_area` when it cannot resolve a place, and
    without this that is a dead end: the agent has told someone we do not know
    where they live and has nothing to offer next. 184 names is small enough to
    return whole and small enough for an agent to match against.

    Display names, not keys. `area_key` is our normalisation and nobody says
    "al barshaa south third" out loud.
    """
    store = _comparables(request)
    names = store.areas
    return AreasResponse(snapshot_id=store.snapshot_id, count=len(names), areas=names)


@router.get(
    "/comparables",
    response_model=Comparable,
    summary="What places like this rent for, or why we will not say",
)
def comparables(
    request: Request,
    area: str = Query(min_length=1, max_length=120),
    kind: str = Query(pattern="^(flat|villa)$"),
    bedrooms: int = Query(ge=0, le=20),
) -> Comparable:
    """Look up one market figure.

    **Always 200.** `insufficient_data`, `stale` and `unknown_area` are answers,
    not failures - each one is a thing the agent has to say out loud - and
    returning them as 4xx would teach every client to treat our honesty as an
    error. The status is in the body, where the caller must read it.
    """
    return _comparables(request).lookup(_resolvable(area), kind, bedrooms)


class RuleSummary(BaseModel):
    """One rule, as reported by /healthz."""

    id: str
    version: int
    approval_status: str
    signature: str
    clause: str


class HealthResponse(BaseModel):
    """What the service can prove about itself right now.

    `not_yet_checked` is the important field. A health check that reports `ok`
    while silently not looking at half the system is worse than no health check,
    so anything unverified is named rather than omitted.
    """

    status: str
    checks: dict[str, bool]
    not_yet_checked: list[str]

    #: How old the newest contract behind our comparables is, or None when no
    #: market data is loaded. Reported rather than judged: past
    #: `market_snapshot_fresh_days` every answer discloses it, and past
    #: `market_snapshot_max_age_days` `market_data_usable` goes false.
    market_data_age_days: int | None = None
    corpus_signed: bool
    rule_count: int
    rules: list[RuleSummary]


@router.get("/healthz", response_model=HealthResponse, summary="Liveness and corpus state")
def healthz(request: Request) -> HealthResponse:
    """Report corpus state. **Fails if the corpus is not signed** (G7).

    In practice the process cannot reach this route with an unsigned corpus,
    because `create_app` refuses to build. The check is repeated here so that a
    deployment is verifiable from outside, without trusting that it booted the
    way we think it did.
    """
    state = request.app.state
    checks = {
        "corpus_loaded": state.rule_count > 0,
        "corpus_signed": state.corpus_signed,
        "audit_writable": os.access(state.audit.path.parent, os.W_OK),
        # `usable`, not `fresh`. Ageing data is a working state, not a fault:
        # it is quoted with its age disclosed as a named condition. Making
        # freshness a pass/fail check would report `degraded` for eight months
        # of every publication cycle, and a service that is always degraded is
        # a service nobody looks at the health of.
        #
        # What *is* pass/fail is whether anything can be answered at all.
        "market_data_loaded": state.comparables is not None,
        "market_data_usable": (
            state.comparables is not None and not state.comparables.is_stale(date.today())
        ),
    }

    return HealthResponse(
        status="ok" if all(checks.values()) else "degraded",
        checks=checks,
        # Named, not omitted. Each becomes a real check when the thing it
        # describes is wired; market data became two of them at T2.3.
        not_yet_checked=[],
        market_data_age_days=(
            state.comparables.age_days(date.today()) if state.comparables else None
        ),
        corpus_signed=state.corpus_signed,
        rule_count=state.rule_count,
        rules=[
            RuleSummary(
                id=rule.id,
                version=rule.version,
                approval_status=rule.approval.status.value,
                signature=rule.approval.signature,
                clause=rule.source.clause,
            )
            for rule in state.rules.values()
        ],
    )
