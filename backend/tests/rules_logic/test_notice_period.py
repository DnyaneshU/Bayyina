"""Law 26 of 2007, Article 14 — notice of a change to tenancy terms.

Ninety days before expiry. Pure date arithmetic, no market data, and the second
independent ground most callers do not know exists: an invalid notice settles the
matter regardless of whether the increase itself was lawful.
"""

from datetime import date

import pytest

from bayyina.rules_logic.notice_period import evaluate

REQUIRED = 90


@pytest.mark.parametrize(
    ("served", "verdict", "days"),
    [
        (date(2026, 12, 1), "valid", 120),  # comfortably early
        (date(2026, 12, 31), "valid", 90),  # exactly 90 — the boundary
        (date(2027, 1, 1), "invalid", 89),  # one day short
        (date(2027, 2, 1), "invalid", 58),
        (date(2027, 3, 30), "invalid", 1),  # the day before expiry
        (date(2027, 3, 31), "invalid", 0),  # the day of expiry
    ],
)
def test_the_ninety_day_boundary(served, verdict, days):
    result = evaluate(date(2027, 3, 31), served, REQUIRED)
    assert result.days_notice == days
    assert result.verdict == verdict


def test_the_demo_case():
    """The scenario shown on stage: contract ends 30 Nov, notice served 20 Sep.

    71 days against 90 required. If this fails, the demo is broken.
    """
    result = evaluate(date(2026, 11, 30), date(2026, 9, 20), REQUIRED)
    assert result.days_notice == 71
    assert result.shortfall_days == 19
    assert result.verdict == "invalid"


def test_valid_notice_has_no_shortfall():
    result = evaluate(date(2027, 3, 31), date(2026, 12, 1), REQUIRED)
    assert result.shortfall_days == 0


def test_notice_served_after_expiry_is_invalid():
    """Negative notice must not wrap around into a large positive shortfall."""
    result = evaluate(date(2027, 3, 31), date(2027, 4, 30), REQUIRED)
    assert result.days_notice == -30
    assert result.verdict == "invalid"
    assert result.shortfall_days == 120


def test_leap_day_is_counted():
    """2028 is a leap year; February has 29 days and the count must include it."""
    result = evaluate(date(2028, 3, 1), date(2028, 1, 1), REQUIRED)
    assert result.days_notice == 60  # 31 Jan + 29 Feb


def test_required_days_comes_from_the_rule_not_a_constant():
    """A different jurisdiction or a future amendment changes only the rule file."""
    result = evaluate(date(2027, 3, 31), date(2027, 1, 1), required_days=60)
    assert result.required_days == 60
    assert result.verdict == "valid"


@pytest.mark.parametrize("required", [0, -1])
def test_non_positive_required_days_is_rejected(required):
    """A rule encoding 0 days would silently validate every notice."""
    with pytest.raises(ValueError):
        evaluate(date(2027, 3, 31), date(2027, 1, 1), required)
