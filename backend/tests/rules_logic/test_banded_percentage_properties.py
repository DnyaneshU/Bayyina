"""Invariants of the band evaluation, checked across generated inputs.

The example-based tests cover the boundaries we thought of. These cover the ones
we did not. For a rules engine, a wrong answer *is* the product failure, and a
sign error or an off-by-one in numeric code is exactly the class of bug that
survives hand-written tests.
"""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from bayyina.registry.schema import Band
from bayyina.rules_logic.banded_percentage import evaluate

BANDS = [
    Band(gap_from=0.00, gap_to=0.10, max_increase=0.00),
    Band(gap_from=0.10, gap_to=0.20, max_increase=0.05),
    Band(gap_from=0.20, gap_to=0.30, max_increase=0.10),
    Band(gap_from=0.30, gap_to=0.40, max_increase=0.15),
    Band(gap_from=0.40, gap_to=None, max_increase=0.20),
]

# Realistic Dubai annual rents, in whole dirhams.
rents = st.integers(min_value=1_000, max_value=10_000_000).map(Decimal)


@given(current=rents, market=rents, proposed=rents)
def test_gap_is_always_a_proportion(current, market, proposed):
    """Never negative, never above 1. A negative gap would select a higher band."""
    result = evaluate(current, market, proposed, BANDS)
    assert 0.0 <= result.gap_pct <= 1.0


@given(market=rents, extra=st.integers(min_value=0, max_value=1_000_000), proposed=rents)
def test_rent_at_or_above_market_never_earns_an_increase(market, extra, proposed):
    """The invariant that protects the tenants who are already overcharged.

    A rent at or above market has no gap, so it sits in the lowest band and no
    increase is permitted. A sign error here would invert the answer for exactly
    the people most likely to be paying too much.
    """
    result = evaluate(market + Decimal(extra), market, proposed, BANDS)
    assert result.gap_pct == 0.0
    assert result.band_matched == 0
    assert result.max_increase_pct == 0.0


@given(current=rents, market=rents, proposed=rents)
def test_the_lawful_ceiling_is_never_below_the_current_rent(current, market, proposed):
    """No band may reduce what the tenant already pays."""
    result = evaluate(current, market, proposed, BANDS)
    assert result.max_lawful_rent >= current


@given(current=rents, market=rents, proposed=rents)
def test_verdict_agrees_with_the_ceiling(current, market, proposed):
    """The verdict is exactly the comparison, with no separate code path."""
    result = evaluate(current, market, proposed, BANDS)
    expected = "permitted" if proposed <= result.max_lawful_rent else "not_permitted"
    assert result.verdict == expected


@given(market=rents, a=rents, b=rents)
def test_a_larger_gap_never_permits_a_smaller_increase(market, a, b):
    """Monotonicity: the further below market, the more (or equally) permitted.

    This is the property a mis-ordered or overlapping band table would break,
    and it holds across the whole table rather than at the boundaries we listed.
    """
    lower, higher = (a, b) if a >= b else (b, a)  # lower rent -> larger gap
    result_small_gap = evaluate(lower, market, lower, BANDS)
    result_large_gap = evaluate(higher, market, higher, BANDS)
    assert result_large_gap.max_increase_pct >= result_small_gap.max_increase_pct


@given(current=rents, market=rents, proposed=rents)
def test_a_proposal_at_the_ceiling_is_always_permitted(current, market, proposed):
    """The boundary belongs to the tenant's side, consistently."""
    result = evaluate(current, market, proposed, BANDS)
    at_ceiling = evaluate(current, market, result.max_lawful_rent, BANDS)
    assert at_ceiling.verdict == "permitted"
