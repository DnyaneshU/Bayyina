"""What breaks, what the caller hears, and what the agent does next.

**A webhook that hangs during a live call produces dead air, and the caller hangs
up.** Silence is the worst failure mode a voice product has: the person cannot
tell whether the line dropped, whether they were understood, or whether anyone is
coming back. Every failure below therefore has three things decided in advance —
an HTTP status, a sentence to say out loud, and what the agent does after saying
it — because deciding any of them mid-call means not deciding them.

**The taxonomy lives here, once.** The spoken lines in `agent/scripts/*/`
are generated from this module and a test asserts they are current, so a line
cannot be edited in a script and quietly disagree with what the service does.

Two entries are worth reading twice:

`COMPARABLE_NOT_FOUND` is **200, not an error.** Thin data is an answer — we
found too few registered contracts to stand behind a figure — and returning it as
a 4xx would teach every client to treat our honesty as a fault. G5 exists to make
this case ordinary.

`CORPUS_UNSIGNED` has no status at all. The service does not start, so no call is
answered and there is nothing to say. A number that rings and then gives wrong
answers from an unverified corpus is worse than a number that does not ring.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Failure(StrEnum):
    """Everything that can go wrong between a caller and an answer."""

    COMPARABLE_NOT_FOUND = "comparable_not_found"
    RULE_EVALUATION_ERROR = "rule_evaluation_error"
    TIMEOUT = "timeout"
    DISPATCH_FAILED = "dispatch_failed"
    CORPUS_UNSIGNED = "corpus_unsigned"
    MARKET_DATA_ABSENT = "market_data_absent"
    UNSUPPORTED_LANGUAGE = "unsupported_language"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class Behaviour:
    """One row of the taxonomy."""

    #: The HTTP status the tool returns. `None` means this never reaches HTTP,
    #: because the service is not running.
    status: int | None

    #: What the agent says. English is the source; the other languages are
    #: translations of this exact sentence, not paraphrases of the situation.
    spoken: str

    #: What the agent does after speaking. Prose rather than an enum: it is read
    #: by whoever writes the conversation design, and the shape of the recovery
    #: differs too much between rows to be usefully typed.
    then: str

    #: Whether the caller is handed to a person. The one field a reviewer scans
    #: for, so it is not buried in `then`.
    escalates: bool = False


#: The taxonomy. Ordered as a reader would want it, not alphabetically.
BEHAVIOUR: dict[Failure, Behaviour] = {
    Failure.COMPARABLE_NOT_FOUND: Behaviour(
        status=200,
        spoken=(
            "I could not find enough registered contracts for a property like "
            "yours to give you a reliable average. I can still tell you what the "
            "rule says, and you can put your own figure to it."
        ),
        then=(
            "Continue. Offer the rule without the comparison, or take a figure "
            "the caller supplies. This is the G5 script and it is not an apology."
        ),
    ),
    Failure.MARKET_DATA_ABSENT: Behaviour(
        status=503,
        spoken=(
            "I cannot look up market averages at the moment. If you already know "
            "the average rent for a property like yours, I can work from that."
        ),
        then="Continue on the caller-supplied path. Everything else still works.",
    ),
    Failure.RULE_EVALUATION_ERROR: Behaviour(
        status=500,
        spoken=(
            "Something went wrong on my side. I am not going to guess at your "
            "answer, so let me pass you to someone who can help."
        ),
        then="Escalate immediately. Do not retry: a rule that failed will fail again.",
        escalates=True,
    ),
    Failure.TIMEOUT: Behaviour(
        status=504,
        spoken="Give me one moment while I check that.",
        then=(
            "Filler line, one retry, then escalate. The filler goes out *before* "
            "the retry, not after it, or the caller hears the silence the line "
            "exists to fill."
        ),
        escalates=True,
    ),
    Failure.DISPATCH_FAILED: Behaviour(
        status=502,
        spoken=(
            "I could not text that through. I can read out the key points now, "
            "or try another number."
        ),
        then=(
            "Offer both alternatives and take one. Never silently drop the pack: "
            "the caller was told they would receive it."
        ),
    ),
    Failure.UNSUPPORTED_LANGUAGE: Behaviour(
        status=422,
        spoken=(
            "I can talk this through with you now, but I cannot send you the "
            "written report in this language yet."
        ),
        then=(
            "Continue the call. Do not send an English document instead - an "
            "English pack for a Malayalam reader is a failed delivery, and it is "
            "worse for being invisible."
        ),
    ),
    Failure.RATE_LIMITED: Behaviour(
        status=429,
        spoken="Let me slow down a moment.",
        then="Back off and retry once. If it persists, escalate.",
        escalates=True,
    ),
    Failure.CORPUS_UNSIGNED: Behaviour(
        status=None,
        spoken="",
        then=(
            "Nothing. The service refuses to start, so no call is answered. A "
            "number that rings and then answers from an unverified corpus is "
            "worse than a number that does not ring (G7)."
        ),
    ),
}


class MissingBehaviourError(KeyError):
    """A failure reached a caller with nothing decided about what to say."""


def behaviour(failure: Failure) -> Behaviour:
    try:
        return BEHAVIOUR[failure]
    except KeyError:
        raise MissingBehaviourError(
            f"no behaviour for {failure!r}. A failure with no spoken line is dead "
            f"air on a live call - decide what the agent says and add it to "
            f"BEHAVIOUR in bayyina/api/errors.py."
        ) from None


def as_markdown() -> str:
    """The taxonomy as the script writers read it.

    Generated rather than authored, so a line cannot be edited in a script and
    quietly disagree with what the service actually does. A test asserts the
    checked-in file matches this output.
    """
    lines = [
        "# Failure taxonomy",
        "",
        "<!-- GENERATED from backend/src/bayyina/api/errors.py. Do not edit by",
        "     hand: run `python scripts/render_failures.py` instead. The service",
        "     and the script must not be able to disagree. -->",
        "",
        "A webhook that hangs during a live call produces dead air, and the caller",
        "hangs up. Every failure here has a status, a sentence, and a next step",
        "decided in advance.",
        "",
        "| Failure | Status | The agent says | Then | Escalates |",
        "|---|---|---|---|---|",
    ]
    for failure, row in BEHAVIOUR.items():
        status = "none - service does not start" if row.status is None else str(row.status)
        spoken = row.spoken.replace("\n", " ").strip() or "-"
        lines.append(
            f"| `{failure.value}` | {status} | {spoken} | {row.then} | "
            f"{'yes' if row.escalates else 'no'} |"
        )
    lines.append("")
    return "\n".join(lines)
