"""The normalisation rules, as pure functions.

These are kept out of SQL deliberately. Each rule is applied by building a small
lookup table from the source's *distinct* values — 213 area names, 35 sub-types —
and joining it back, so the rule has exactly one implementation, that
implementation is unit-testable, and nothing has to be kept in step between
Python and a query.
"""

from __future__ import annotations

import re

# --- Property scope ----------------------------------------------------------

# An allowlist, not a denylist. `property_usage_en = 'Residential'` includes
# 1,120,410 labour-camp contracts and 8,418 staff-accommodation contracts, which
# are whole-block agreements rather than tenancies. Their medians are AED 504,000
# and AED 2,274,500 — left in, a caller in an industrial area is told the market
# rate for their flat is in the hundreds of thousands.
#
# A denylist would admit whatever category DLD adds next. This is the list of
# things a resident actually rents and calls us about; anything else is out of
# scope until someone looks at it.
#: What a resident actually distinguishes, and what a comparable is grouped by.
#:
#: Two kinds, because two is the split that changes the answer: a 2-bed villa
#: rents for AED 105,000 where a 2-bed flat rents for 67,680. Nobody phoning in
#: describes their home as a "Complex Villa", so DLD's eleven labels collapse to
#: the words a caller would use.
DWELLING_KINDS: dict[str, str] = {
    "flat": "flat",
    "studio": "flat",  # the property type, spelt 'Studio ' with a trailing space
    "penthouse": "flat",
    "villa": "villa",
    "complex villas": "villa",  # a villa compound is a villa
    "arabian house": "villa",
}

#: Scope, derived from the same mapping. A type is in scope exactly when we know
#: what kind of home it is - one list, so the two cannot disagree.
DWELLING_PROPERTY_TYPES: frozenset[str] = frozenset(DWELLING_KINDS)

# Categories we have seen and knowingly excluded. Kept explicitly so that a
# category DLD introduces *later* is distinguishable from one we already judged.
NON_DWELLING_PROPERTY_TYPES: frozenset[str] = frozenset(
    {
        "labor camps",
        "staff accommodation",
        "portacabin",
        "building",
        "hotel",
        "hotel apartments",
        "mezzanine",
        "villa addendum",
        "shop",
        "store",
        "office",
        "land parking",
    }
)

KNOWN_PROPERTY_TYPES: frozenset[str] = DWELLING_PROPERTY_TYPES | NON_DWELLING_PROPERTY_TYPES


def dwelling_kind(property_type: str | None) -> str | None:
    """The kind of home a DLD property type describes, or None if it is not one.

    >>> dwelling_kind("Flat")
    'flat'
    >>> dwelling_kind("Studio ")
    'flat'
    >>> dwelling_kind("Complex Villas")
    'villa'
    >>> dwelling_kind("Labor Camps") is None
    True
    """
    if property_type is None:
        return None
    return DWELLING_KINDS.get(property_type.strip().casefold())


def is_dwelling(property_type: str | None) -> bool:
    """Whether this property type is somewhere a household rents and lives."""
    return dwelling_kind(property_type) is not None


# --- Bedrooms ----------------------------------------------------------------

# There is no bedrooms column. The count lives inside a free-text sub-type whose
# spacing and capitalisation are inconsistent: '1bed room+Hall', '2 bed
# rooms+hall', '15 bed room+hall'. A maid's room is not a bedroom, so
# '2 bed rooms+hall+Maids Room' is a 2-bed.
_BEDROOM_PATTERN = re.compile(r"^(\d+)\s*bed", re.IGNORECASE)

# Studios have no bedroom, which is a real category and not a missing value.
_STUDIO = "studio"

# Dwellings whose sub-type carries no bedroom count at all. They cannot be placed
# in an (area, type, bedrooms) cell, so they are out of scope rather than
# rejected — there is nothing wrong with the row, we just cannot compare it.
UNCOUNTABLE_SUB_TYPES: frozenset[str] = frozenset({"duplex", "penthouse", "room"})


def bedrooms_from_sub_type(sub_type: str | None) -> int | None:
    """Bedrooms encoded in a DLD sub-type, or None if it carries no count.

    >>> bedrooms_from_sub_type("Studio")
    0
    >>> bedrooms_from_sub_type("1bed room+Hall")
    1
    >>> bedrooms_from_sub_type("2 bed rooms+hall+Maids Room")
    2
    >>> bedrooms_from_sub_type("Room in labor Camp") is None
    True
    """
    if sub_type is None:
        return None
    text = sub_type.strip()
    if text.casefold() == _STUDIO:
        return 0
    match = _BEDROOM_PATTERN.match(text)
    return int(match.group(1)) if match else None


# --- Areas -------------------------------------------------------------------

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_REPEATED_CHARACTER = re.compile(r"(.)\1+")


def area_key(area_name: str) -> str:
    """A stable key for an area name, tolerant of DLD's spelling drift.

    Case-folds, collapses punctuation, and collapses runs of a repeated
    character. That last rule is what makes 'Al Barshaa South Third' reachable
    when a caller types 'Al Barsha South Third' — the doubled vowel is DLD's,
    and the resident has no way to know it.

    Measured on the 2026-02-26 release: 213 area names collapse to 212 keys, and
    the single merge is 'AL QUSAIS' (area 305, 148,665 contracts) with
    'Al Qusais' (area 241, 11 contracts) — the same neighbourhood recorded twice.

    **No two genuinely different neighbourhoods may share a key.** That is not a
    property of the rule, it is a property of the rule *and this dataset*, so it
    is asserted against the real file rather than assumed. Merging Al Barsha
    First into Al Barsha Second would corrupt both, silently.

    >>> area_key("Al Barshaa South Third") == area_key("Al Barsha South Third")
    True
    >>> area_key("AL QUSAIS") == area_key("Al Qusais")
    True
    >>> area_key("Al Barsha First") == area_key("Al Barsha Second")
    False
    """
    key = _NON_ALPHANUMERIC.sub(" ", area_name.strip().casefold())
    key = _REPEATED_CHARACTER.sub(r"\1", key)
    return " ".join(key.split())
