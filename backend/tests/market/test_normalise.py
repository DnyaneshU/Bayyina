"""The normalisation rules on their own, with no database in the way."""

from __future__ import annotations

import doctest

import pytest

from bayyina.market import normalise
from bayyina.market.normalise import (
    DWELLING_PROPERTY_TYPES,
    KNOWN_PROPERTY_TYPES,
    NON_DWELLING_PROPERTY_TYPES,
    area_key,
    bedrooms_from_sub_type,
    is_dwelling,
)


def test_the_documented_examples_are_true():
    """The docstrings are the shortest description of these rules, so they are
    executed rather than trusted."""
    results = doctest.testmod(normalise, verbose=False)
    assert results.failed == 0
    assert results.attempted > 0


# --- Bedrooms -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("sub_type", "expected"),
    [
        ("Studio", 0),
        ("studio", 0),
        ("1bed room+Hall", 1),  # no space after the digit
        ("2 bed rooms+hall", 2),  # spaced, plural
        ("15 bed room+hall", 15),  # spaced, singular, two digits
        ("2 bed rooms+hall+Maids Room", 2),  # a maid's room is not a bedroom
        ("  3 bed rooms+hall  ", 3),
        ("Room in labor Camp", None),
        ("Penthouse", None),
        ("Duplex", None),
        ("Office", None),
        (None, None),
    ],
)
def test_bedrooms_are_read_out_of_the_sub_type(sub_type, expected):
    """There is no bedrooms column. The count lives inside free text whose
    spacing and capitalisation DLD does not hold constant."""
    assert bedrooms_from_sub_type(sub_type) == expected


def test_a_studio_is_zero_bedrooms_and_not_a_missing_value():
    """The distinction the type system will not make for us. Studios are 966,061
    contracts and disproportionately what a lower-income caller rents."""
    assert bedrooms_from_sub_type("Studio") == 0
    assert bedrooms_from_sub_type("Studio") is not None


# --- Scope --------------------------------------------------------------------


@pytest.mark.parametrize(
    "property_type", ["Flat", "Villa", "Studio ", "Complex Villas", "Arabian House"]
)
def test_places_people_live_are_in_scope(property_type):
    """'Studio ' carries a trailing space in the release, on 73,139 rows."""
    assert is_dwelling(property_type)


@pytest.mark.parametrize(
    "property_type",
    ["Labor Camps", "Staff Accommodation", "Portacabin", "Office", "Shop", "Hotel", None],
)
def test_places_people_are_housed_are_not(property_type):
    assert not is_dwelling(property_type)


def test_scope_is_an_allowlist_and_the_exclusions_are_written_down():
    """Both halves are named so that a category appearing in a later release is
    distinguishable from one we already judged and set aside."""
    assert DWELLING_PROPERTY_TYPES.isdisjoint(NON_DWELLING_PROPERTY_TYPES)
    assert KNOWN_PROPERTY_TYPES == DWELLING_PROPERTY_TYPES | NON_DWELLING_PROPERTY_TYPES
    assert all(name == name.casefold() for name in KNOWN_PROPERTY_TYPES)


# --- Areas --------------------------------------------------------------------


def test_dlds_doubled_vowel_does_not_hide_a_neighbourhood():
    """DLD writes 'Al Barshaa South Third'. A resident writes 'Al Barsha South
    Third' and has no way to know which spelling is on file."""
    assert area_key("Al Barshaa South Third") == area_key("Al Barsha South Third")


def test_one_neighbourhood_recorded_twice_resolves_to_one_key():
    assert area_key("AL QUSAIS") == area_key("Al Qusais")


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Al Barsha First", "Al Barsha Second"),
        ("Al Barsha South Fourth", "Al Barsha South Fifth"),
        ("Jabal Ali Industrial First", "Jabal Ali Industrial Second"),
        ("Marsa Dubai", "Madinat Dubai Almelaheyah"),
    ],
)
def test_different_neighbourhoods_never_share_a_key(left, right):
    """The damaging direction. Merging Al Barsha First into Al Barsha Second
    would corrupt both medians and nothing would look wrong."""
    assert area_key(left) != area_key(right)


@pytest.mark.parametrize(
    "name", ["  Al Barsha First  ", "AL BARSHA FIRST", "Al-Barsha  First", "al barsha first"]
)
def test_the_key_survives_the_ways_a_name_gets_written(name):
    assert area_key(name) == area_key("Al Barsha First")
