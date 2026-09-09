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

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

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

    record = request.app.state.evaluator.evaluate(
        body.rule_id,
        body.inputs,
        body.input_sources,
        market=market,
    )

    # G9: written before the response leaves. An evaluation the caller acted on
    # but the log never saw would be exactly the gap the log exists to close.
    request.app.state.audit.append(record)
    return record


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
    }

    return HealthResponse(
        status="ok" if all(checks.values()) else "degraded",
        checks=checks,
        # Named, not omitted. Each of these becomes a real check when the thing
        # it describes is wired: market data lands at T2.1.
        not_yet_checked=["market_snapshot"],
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
