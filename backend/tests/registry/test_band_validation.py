"""A malformed band table must fail at load, not mid-call.

Catching it at evaluation means the service boots happily and then fails while a
caller is on the line. Band tables are static data in a signed file, so every
property of them is knowable at load time and belongs there — the same place
G7 already rejects unsigned rules.
"""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from bayyina.registry.schema import Rule
from tests.registry.test_schema import MINIMAL, MINIMAL_NOTICE

FULL_BANDS = [
    {"gap_from": 0.00, "gap_to": 0.10, "max_increase": 0.00},
    {"gap_from": 0.10, "gap_to": 0.20, "max_increase": 0.05},
    {"gap_from": 0.20, "gap_to": 0.30, "max_increase": 0.10},
    {"gap_from": 0.30, "gap_to": 0.40, "max_increase": 0.15},
    {"gap_from": 0.40, "gap_to": None, "max_increase": 0.20},
]


def _rule(bands) -> dict:
    return {**deepcopy(MINIMAL), "bands": bands}


def test_the_real_band_table_is_accepted():
    assert len(Rule.model_validate(_rule(FULL_BANDS)).bands) == 5


def test_last_band_must_be_unbounded():
    """Otherwise a gap above the top bound matches nothing at all."""
    bounded = deepcopy(FULL_BANDS)
    bounded[-1]["gap_to"] = 0.50
    with pytest.raises(ValidationError, match="unbounded"):
        Rule.model_validate(_rule(bounded))


def test_bands_must_start_at_zero():
    """A rent exactly at market has a gap of zero and must match something."""
    gapped = deepcopy(FULL_BANDS)
    gapped[0]["gap_from"] = 0.05
    with pytest.raises(ValidationError, match="start at 0"):
        Rule.model_validate(_rule(gapped))


def test_bands_must_be_contiguous():
    """A hole between bands is a gap value with no defined answer."""
    holed = deepcopy(FULL_BANDS)
    holed[1]["gap_from"] = 0.12  # band 0 ends at 0.10, leaving 0.10-0.12 undefined
    with pytest.raises(ValidationError, match="contiguous"):
        Rule.model_validate(_rule(holed))


def test_bands_must_not_overlap():
    """Overlapping bands make the answer depend on evaluation order."""
    overlapping = deepcopy(FULL_BANDS)
    overlapping[1]["gap_from"] = 0.05
    with pytest.raises(ValidationError, match="contiguous"):
        Rule.model_validate(_rule(overlapping))


def test_empty_band_table_is_rejected():
    with pytest.raises(ValidationError):
        Rule.model_validate(_rule([]))


def test_banded_logic_requires_bands():
    """A banded rule with no table would refuse every caller at runtime."""
    with pytest.raises(ValidationError, match="bands"):
        Rule.model_validate(_rule(None))


def test_non_banded_logic_does_not_require_bands():
    """Notice validity is date arithmetic; it has no band table."""
    rule = Rule.model_validate(deepcopy(MINIMAL_NOTICE))
    assert rule.bands is None


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_gap_bounds_must_be_a_proportion(bad):
    """A gap is a proportion of market rent: 0 to 1, never a percentage like 20."""
    out_of_range = deepcopy(FULL_BANDS)
    out_of_range[0]["gap_to"] = bad
    with pytest.raises(ValidationError):
        Rule.model_validate(_rule(out_of_range))


def test_max_increase_of_twenty_percent_is_written_as_zero_point_two():
    """The likeliest encoding mistake: 20 instead of 0.20.

    Left unvalidated, that permits a 2000% increase with a citation attached.
    """
    mistake = deepcopy(FULL_BANDS)
    mistake[-1]["max_increase"] = 20
    with pytest.raises(ValidationError):
        Rule.model_validate(_rule(mistake))
