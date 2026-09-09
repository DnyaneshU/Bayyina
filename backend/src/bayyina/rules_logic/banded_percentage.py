"""Decree 43 of 2013, Article 1 — permitted rent increase.

The permitted increase is a function of how far the current rent sits *below*
the market average for a comparable property. The bands come from the signed
rule file; this module only applies them.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from bayyina.registry.schema import Band
from bayyina.rules_logic.errors import RuleInputError, RuleLogicError

FILS = Decimal("0.01")


@dataclass(frozen=True)
class BandedResult:
    """What the rule determined, and the working behind it.

    Everything needed to explain the answer aloud and to print it in the
    evidence pack, so that neither has to recompute anything.
    """

    verdict: str
    gap_pct: float
    band_matched: int
    max_increase_pct: float
    max_lawful_rent: Decimal
    proposed_increase_pct: float


def evaluate(
    current_annual_rent: Decimal,
    market_average_rent: Decimal,
    proposed_annual_rent: Decimal,
    bands: list[Band],
) -> BandedResult:
    """Apply the band table.

    Raises ValueError rather than returning a plausible-looking wrong answer:
    a verdict about someone's rent, delivered with a citation attached, is worse
    when wrong than when withheld.
    """
    if market_average_rent <= 0:
        raise RuleInputError("market_average_rent must be positive")
    if current_annual_rent <= 0:
        raise RuleInputError("current_annual_rent must be positive")

    # How far the current rent sits below the market average. At or above
    # market the gap is zero, which selects the lowest band — a rent already at
    # market does not earn a larger permitted increase.
    raw_gap = (market_average_rent - current_annual_rent) / market_average_rent
    gap = max(0.0, float(raw_gap))

    matched: int | None = None
    max_increase = 0.0
    for index, band in enumerate(bands):
        if band.gap_to is None or gap <= band.gap_to:
            matched = index
            max_increase = band.max_increase
            break

    if matched is None:
        # Only reachable if the corpus has no unbounded top band. The loader
        # cannot detect this, so it is caught here rather than silently
        # defaulting to the most permissive or most restrictive answer.
        raise RuleLogicError(
            f"no band matched a gap of {gap:.4f}; the band table must end with "
            "an unbounded band (gap_to: null)"
        )

    max_lawful_rent = (current_annual_rent * (Decimal("1") + Decimal(str(max_increase)))).quantize(
        FILS, rounding=ROUND_HALF_UP
    )

    proposed_increase_pct = float(
        (proposed_annual_rent - current_annual_rent) / current_annual_rent
    )

    return BandedResult(
        verdict="permitted" if proposed_annual_rent <= max_lawful_rent else "not_permitted",
        gap_pct=gap,
        band_matched=matched,
        max_increase_pct=max_increase,
        max_lawful_rent=max_lawful_rent,
        proposed_increase_pct=proposed_increase_pct,
    )
