"""Invariants of the notice-period rule, checked across generated dates."""

from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from bayyina.rules_logic.notice_period import evaluate

dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 12, 31))
required = st.integers(min_value=1, max_value=365)


@given(expiry=dates, served=dates, days=required)
def test_shortfall_is_never_negative(expiry, served, days):
    assert evaluate(expiry, served, days).shortfall_days >= 0


@given(expiry=dates, served=dates, days=required)
def test_valid_exactly_when_notice_meets_the_requirement(expiry, served, days):
    """The verdict is the comparison, with no separate code path to drift."""
    result = evaluate(expiry, served, days)
    assert (result.verdict == "valid") == (result.days_notice >= days)


@given(expiry=dates, served=dates, days=required)
def test_a_shortfall_of_zero_means_valid(expiry, served, days):
    result = evaluate(expiry, served, days)
    assert (result.shortfall_days == 0) == (result.verdict == "valid")


@given(expiry=dates, served=dates, days=required, earlier=st.integers(1, 400))
def test_serving_earlier_never_gives_less_notice(expiry, served, days, earlier):
    """Monotonicity. A sign error in the subtraction would invert this."""
    later = evaluate(expiry, served, days)
    sooner = evaluate(expiry, served - timedelta(days=earlier), days)
    assert sooner.days_notice > later.days_notice
    assert sooner.shortfall_days <= later.shortfall_days
