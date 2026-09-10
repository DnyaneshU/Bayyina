"""How a field is named and shaped in a document a resident reads.

`gap_pct` and `max_lawful_rent` are our names for things. **GLOSSARY.md section 1
is explicit that the user-facing word is different**, and that the mapping is
deliberate: "the most they can charge" rather than "legal rent", because the
latter sounds like a fixed official figure and is not.

A pack rendered with internal names would also print `Gap pct: 0.058824`, which
is not a sentence anyone can act on.

**Every field must have an entry here.** A new computed field with no wording
raises rather than falling back to its own name, so adding one forces a decision
about how to say it out loud — which is where that decision belongs, not in a
template a fortnight later.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from .pack import money, written_date


class Shape(StrEnum):
    """How a value is written. Currency and dates follow GLOSSARY section 4."""

    MONEY = "money"
    PERCENT = "percent"
    DATE = "date"
    DAYS = "days"
    PLAIN = "plain"


#: `field name -> (what a person is told it is, how it is written)`.
#:
#: The labels are the strings already approved for the interface in
#: `frontend/src/i18n/locales/en.json`, which the glossary test gates. Using the
#: same words in the pack is the point: someone who checked on the web and then
#: took a printout to a hearing should not meet two vocabularies.
WORDING: dict[str, tuple[str, Shape]] = {
    # --- What the caller told us ---
    "current_annual_rent": ("What you pay now, per year", Shape.MONEY),
    "proposed_annual_rent": ("What they are asking for", Shape.MONEY),
    "market_average_rent": ("Market average", Shape.MONEY),
    "contract_expiry": ("When your contract ends", Shape.DATE),
    "notice_served": ("When they told you", Shape.DATE),
    # --- What the rule worked out: rent increase ---
    "gap_pct": ("How far below the average", Shape.PERCENT),
    "max_increase_pct": ("Permitted increase", Shape.PERCENT),
    "max_lawful_rent": ("The most they can charge", Shape.MONEY),
    "proposed_increase_pct": ("The increase they are asking for", Shape.PERCENT),
    # `band_matched` is an index into the rule's own table. A reader does not
    # need the index; they need to know a band was selected and which one, so it
    # is written as a position rather than as an offset.
    "band_matched": ("Which step of the rule applied", Shape.PLAIN),
    # --- What the rule worked out: notice period ---
    "days_notice": ("Days of notice you were given", Shape.DAYS),
    "required_days": ("Days the rule requires", Shape.DAYS),
    "shortfall_days": ("Days short", Shape.DAYS),
}


#: What a named condition means, in the words the interface already uses.
#: Never the enum value: `market_data_ageing` is a slug, not a sentence.
CONDITION_WORDING: dict[str, str] = {
    "market_average_not_derived": (
        "You gave us the market average. We applied the rule to that figure "
        "exactly, but we have not checked that it is the right average for your "
        "property."
    ),
    "thin_comparable_data": (
        "We found fewer registered contracts for a property like yours than we "
        "would like. That is enough to apply the rule, but it is a thinner "
        "comparison than usual."
    ),
    "market_data_ageing": (
        "Our market figures come from contracts registered up to the date shown "
        "below. Rents in Dubai typically move a few percent over that time, so "
        "treat the comparison as close rather than exact."
    ),
}


# --- Other languages ----------------------------------------------------------
#
# Drafts. The directories under `templates/` carry `_TRANSLATION_STATUS`, so
# `supported_languages()` excludes them and nothing serves them to a caller.
#
# **There is no fallback to English.** A label with no translation raises, the
# same way a field with no wording at all raises. A document that is Arabic prose
# with English labels scattered through it is not a translated document; it is a
# document that looks translated to whoever shipped it and does not to whoever
# reads it.

LABELS: dict[str, dict[str, str]] = {
    "en": {name: wording[0] for name, wording in WORDING.items()},
    # Other languages are added by whoever writes their template. Machine
    # translation is not acceptable here: this document tells someone what their
    # landlord may lawfully charge, and a plausible-sounding mistranslation is
    # worse than no document because the reader cannot tell.
}

CONDITIONS: dict[str, dict[str, str]] = {
    "en": dict(CONDITION_WORDING),
}

#: How a count of days is written. Not a format string with a number dropped in:
#: languages place the unit differently, and a template assuming "N days"
#: produces something a reader notices immediately.
DAYS_WORDING: dict[str, tuple[str, str]] = {
    "en": ("{n} day", "{n} days"),
}


class MissingWordingError(KeyError):
    """A field reached a document with no decision about how to say it."""


def label(name: str, language: str = "en") -> str:
    """What a person is told this field is, in the language they read.

    **No fallback to English.** A missing translation raises, the same way a
    field with no wording at all raises. Arabic prose with English labels
    scattered through it is not a translated document — it is one that looks
    translated to whoever shipped it and does not to whoever reads it.
    """
    if name not in WORDING:
        raise MissingWordingError(
            f"no wording for {name!r}. A field cannot reach a document under its "
            f"internal name - decide what a resident is told it is, and add it to "
            f"WORDING in bayyina/evidence/wording.py."
        )
    try:
        return LABELS[language][name]
    except KeyError:
        raise MissingWordingError(
            f"no {language!r} label for {name!r}. Add it to LABELS in "
            f"bayyina/evidence/wording.py, or the pack is half in one language."
        ) from None


def value(name: str, raw: object, language: str = "en") -> str:
    """The value, written the way GLOSSARY section 4 requires."""
    if raw is None:
        return "—"
    shape = WORDING[name][1] if name in WORDING else Shape.PLAIN
    if shape is Shape.MONEY:
        return money(raw)
    if shape is Shape.PERCENT:
        # Stored as a proportion; spoken as a percentage. One decimal, because
        # the rule's own bands are whole percentage points and more precision
        # would imply the input was that precise.
        return f"{Decimal(str(raw)) * 100:.1f}%"
    if shape is Shape.DATE:
        return written_date(raw, language)  # type: ignore[arg-type]
    if shape is Shape.DAYS:
        count = int(raw)
        singular, plural = DAYS_WORDING.get(language, DAYS_WORDING["en"])
        return (singular if count == 1 else plural).format(n=count)
    if name == "band_matched":
        return f"{int(raw) + 1}"
    return str(raw)


def condition(name: str, language: str = "en") -> str:
    """What a named condition means, in a sentence."""
    if name not in CONDITION_WORDING:
        raise MissingWordingError(
            f"no wording for the condition {name!r}. A condition printed as its "
            f"own slug tells a reader nothing - add it to CONDITION_WORDING."
        )
    try:
        return CONDITIONS[language][name]
    except KeyError:
        raise MissingWordingError(
            f"no {language!r} wording for the condition {name!r}. Add it to "
            f"CONDITIONS in bayyina/evidence/wording.py."
        ) from None
