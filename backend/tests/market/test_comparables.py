"""The three bands, the two refusals, and the invariant underneath all of them.

**No code path returns a number below the evidence threshold.** The plan says to
assert that rather than assume it, so the bands are tested at their exact
boundaries and the type is tested directly — a `Comparable` that is not `ok` must
be unable to hold a figure at all.
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from bayyina.market.comparables import (
    Comparable,
    ComparableStatus,
    ComparableStore,
    MarketDataUnavailableError,
)
from bayyina.settings import Settings

from .conftest import START, cell

#: The synthetic release's contracts all start here, so this is the window end.
FRESH = START + timedelta(days=30)
LONG_AFTER = START + timedelta(days=400)


def store_for(database, **kwargs) -> ComparableStore:
    return ComparableStore(database, snapshot_id="snap_test", **kwargs)


# --- The three bands ----------------------------------------------------------


def test_thick_data_answers_with_full_confidence(market, database):
    """30 or more comparable contracts: quote the figure, no caveat."""
    database, _, _ = market(cell(40))
    found = store_for(database).lookup("Al Barsha First", "flat", 2, as_of=FRESH)

    assert found.status is ComparableStatus.OK
    assert found.contract_count == 40
    assert found.median_annual_rent is not None
    assert found.full_confidence is True


def test_thin_but_usable_data_answers_with_reduced_confidence(market, database):
    """10 to 29: the figure is quotable and its thinness is disclosed beside it.

    This band is the reason `full_confidence` exists as a separate field rather
    than being inferred from the count downstream — the voice script has to say
    the caveat, and it should not have to re-derive when.
    """
    database, _, _ = market(cell(15))
    found = store_for(database).lookup("Al Barsha First", "flat", 2, as_of=FRESH)

    assert found.status is ComparableStatus.OK
    assert found.contract_count == 15
    assert found.median_annual_rent is not None
    assert found.full_confidence is False


def test_below_the_floor_there_is_no_figure_to_return(market, database):
    database, _, _ = market(cell(4))
    found = store_for(database).lookup("Al Barsha First", "flat", 2, as_of=FRESH)

    assert found.status is ComparableStatus.INSUFFICIENT_DATA
    assert found.median_annual_rent is None
    assert found.full_confidence is False
    assert found.contract_count == 4, "the caller is owed the number we did find"


@pytest.mark.parametrize(
    ("count", "status", "full"),
    [
        (9, ComparableStatus.INSUFFICIENT_DATA, False),
        (10, ComparableStatus.OK, False),
        (29, ComparableStatus.OK, False),
        (30, ComparableStatus.OK, True),
        (31, ComparableStatus.OK, True),
    ],
)
def test_the_boundaries_are_exactly_where_the_settings_put_them(
    market, database, count, status, full
):
    """Off-by-one here is the difference between quoting a figure and refusing
    to, so both edges are pinned rather than sampled."""
    database, _, _ = market(cell(count))
    found = store_for(database).lookup("Al Barsha First", "flat", 2, as_of=FRESH)

    assert found.status is status
    assert found.full_confidence is full
    assert (found.median_annual_rent is not None) == (status is ComparableStatus.OK)


def test_the_thresholds_come_from_settings_not_from_literals(market, database):
    database, _, _ = market(cell(15), settings=Settings(min_contracts_for_answer=20))
    settings = Settings(min_contracts_for_answer=20, min_contracts_for_full_confidence=100)
    found = store_for(database, settings=settings).lookup("Al Barsha First", "flat", 2, as_of=FRESH)
    assert found.status is ComparableStatus.INSUFFICIENT_DATA


# --- Staleness ----------------------------------------------------------------


def test_data_too_old_to_quote_is_refused_however_thick_it_is(market, database):
    """Freshness is a property of the release, not of the cell.

    A cell with 40,000 contracts behind it is still describing a market that has
    moved on. Dubai rents moved 65,000 to 88,000 between 2021 and 2026 in one
    area, and the rule's bands are five percentage points wide — a stale median
    flips a band near its boundary.
    """
    database, _, _ = market(cell(400))
    found = store_for(database).lookup("Al Barsha First", "flat", 2, as_of=LONG_AFTER)

    assert found.status is ComparableStatus.STALE
    assert found.median_annual_rent is None
    assert found.age_days == 400


def test_staleness_is_measured_from_the_data_not_from_the_ingest(market, database):
    """Re-running the ingest on an old file must not make it fresh.

    Measured from `computed_at`, a nightly job pointed at a stale release would
    report perfectly fresh comparables for ever. The clock that matters is the
    newest contract's, and it is the release's, not ours.
    """
    database, _, aggregate_report = market(cell(40))
    found = store_for(database).lookup("Al Barsha First", "flat", 2, as_of=LONG_AFTER)

    assert found.window_end == aggregate_report.window_end
    assert found.age_days == (LONG_AFTER - aggregate_report.window_end).days
    assert found.status is ComparableStatus.STALE


def test_the_staleness_limit_comes_from_settings(market, database):
    database, _, _ = market(cell(40))
    generous = store_for(database, settings=Settings(market_snapshot_max_age_days=3650))
    assert generous.lookup("Al Barsha First", "flat", 2, as_of=LONG_AFTER).status is (
        ComparableStatus.OK
    )


def test_staleness_is_asked_before_thinness(market, database):
    """Order matters to the person listening.

    Telling someone "not enough contracts in your area" when the real problem is
    that our whole release is six months old is both wrong and unactionable.
    """
    database, _, _ = market(cell(4))
    found = store_for(database).lookup("Al Barsha First", "flat", 2, as_of=LONG_AFTER)
    assert found.status is ComparableStatus.STALE


# --- Areas --------------------------------------------------------------------


def test_a_resident_spelling_finds_dlds_spelling(market, database):
    """DLD writes 'Al Barshaa South Third'. Nobody else does."""
    database, _, _ = market(cell(40, area="Al Barshaa South Third", area_id=409))
    found = store_for(database).lookup("Al Barsha South Third", "flat", 2, as_of=FRESH)

    assert found.status is ComparableStatus.OK
    assert found.area_name == "Al Barshaa South Third"


def test_an_area_we_do_not_know_says_so(market, database):
    """Distinct from insufficient data: one means "not enough contracts there",
    the other "where?" — and only one of them the caller can fix."""
    database, _, _ = market(cell(40))
    found = store_for(database).lookup("Narnia", "flat", 2, as_of=FRESH)

    assert found.status is ComparableStatus.UNKNOWN_AREA
    assert found.median_annual_rent is None
    assert found.area_name is None


def test_a_known_area_with_no_such_cell_is_thin_not_unknown(market, database):
    database, _, _ = market(cell(40))
    found = store_for(database).lookup("Al Barsha First", "villa", 7, as_of=FRESH)

    assert found.status is ComparableStatus.INSUFFICIENT_DATA
    assert found.contract_count == 0
    assert found.area_name == "Al Barsha First"


def test_the_store_can_list_the_areas_it_knows(market, database):
    """The voice agent needs this to disambiguate, rather than guessing."""
    database, _, _ = market(cell(40) + cell(40, prefix="M", area="Marsa Dubai", area_id=999))
    assert store_for(database).areas == ["Al Barsha First", "Marsa Dubai"]


# --- The invariant, tested on the type itself ---------------------------------


@pytest.mark.parametrize(
    "status",
    [ComparableStatus.INSUFFICIENT_DATA, ComparableStatus.STALE, ComparableStatus.UNKNOWN_AREA],
)
def test_a_comparable_that_is_not_ok_cannot_hold_a_figure(status):
    """G5 as a property of the type, not of the branch that built the object.

    Every refusal path is one `return` away from carrying a number by accident.
    This makes the accident impossible to express.
    """
    common = {
        "area_key": "al barsha first",
        "property_kind": "flat",
        "bedrooms": 2,
        "snapshot_id": "snap_test",
        "window_start": date(2025, 3, 1),
        "window_end": date(2026, 3, 1),
        "age_days": 10,
    }
    with pytest.raises(ValidationError, match="must not carry a figure"):
        Comparable(status=status, median_annual_rent=85_000, **common)

    with pytest.raises(ValidationError, match="no confidence to report"):
        Comparable(status=status, full_confidence=True, **common)


def test_an_ok_comparable_without_a_figure_is_also_refused():
    """The other direction: a quotable status with nothing to quote is a bug
    that would surface as `None` somewhere far away."""
    with pytest.raises(ValidationError, match="must carry a figure"):
        Comparable(
            status=ComparableStatus.OK,
            area_key="al barsha first",
            property_kind="flat",
            bedrooms=2,
            snapshot_id="snap_test",
            window_start=date(2025, 3, 1),
            window_end=date(2026, 3, 1),
            age_days=10,
        )


# --- Boot ---------------------------------------------------------------------


def test_a_missing_database_is_refused_at_boot_not_at_the_first_call(tmp_path):
    """A service that starts and then cannot answer is worse than one that
    refuses to start — the same reasoning as the rules corpus (G7)."""
    with pytest.raises(MarketDataUnavailableError, match="ingest_market"):
        ComparableStore(tmp_path / "absent.duckdb")


def test_an_ingest_with_no_aggregation_is_refused(market, database):
    import duckdb

    market(cell(40))
    con = duckdb.connect(str(database))
    con.execute("delete from aggregates")
    con.close()

    with pytest.raises(MarketDataUnavailableError, match="no aggregated snapshot"):
        ComparableStore(database)


def test_the_latest_snapshot_is_chosen_when_none_is_named(market, database):
    market(cell(40))
    assert ComparableStore(database).snapshot_id == "snap_test"


# --- Latency ------------------------------------------------------------------


def test_a_lookup_is_far_inside_the_budget(market, database):
    """**T2.2's definition of done: under 20 ms.**

    The budget exists because a `GROUP BY` over 5.3M rows at call time cannot
    meet it, and our webhook has 150 ms of a 1.5 s first-audio target. The table
    is read once at boot and held in memory, so a lookup is a dict access and
    the measurement below is really a regression alarm: if this ever approaches
    20 ms, something has put I/O back on the request path.
    """
    database, _, _ = market(cell(40) + cell(40, prefix="M", area="Marsa Dubai", area_id=999))
    store = store_for(database)

    # Warm, then measure the 95th percentile of a thousand lookups.
    for _ in range(50):
        store.lookup("Al Barsha First", "flat", 2, as_of=FRESH)

    timings = []
    for _ in range(1000):
        started = time.perf_counter()
        store.lookup("Al Barsha First", "flat", 2, as_of=FRESH)
        timings.append((time.perf_counter() - started) * 1000)

    timings.sort()
    p95 = timings[949]
    assert p95 < 20.0, f"p95 lookup is {p95:.3f} ms, over the 20 ms budget"
    assert max(timings) < 20.0, f"slowest lookup is {max(timings):.3f} ms"


def test_no_request_touches_the_database(market, database):
    """The store is read once at boot and held in memory.

    Deleting the file underneath a live store must change nothing. That is a
    stronger statement than timing it: a lookup cannot be doing I/O against a
    file that is no longer there.
    """
    database, _, _ = market(cell(40))
    store = store_for(database)
    database.unlink()

    found = store.lookup("Al Barsha First", "flat", 2, as_of=FRESH)
    assert found.status is ComparableStatus.OK
    assert found.median_annual_rent is not None
    assert store.areas == ["Al Barsha First"]


# --- Recency is the cell's, not the release's ---------------------------------


def _mixed_ages(market):
    """One recent cell and one that trails the release badly."""
    return market(
        cell(40, prefix="NOW", start=START)
        + cell(
            40,
            prefix="OLD",
            start=START - timedelta(days=280),
            sub_type="1bed room+Hall",
            rent=50_000,
        )
    )


def test_the_age_reported_is_the_age_of_the_cell_being_quoted(market, database):
    """**A disclosure that was wrong for 11.7% of cells.**

    We told every caller the release was 193 days old. Measured on the real
    data, 98 of 841 quotable cells trail the horizon by more than a month, and
    one holds 72 contracts whose newest is **418 days old** — past our own
    refusal threshold, quoted with a "193 days" label.

    The whole two-threshold model rests on this number. It has to be the age of
    the evidence actually being quoted.
    """
    database, _, aggregate_report = _mixed_ages(market)
    store = store_for(database)
    as_of = START + timedelta(days=30)

    recent = store.lookup("Al Barsha First", "flat", 2, as_of=as_of)
    trailing = store.lookup("Al Barsha First", "flat", 1, as_of=as_of)

    assert recent.age_days == 30
    assert trailing.age_days == 310, "the older cell reported the release's age"
    assert store.age_days(as_of) == 30, "the release itself is still recent"
    assert aggregate_report.window_end == START


def test_a_cell_past_the_limit_is_refused_inside_a_release_that_is_not(market, database):
    """The consequence. A release can be well inside its limit while a cell in
    it is not, and it is the cell we are about to read out."""
    database, _, _ = _mixed_ages(market)
    store = store_for(database, settings=Settings(market_snapshot_max_age_days=200))
    as_of = START + timedelta(days=30)

    assert store.is_stale(as_of) is False, "the release is 30 days old"
    assert store.lookup("Al Barsha First", "flat", 2, as_of=as_of).status is ComparableStatus.OK
    trailing = store.lookup("Al Barsha First", "flat", 1, as_of=as_of)
    assert trailing.status is ComparableStatus.STALE
    assert trailing.median_annual_rent is None


def test_the_build_says_when_it_has_produced_figures_already_too_old(market):
    """Cheaper to learn at build time than one request at a time."""
    _, _, report = _mixed_ages(market)
    assert report.oldest_quotable_contract == START - timedelta(days=280)


def test_a_window_of_no_months_is_refused(market, database, release):
    from bayyina.market.aggregate import aggregate as run

    market(cell(40))
    with pytest.raises(ValueError, match="must be positive"):
        run(database, "snap_test", window_months=0)
