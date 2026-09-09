"""Decree 43 of 2013, Article 1 — permitted rent increase.

The permitted increase depends on how far the current rent sits *below* the
market average. Band boundaries are tested on both sides: an off-by-one here is
a wrong answer given to a tenant about money, with a citation attached to make
it look authoritative.
"""

from decimal import Decimal

import pytest

from bayyina.registry.schema import Band
from bayyina.rules_logic.banded_percentage import evaluate

BANDS = [
    Band(gap_from=0.00, gap_to=0.10, max_increase=0.00),
    Band(gap_from=0.10, gap_to=0.20, max_increase=0.05),
    Band(gap_from=0.20, gap_to=0.30, max_increase=0.10),
    Band(gap_from=0.30, gap_to=0.40, max_increase=0.15),
    Band(gap_from=0.40, gap_to=None, max_increase=0.20),
]


@pytest.mark.parametrize(
    ("current", "market", "band", "cap"),
    [
        (Decimal("100000"), Decimal("100000"), 0, 0.00),  # at market
        (Decimal("110000"), Decimal("100000"), 0, 0.00),  # above market
        (Decimal("90000"), Decimal("100000"), 0, 0.00),  # exactly 10% below
        (Decimal("89999"), Decimal("100000"), 1, 0.05),  # a dirham past 10%
        (Decimal("80000"), Decimal("100000"), 1, 0.05),  # exactly 20%
        (Decimal("79999"), Decimal("100000"), 2, 0.10),  # a dirham past 20%
        (Decimal("70000"), Decimal("100000"), 2, 0.10),  # exactly 30%
        (Decimal("69999"), Decimal("100000"), 3, 0.15),  # a dirham past 30%
        (Decimal("60000"), Decimal("100000"), 3, 0.15),  # exactly 40%
        (Decimal("59999"), Decimal("100000"), 4, 0.20),  # a dirham past 40%
        (Decimal("50000"), Decimal("100000"), 4, 0.20),  # 50% below
    ],
)
def test_every_band_boundary(current, market, band, cap):
    result = evaluate(current, market, current, BANDS)
    assert result.band_matched == band
    assert result.max_increase_pct == pytest.approx(cap)


def test_the_demo_case():
    """The scenario shown on stage, using the real market figure.

    Al Barsha First, 2-bed flat: median AED 87,000 from 5,557 registered
    contracts. Tenant pays 80,000, landlord asks 96,000.

    If this test fails, the demo is broken. That is why it is named.
    """
    result = evaluate(Decimal("80000"), Decimal("87000"), Decimal("96000"), BANDS)

    assert result.gap_pct == pytest.approx(0.0805, abs=0.0005)
    assert result.band_matched == 0
    assert result.max_increase_pct == 0.00
    assert result.max_lawful_rent == Decimal("80000.00")
    assert result.proposed_increase_pct == pytest.approx(0.20)
    assert result.verdict == "not_permitted"


def test_rent_above_market_permits_no_increase():
    """A negative gap is clamped to zero, not allowed to select a higher band."""
    result = evaluate(Decimal("120000"), Decimal("100000"), Decimal("125000"), BANDS)
    assert result.gap_pct == 0.0
    assert result.band_matched == 0
    assert result.verdict == "not_permitted"


def test_permitted_when_the_proposal_is_within_the_cap():
    result = evaluate(Decimal("50000"), Decimal("100000"), Decimal("60000"), BANDS)
    assert result.max_lawful_rent == Decimal("60000.00")
    assert result.verdict == "permitted"


def test_proposal_exactly_at_the_cap_is_permitted():
    result = evaluate(Decimal("50000"), Decimal("100000"), Decimal("60000.00"), BANDS)
    assert result.verdict == "permitted"


def test_one_fils_over_the_cap_is_not_permitted():
    """The boundary is the boundary. No tolerance, in either direction."""
    result = evaluate(Decimal("50000"), Decimal("100000"), Decimal("60000.01"), BANDS)
    assert result.verdict == "not_permitted"


def test_a_reduction_is_permitted():
    """Nothing in the rule prevents a landlord charging less."""
    result = evaluate(Decimal("80000"), Decimal("87000"), Decimal("75000"), BANDS)
    assert result.verdict == "permitted"


def test_max_lawful_rent_is_rounded_to_fils():
    """33,333.33 sits 33.3% below 50,000 -> band 3 -> 15%.

    33333.33 * 1.15 = 38333.3295, which must round half-up to 38333.33.
    Money is Decimal throughout; a float here would produce 38333.329999...
    """
    result = evaluate(Decimal("33333.33"), Decimal("50000"), Decimal("33333.33"), BANDS)
    assert result.band_matched == 3
    assert result.max_lawful_rent == Decimal("38333.33")


@pytest.mark.parametrize(
    ("current", "market"),
    [
        (Decimal("50000"), Decimal("0")),
        (Decimal("50000"), Decimal("-1")),
        (Decimal("0"), Decimal("100000")),
        (Decimal("-1"), Decimal("100000")),
    ],
)
def test_non_positive_inputs_are_rejected(current, market):
    """Refuse to compute rather than return a plausible-looking wrong answer."""
    with pytest.raises(ValueError):
        evaluate(current, market, Decimal("60000"), BANDS)


def test_malformed_band_table_is_rejected():
    """A corpus whose top band is bounded could leave a gap unmatched."""
    bounded = [Band(gap_from=0.00, gap_to=0.10, max_increase=0.00)]
    with pytest.raises(ValueError):
        evaluate(Decimal("50000"), Decimal("100000"), Decimal("60000"), bounded)
