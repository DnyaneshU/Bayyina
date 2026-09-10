"""What the aggregate must cover, and what it must refuse to compute.

The two things worth breaking here are both about *when*: which twelve months
the window covers, and whether a median exists for a cell too thin to quote.
"""

from __future__ import annotations

from datetime import date

import duckdb
import pytest

from bayyina.market.aggregate import SnapshotNotFoundError
from bayyina.settings import Settings

from .conftest import cell


def comparables(database) -> list[tuple]:
    con = duckdb.connect(str(database), read_only=True)
    try:
        return con.execute(
            "select area_key, property_kind, bedrooms, contract_count, median_annual_rent "
            "from comparables order by area_key, property_kind, bedrooms"
        ).fetchall()
    finally:
        con.close()


# --- The shape of the table ---------------------------------------------------


def test_one_row_per_area_kind_and_bedroom_count(market):
    database, _, report = market(
        cell(40, prefix="A")
        + cell(30, prefix="B", sub_type="1bed room+Hall")
        + cell(20, prefix="C", property_type="Villa", rent=150_000)
        + cell(15, prefix="D", area="Marsa Dubai", area_id=999, rent=120_000)
    )
    rows = comparables(database)

    assert len(rows) == 4 == report.cells
    assert {(r[0], r[1], r[2]) for r in rows} == {
        ("al barsha first", "flat", 2),
        ("al barsha first", "flat", 1),
        ("al barsha first", "villa", 2),
        ("marsa dubai", "flat", 2),
    }
    assert all(count > 0 and median is not None for *_, count, median in rows)


def test_dlds_eleven_labels_collapse_to_the_words_a_caller_uses(market):
    """Nobody phoning in describes their home as a 'Complex Villa'."""
    database, _, _ = market(
        cell(20, prefix="V", property_type="Villa", rent=150_000)
        + cell(20, prefix="C", property_type="Complex Villas", rent=150_000)
        + cell(20, prefix="A", property_type="Arabian House", rent=150_000)
    )
    kinds = {r[1] for r in comparables(database)}
    assert kinds == {"villa"}, "three DLD labels for one thing a resident would call a villa"


def test_the_median_is_the_median(market):
    # Odd count, so the answer is a value that is actually in the data.
    database, _, _ = market(cell(41, rent=60_000))
    ((_, _, _, count, median),) = comparables(database)
    assert count == 41
    assert median == 80_000  # 60,000 + 20 * 1,000


# --- The window ---------------------------------------------------------------


def test_the_window_ends_at_the_data_not_at_today(market):
    """**The failure that would have gone unnoticed for months.**

    The release runs to 2026-03-01 and today is later than that. A rolling twelve
    months to `now()` slides off the end of the data: six months after
    publication it covers 267,252 contracts instead of 567,652, and it keeps
    shrinking, with no error and no signal — just quietly thinner evidence and
    more cells falling under the answer floor.
    """
    database, ingest_report, report = market(cell(40, start=date(2025, 3, 1)))

    assert report.window_end == ingest_report.data_horizon == date(2025, 3, 1)
    assert report.window_start == date(2024, 3, 1)
    assert report.contracts_in_window == 40, "the window missed the data it was built from"


def test_contracts_older_than_the_window_are_not_counted(market):
    """A median over five years describes no year in it."""
    database, _, report = market(
        cell(40, prefix="NOW", start=date(2025, 3, 1))
        + cell(40, prefix="OLD", start=date(2021, 6, 1), rent=30_000)
    )
    assert report.contracts_in_window == 40
    ((_, _, _, count, median),) = comparables(database)
    assert count == 40
    assert median > 60_000, "a 2021 rent leaked into a 2025 median"


def test_a_shorter_window_can_be_asked_for_without_reingesting(market):
    database, _, report = market(cell(40, start=date(2025, 3, 1)), window_months=6)
    assert report.window_months == 6
    assert report.window_start == date(2024, 9, 1)


# --- G5: below the floor, no median exists ------------------------------------


def test_a_thin_cell_gets_no_median_at_all(market):
    """Not computed and withheld — never computed.

    A number that does not exist cannot be read to a caller by mistake, and this
    is the last place it could have been created.
    """
    database, _, report = market(cell(4, prefix="THIN"))
    ((area, kind, beds, count, median),) = comparables(database)

    assert count == 4, "the count is kept — 'we found only four' needs the four"
    assert median is None
    assert report.cells == 1
    assert report.quotable_cells == 0


def test_a_cell_exactly_at_the_floor_is_quotable(market):
    """The boundary is a decision, so it is asserted rather than assumed."""
    floor = Settings().min_contracts_for_answer
    database, _, report = market(cell(floor, prefix="EXACT"))
    ((*_, count, median),) = comparables(database)

    assert count == floor
    assert median is not None
    assert report.quotable_cells == 1


def test_one_below_the_floor_is_not(market):
    floor = Settings().min_contracts_for_answer
    database, _, report = market(cell(floor - 1, prefix="UNDER"))
    ((*_, median),) = [comparables(database)[0]]
    assert median is None
    assert report.quotable_cells == 0


