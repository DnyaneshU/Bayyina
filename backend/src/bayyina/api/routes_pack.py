"""The artifact a resident takes away.

`/evidence-pack` takes the same body as `/evaluate`, evaluates it, and returns
the pack as a downloadable document. It does **not** accept an evaluation
record.

That is deliberate and it is the whole security property of this endpoint.
`build_pack` refuses anything that is not an `EvaluationRecord`, but a record
posted over HTTP would arrive already looking like one - a verdict nobody
computed, carrying our citation, our signature and our name on it. So the record
is produced here, from inputs, by the same evaluator every other answer comes
from. There is no request shape that lets a caller choose what the document says.

**Plain text, not PDF.** T2.5 renders the PDF, and the Malayalam glyph work it
needs is real. The text pack is complete and correct today, and a person can
print it, so it ships now rather than waiting behind a font problem.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from ..evidence.pack import UnsupportedLanguageError, build_pack, supported_languages
from ..store.idempotency import Idempotency, IdempotencyConflictError
from .routes_evaluate import EvaluateRequest, evaluate_request

router = APIRouter()

#: Anything outside this is stripped from the download filename. A caller
#: reference reaches us from a voice agent and ends up in a `Content-Disposition`
#: header, which is a header-injection and path-traversal surface if taken as
#: given. The reference inside the document is unmodified; only the filename is
#: narrowed.
#: Dots are excluded along with everything else: we append the extension
#: ourselves, so a dot in the reference buys nothing and `../..` arriving in a
#: suggested filename is not something to hand to a download manager.
_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


class PackRequest(EvaluateRequest):
    """An evaluation, plus who it is for and what language they read."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "summary": "A pack for one evaluation",
                    "description": (
                        "The same body as `/evaluate`, plus a reference and a "
                        "language. Send `Idempotency-Key` as a header and a retry "
                        "replays this document rather than producing a second."
                    ),
                    "value": {
                        "rule_id": "rent_increase.dubai.decree_43_2013",
                        "inputs": {
                            "current_annual_rent": "80000",
                            "proposed_annual_rent": "96000",
                            "market_average_rent": "87000",
                        },
                        "input_sources": {
                            "current_annual_rent": "caller_stated",
                            "proposed_annual_rent": "caller_stated",
                            "market_average_rent": "user_supplied",
                        },
                        "market": {"snapshot_id": "user_supplied"},
                        "caller_ref": "BYN-4821",
                        "language": "en",
                    },
                }
            ]
        },
    )

    #: A case reference the person can quote. Never a phone number: the pack
    #: gets printed and left on a desk.
    caller_ref: str = Field(min_length=1, max_length=64)

    language: str = Field(min_length=2, max_length=8)


class PackLanguages(BaseModel):
    """Which languages a pack can actually be produced in."""

    model_config = ConfigDict(extra="forbid")

    languages: list[str]


@router.get(
    "/evidence-pack/languages",
    response_model=PackLanguages,
    summary="Languages a pack can be produced in",
)
def pack_languages() -> PackLanguages:
    """Derived from the templates on disk, never from a list.

    A client that offers a language we cannot render produces a caller who
    chooses Malayalam and receives English, which the plan counts as a failed
    delivery. This endpoint is how a client avoids offering it.
    """
    return PackLanguages(languages=list(supported_languages()))


@router.post(
    "/evidence-pack",
    response_class=PlainTextResponse,
    summary="The evidence pack for one evaluation, as a document",
    responses={
        200: {"content": {"text/plain": {}}, "description": "The pack"},
        422: {"description": "A language we have no template for"},
    },
)
def evidence_pack(
    request: Request,
    body: PackRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> PlainTextResponse:
    """Evaluate, then render the pack for that evaluation.

    A `HUMAN_REVIEW_REQUIRED` outcome still produces a pack. That is not a
    consolation prize: it is the document that says which facts were missing and
    which rule would have applied, and it is the one a person takes to the Rental
    Dispute Centre when we could not answer. Refusing to produce it would leave
    the caller with nothing precisely when they need something.

    Send an `Idempotency-Key` and a retry replays the first document rather than
    producing a second one. The stored bytes are returned, not a fresh render
    that happens to match — so a pack quoted in a hearing is the pack we made.
    """
    store = Idempotency(request.app.state.store)
    fingerprint_of = body.model_dump_json()

    if idempotency_key is not None:
        try:
            earlier = store.stored(
                idempotency_key, operation="evidence_pack", request=fingerprint_of
            )
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if earlier is not None:
            return _as_download(earlier, body.caller_ref, replayed=True)

    record = evaluate_request(request, body)

    try:
        pack = build_pack([record], body.caller_ref, body.language)
    except UnsupportedLanguageError as exc:
        # 422, not 500. The request named a language we do not have; that is
        # something the caller can act on, and the message says what we do have.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    text = pack.render_text()
    if idempotency_key is not None:
        store.remember(
            idempotency_key,
            call_id=body.caller_ref,
            operation="evidence_pack",
            request=fingerprint_of,
            response=text,
        )
    return _as_download(text, body.caller_ref, replayed=False)


def _as_download(text: str, caller_ref: str, *, replayed: bool) -> PlainTextResponse:
    reference = _FILENAME_SAFE.sub("-", caller_ref).strip("-") or "case"
    return PlainTextResponse(
        text,
        headers={
            "Content-Disposition": f'attachment; filename="bayyina-{reference}.txt"',
            # The pack quotes a decree and states an outcome. A stale copy served
            # from a proxy after a rule is re-signed would be a document citing a
            # version we no longer run.
            "Cache-Control": "no-store",
            # Stated rather than inferred. A client that cannot tell a replay
            # from a fresh document will eventually count one as two.
            "Idempotent-Replay": "true" if replayed else "false",
        },
    )
