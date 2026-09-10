"""The artifact a resident carries into a hearing.

**Guardrail G10: this states, it never argues.** The pack accepts evaluation
records and lays out what they contain. It composes nothing, weighs nothing, and
recommends nothing — the difference between "your rent sits 5.9% below the
market average, so the published limit is 0%" and "you have a strong case" is
the difference between information and legal advice, and only one of those we
are allowed to give.

That is enforced by the input type, not by care. `build_pack` accepts
`EvaluationRecord` and nothing else, so there is no seam through which a
sentence somebody wrote — or a model generated — can enter the document path.
**No language model may be imported anywhere under this package**, and a test
walks the import graph to prove it rather than trusting the reviewer.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..registry.evaluator import EvaluationRecord

#: Where the templates live, one directory per language.
TEMPLATE_ROOT = Path(__file__).parent / "templates"

#: The template each language must provide before a pack can be produced in it.
PACK_TEMPLATE = "pack.txt.j2"


class EvidenceError(Exception):
    """Base class for every failure in building an evidence pack."""


class UnsupportedLanguageError(EvidenceError):
    """Asked for a language we have no template for.

    Deliberately **not** a fallback to English. The plan is explicit that an
    English PDF for a Malayalam caller is a failed delivery, and a silent
    fallback is how that happens without anybody noticing: the call completes,
    the pack sends, and the person cannot read the thing they were told to take
    to the Rental Dispute Centre.
    """


def supported_languages() -> tuple[str, ...]:
    """Languages a pack can actually be produced in, derived from the templates.

    Derived, never listed. A language becomes supported by a translated template
    file appearing on disk — the same shape as the interface's language switcher
    (D-065), so there is no second place to remember and no way to advertise a
    language nothing can render.
    """
    if not TEMPLATE_ROOT.is_dir():
        return ()
    return tuple(
        sorted(
            directory.name
            for directory in TEMPLATE_ROOT.iterdir()
            if directory.is_dir() and (directory / PACK_TEMPLATE).is_file()
        )
    )


class EvidencePack(BaseModel):
    """One resident's case, assembled from records and nothing else."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_id: str = Field(default_factory=lambda: f"pk_{uuid4().hex}")

    #: How the caller is identified to themselves — a case reference they can
    #: quote. Never a phone number: the pack may be printed and left on a desk.
    caller_ref: str = Field(min_length=1, max_length=64)

    language: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    records: tuple[EvaluationRecord, ...] = Field(min_length=1)

    #: `rule_id` to the signature of the exact rule version that produced each
    #: answer. Lifted out of the records so a reader can check the encoding
    #: against the provenance page without reading the whole document.
    signatures: dict[str, str] = Field(default_factory=dict)

    @field_validator("records")
    @classmethod
    def _only_records(cls, records: tuple[EvaluationRecord, ...]):
        """G10, one layer below `build_pack`, so nothing can bypass it.

        Pydantic would coerce a compatible mapping into an `EvaluationRecord`
        here, which is the one door left open — a dict assembled by hand, or by
        a model, would arrive looking exactly like a verdict we computed.
        """
        for record in records:
            if not isinstance(record, EvaluationRecord):
                raise TypeError(
                    f"an evidence pack is built from evaluation records, not "
                    f"{type(record).__name__}. Nothing that was written rather "
                    f"than computed may enter the document path (G10)."
                )
        return records

    def render_text(self) -> str:
        """The pack as plain text. PDF rendering is T2.5."""
        # Imported here rather than at module scope: `render` needs this type,
        # and the cycle is not worth a shared module for one function.
        from .render import render_text

        return render_text(self)


def build_pack(
    records: object,
    caller_ref: str,
    language: str,
) -> EvidencePack:
    """Assemble an evidence pack, or refuse.

    Raises `TypeError` for anything that is not an evaluation record, and
    `UnsupportedLanguageError` for a language we cannot render.
    """
    if isinstance(records, EvaluationRecord):
        # One record is a common call and an easy mistake; accept it rather than
        # iterating the fields of a model.
        records = [records]
    if isinstance(records, (str, bytes)) or not hasattr(records, "__iter__"):
        raise TypeError(
            f"an evidence pack is built from evaluation records, not "
            f"{type(records).__name__} (G10)."
        )

    collected = tuple(records)
    for record in collected:
        if not isinstance(record, EvaluationRecord):
            raise TypeError(
                f"an evidence pack is built from evaluation records, not "
                f"{type(record).__name__}. Nothing that was written rather than "
                f"computed may enter the document path (G10)."
            )
    if not collected:
        raise EvidenceError("an evidence pack with no findings is not a document")

    available = supported_languages()
    if language not in available:
        raise UnsupportedLanguageError(
            f"no evidence template for {language!r}. Available: "
            f"{', '.join(available) or 'none'}. A pack is not produced in a "
            f"language the reader cannot read, and English is not a fallback — "
            f"see docs/GLOSSARY.md section 6."
        )

    return EvidencePack(
        caller_ref=caller_ref,
        language=language,
        records=collected,
        signatures={record.rule_id: record.rule_signature for record in collected},
    )


# --- Presentation helpers -----------------------------------------------------
#
# Kept here rather than in the templates so that every surface formats a rent the
# same way. The glossary is explicit: written **AED 80,000**, never "80K", never
# "Dhs"; dates written **30 November 2026**, never numeric, because the ambiguity
# between conventions produces wrong verdicts.


def money(amount: Decimal | int | float | str | None) -> str:
    """`AED 80,000` — the written form from GLOSSARY section 4."""
    if amount is None:
        return "—"
    value = Decimal(str(amount))
    whole = value.quantize(Decimal(1)) if value == value.to_integral_value() else value
    return f"AED {whole:,}"


def written_date(value: date | datetime | str | None) -> str:
    """`30 November 2026`. Never numeric."""
    if value is None:
        return "—"
    if isinstance(value, str):
        value = date.fromisoformat(value)
    if isinstance(value, datetime):
        value = value.date()
    return f"{value.day} {value.strftime('%B')} {value.year}"