def test_the_floor_the_table_was_built_under_is_recorded(market):
    """The artefact carries the rule it was made by, so a figure quoted last
    month can be explained next month."""
    _, _, report = market(cell(40), settings=Settings(min_contracts_for_answer=25))
    assert report.answer_floor == 25


def test_raising_the_floor_removes_medians(market):
    database, _, report = market(cell(20), settings=Settings(min_contracts_for_answer=50))
    ((*_, count, median),) = comparables(database)
    assert count == 20
    assert median is None, "20 contracts produced a figure under a floor of 50"
    assert report.quotable_cells == 0


# --- Provenance and re-runs ---------------------------------------------------


def test_re_aggregating_replaces_rather_than_doubles(market, database):
    from bayyina.market.aggregate import aggregate as run

    market(cell(40))
    first = comparables(database)
    run(database, "snap_test")
    assert comparables(database) == first


def test_aggregating_a_snapshot_that_is_not_there_says_which_are(market, database):
    from bayyina.market.aggregate import aggregate as run

    market(cell(40))
    with pytest.raises(SnapshotNotFoundError, match="snap_test"):
        run(database, "snap_missing")


def test_a_failed_aggregation_leaves_no_half_table(market, database, monkeypatch):
    """Same reasoning as the ingest: a comparables table with no `aggregates` row
    has no window, no floor and no date, and looks entirely normal."""
    from bayyina.market import aggregate as module

    market(cell(40))
    before = comparables(database)

    def explode(**kwargs):
        raise RuntimeError("the machine went away")

    monkeypatch.setattr(module, "AggregateReport", explode)
    with pytest.raises(RuntimeError, match="the machine went away"):
        module.aggregate(database, "snap_test")

    assert comparables(database) == before, "a failed run damaged the standing table"


# --- The serving database -----------------------------------------------------


def test_the_serving_database_carries_no_contract_rows(market, database, tmp_path):
    """**The 359 MB question.**

    The request path reads 1,324 comparables. The build database beside them
    holds 5.3 million individual tenancy records — a rent, an area, a date, a
    contract id each — that nothing at runtime touches. Shipping them inside a
    public container image would be needless in both size and disclosure.
    """
    from bayyina.market.aggregate import SERVING_TABLES, export_for_serving

    market(cell(40))
    serving = tmp_path / "comparables.duckdb"
    export_for_serving(database, serving, "snap_test")

    con = duckdb.connect(str(serving), read_only=True)
    try:
        tables = {name for (name,) in con.execute("show tables").fetchall()}
        assert tables == set(SERVING_TABLES)
        assert "contracts" not in tables
        assert con.execute("select count(*) from comparables").fetchone()[0] == 1
        assert con.execute("select count(*) from areas").fetchone()[0] == 1
    finally:
        con.close()


def test_the_serving_database_keeps_its_provenance(market, database, tmp_path):
    """A figure that cannot be traced to a file is not evidence, and the shipped
    database is the only copy a deployed service has."""
    from bayyina.market.aggregate import export_for_serving

    _, ingest_report, _ = market(cell(40))
    serving = tmp_path / "comparables.duckdb"
    export_for_serving(database, serving, "snap_test")

    con = duckdb.connect(str(serving), read_only=True)
    try:
        source, digest, horizon = con.execute(
            "select source, source_sha256, data_horizon from snapshots"
        ).fetchone()
    finally:
        con.close()

    assert digest == ingest_report.source_sha256
    assert source == ingest_report.source
    assert horizon == ingest_report.data_horizon


def test_the_service_can_read_what_was_exported(market, database, tmp_path):
    """The export is only correct if the store actually boots from it."""
    from bayyina.market.aggregate import export_for_serving
    from bayyina.market.comparables import ComparableStore

    market(cell(40))
    serving = tmp_path / "comparables.duckdb"
    export_for_serving(database, serving, "snap_test")

    store = ComparableStore(serving, snapshot_id="snap_test")
    assert store.areas == ["Al Barsha First"]


def test_exporting_a_snapshot_with_nothing_in_it_is_refused(market, database, tmp_path):
    """Shipping an empty database would boot a service that answers nothing, and
    it would look exactly like a healthy one."""
    from bayyina.market.aggregate import SnapshotNotFoundError, export_for_serving

    market(cell(40))
    with pytest.raises(SnapshotNotFoundError, match="empty serving database"):
        export_for_serving(database, tmp_path / "empty.duckdb", "snap_absent")


def test_the_export_is_far_smaller_than_the_build(market, database, tmp_path):
    """On the real release: 359 MB down to 1.3 MB, 271x. The fixture is tiny, so
    this asserts the relationship rather than the number."""
    from bayyina.market.aggregate import export_for_serving

    market(cell(2_000))
    serving = tmp_path / "comparables.duckdb"
    size = export_for_serving(database, serving, "snap_test")
    assert size < database.stat().st_size
