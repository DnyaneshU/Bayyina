"""Provenance: the rule we applied, laid open beside the text it came from.

**Guardrail G9 in public.** Every verdict cites a clause; this is where a person
follows that citation and checks it. The page carries the verbatim source, our
encoding of it in words, the signature over the bytes, and the approval status -
so that trust in an answer rests on something a reader can inspect rather than
on our say-so (DESIGN.md section 9: provenance replaces authority).

Two decisions worth stating, because both could reasonably have gone the other
way:

**The signature is recomputed, never echoed.** Reading `approval.signature` out
of the file and printing it would attest to nothing: a tampered file carries a
tampered signature block quite happily. `signature_matches` is the result of
hashing the rule body *now* and comparing. The corpus is verified at boot and
again in CI, so this should never be false in a running service - and if it ever
is, the page says so rather than presenting a forgery as provenance.

**The review notes are published, not hidden.** They record where our encoding
interprets a text that is ambiguous - the decree states whole-percentage bands
and leaves 10-11% undefined, and we had to choose. Publishing that is the
difference between provenance and marketing, and it is the single most useful
thing on the page for the reviewer this exists to serve.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict

from ..registry.explain import EncodedStep, explain
from ..registry.schema import ApprovalStatus, Rule
from ..registry.signing import rule_digest

router = APIRouter()


class RuleCitation(BaseModel):
    """Where the text comes from."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    title: str
    clause: str
    url: str


class RuleInputSummary(BaseModel):
    """One declared input, and whether the caller supplies it or we derive it."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: str
    currency: str | None
    required: bool

    #: True when we compute the value from market data rather than being told
    #: it. The distinction drives G5 and it is the first thing a reviewer asks
    #: about a figure, so it is on the page rather than implied.
    derived: bool


class ProvenanceSummary(BaseModel):
    """One rule, enough to choose it from a list."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    version: int
    title: str
    clause: str
    approval_status: ApprovalStatus
    signature: str | None
    signature_matches: bool


class ProvenanceListing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int
    rules: list[ProvenanceSummary]


class ProvenanceDetail(BaseModel):
    """Everything needed to check one encoding against its source."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    version: int
    jurisdiction: str
    effective_from: date
    effective_to: date | None

    citation: RuleCitation

    #: The clause as published. Never summarised, never trimmed: the comparison
    #: this page exists for is between this text and `encoded` below it.
    verbatim: str

    logic: str
    encoded: list[EncodedStep]
    inputs: list[RuleInputSummary]

    #: Where our encoding had to interpret, and what a reviewer must confirm.
    review_notes: list[str]

    approval_status: ApprovalStatus
    approved_by: str | None
    approved_at: datetime | None
    signature: str | None

    #: Recomputed from the rule body on this request.
    signature_matches: bool

    #: Present whenever `signature_matches` is false, naming what we computed so
    #: the discrepancy can be investigated rather than merely reported.
    computed_signature: str | None = None


def _matches(rule: Rule) -> bool:
    return bool(rule.approval.signature) and rule.approval.signature == rule_digest(rule)


def _summary(rule: Rule) -> ProvenanceSummary:
    return ProvenanceSummary(
        rule_id=rule.id,
        version=rule.version,
        title=rule.source.title,
        clause=rule.source.clause,
        approval_status=rule.approval.status,
        signature=rule.approval.signature,
        signature_matches=_matches(rule),
    )


@router.get(
    "/provenance",
    response_model=ProvenanceListing,
    summary="Every rule in the corpus, with its approval state",
)
def provenance_index(request: Request) -> ProvenanceListing:
    """The corpus, in one list.

    Small by design. A registry a reader cannot hold in their head is a registry
    they will not audit, and two rules that are checkable beat twenty that are
    taken on trust.
    """
    rules: dict[str, Rule] = request.app.state.rules
    summaries = [_summary(rule) for _, rule in sorted(rules.items())]
    return ProvenanceListing(count=len(summaries), rules=summaries)


@router.get(
    "/provenance/{rule_id}",
    response_model=ProvenanceDetail,
    summary="One rule: the source text, our encoding of it, and the signature",
    responses={404: {"description": "No such rule in the corpus"}},
)
def provenance_detail(
    request: Request,
    rule_id: str = Path(min_length=1, max_length=200),
) -> ProvenanceDetail:
    """One rule, laid open.

    404 for an unknown id rather than an empty page: a citation that resolves to
    a blank document reads as "this rule exists and says nothing", which is the
    opposite of what an absent rule means.
    """
    rules: dict[str, Rule] = request.app.state.rules
    rule = rules.get(rule_id)
    if rule is None:
        known = ", ".join(sorted(rules)) or "none"
        raise HTTPException(
            status_code=404,
            detail=f"no rule {rule_id!r} in the corpus. Known rules: {known}",
        )

    matches = _matches(rule)
    return ProvenanceDetail(
        rule_id=rule.id,
        version=rule.version,
        jurisdiction=rule.jurisdiction,
        effective_from=rule.effective_from,
        effective_to=rule.effective_to,
        citation=RuleCitation(
            document_id=rule.source.document_id,
            title=rule.source.title,
            clause=rule.source.clause,
            url=rule.source.url,
        ),
        verbatim=rule.source.verbatim,
        logic=rule.logic.value,
        encoded=explain(rule),
        inputs=[
            RuleInputSummary(
                name=name,
                type=spec.type.value,
                currency=spec.currency,
                required=spec.required,
                derived=spec.derived,
            )
            for name, spec in sorted(rule.inputs.items())
        ],
        review_notes=list(rule.review_notes),
        approval_status=rule.approval.status,
        approved_by=rule.approval.approved_by,
        approved_at=rule.approval.approved_at,
        signature=rule.approval.signature,
        signature_matches=matches,
        computed_signature=None if matches else rule_digest(rule),
    )
