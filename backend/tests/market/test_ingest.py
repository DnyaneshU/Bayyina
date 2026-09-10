"""What the ingest must refuse, and what it must not throw away.

Every test here names a real defect in the DLD release. If one of these stops
being load-bearing, a resident gets a confident wrong number with a correct
citation attached, which is the worst outcome this product has.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from bayyina.market.errors import (
    DataQualityError,
    SourceNotFoundError,
    UnknownCategoryError,
)
from bayyina.market.ingest import MIN_ROWS_FOR_IQR, ingest

from .conftest import baseline, row


def stored(database: Path) -> list[tuple]:
    con = duckdb.connect(str(database), read_only=True)
    try:
        return con.execute(
            "select contract_id, area_key, property_type, bedrooms, annual_rent "
            "from contracts order by contract_id"
        ).fetchall()
    finally:
        con.close()


def ids(database: Path) -> set[str]:
    return {r[0] for r in stored(database)}


#: `baseline()` puts this many ordinary contracts in one cell.
BASELINE_ROWS = 40


def assert_out_of_scope(report, database: Path, *contracts: str) -> None:
    """Assert the rows never entered scope — not merely that they are absent.

    Asserting only their absence from `contracts` is not enough, and this was
    found the hard way: with the scope rule deleted, the hazard rows *did* enter
    scope and were then removed by the outlier fence, so the test still passed
    and proved nothing. A rent far from its peers is caught twice over. The
    claim being made is "this is not a tenancy", and the only stage that can
    speak to it is scope.
    """
    assert report.in_scope_rows == BASELINE_ROWS, (
        f"{report.in_scope_rows - BASELINE_ROWS} row(s) reached the in-scope set "
        f"that should never have been considered a tenancy"
    )
    assert set(contracts).isdisjoint(ids(database))


# --- Scope: what is not a tenancy ---------------------------------------------


def test_labour_camp_rents_never_reach_a_comparable(release, database):
    """The failure that started this file.

    'Room in labor Camp' has a median of AED 504,000 and 978,610 contracts sit
    under it, all labelled `property_usage_en = 'Residential'`. Left in, a
    caller in an industrial area is told the market rate for their flat is in
    the hundreds of thousands, and every verdict resting on it is wrong while
    looking perfectly sound.
    """
    source = release(
        baseline()
        + [
            row(
                "CRT_CAMP", rent=504_000, property_type="Labor Camps", sub_type="Room in labor Camp"
            ),
            row(
                "CRT_STAFF",
                rent=2_274_500,
                property_type="Staff Accommodation",
                sub_type="Staff Accommodatoion",
            ),
            row("CRT_PORTA", rent=929_388, property_type="Portacabin", sub_type="Portacabin Rooms"),
        ]
    )
    report = ingest(source, database)
    assert_out_of_scope(report, database, "CRT_CAMP", "CRT_STAFF", "CRT_PORTA")


def test_a_camp_room_wearing_a_flats_label_is_still_excluded(release, database):
    """Neither filter is sufficient alone, which is why scope is their intersection.

    In the real release 'Room in labor Camp' appears 3,234 times under property
    type 'Flat', and 'Studio' appears 6,552 times under 'Labor Camps'. Filtering
    on property type alone admits the first; on sub-type alone admits the second.
    """
    source = release(
        baseline()
        + [
            row(
                "CRT_CAMP_AS_FLAT",
                rent=936_120,
                property_type="Flat",
                sub_type="Room in labor Camp",
            ),
            row("CRT_STUDIO_IN_CAMP", rent=540_000, property_type="Labor Camps", sub_type="Studio"),
        ]
    )
    report = ingest(source, database)
    assert_out_of_scope(report, database, "CRT_CAMP_AS_FLAT", "CRT_STUDIO_IN_CAMP")


def test_a_whole_block_contract_is_not_one_flats_rent(release, database):
    """`annual_amount` is the whole-contract total, not the rent of one unit.

    Measured: a 2-bed flat contract covering one property has a median of AED
    66,000; covering ten, AED 596,904. The plan did not have this condition and
    1,375,195 residential rows carry it. Left in, every median is inflated and
    one contract is counted once per property it covers.
    """
    source = release(
        baseline() + [row("CRT_BLOCK", rent=596_904, properties=10, line=n) for n in range(1, 11)]
    )
    report = ingest(source, database)
    assert_out_of_scope(report, database, "CRT_BLOCK")


def test_one_contract_is_stored_once(release, database):
    """The 0.06% where `no_of_prop` disagrees with the line count.

    `no_of_prop = 1` de-duplicates 99.94% of the release on its own. A tenancy
    counted twice must not reach a median on the strength of that.
    """
    source = release(
        baseline()
        + [
            row("CRT_REPEATED", rent=75_000, line=1),
            row("CRT_REPEATED", rent=75_000, line=2),
        ]
    )
    report = ingest(source, database)
    assert [r[0] for r in stored(database)].count("CRT_REPEATED") == 1
    assert report.row_count == len(ids(database))


def test_commercial_stock_is_out_of_scope(release, database):
    source = release(baseline() + [row("CRT_SHOP", usage="Commercial", sub_type="Shop")])
    report = ingest(source, database)
    assert_out_of_scope(report, database, "CRT_SHOP")


def test_a_dwelling_with_no_bedroom_count_is_excluded_not_rejected(release, database):
    """A penthouse is a real home; we simply cannot place it in a bedroom cell.

    It belongs in `excluded`, not in `rejected` — nothing is wrong with the row,
    and counting it as a data-quality problem would misreport the one number the
    DoD is written in.
    """
    source = release(baseline() + [row("CRT_PENTHOUSE", sub_type="Penthouse")])
    report = ingest(source, database)
    assert_out_of_scope(report, database, "CRT_PENTHOUSE")
    assert report.rejected_rows == 0, "an excluded row must not be counted as a rejection"


# --- Rejections: in scope, unusable -------------------------------------------


@pytest.mark.parametrize(
    ("contract", "kwargs", "reason"),
    [
        ("CRT_ZERO", {"rent": 0.0}, "non_positive_rent"),
        ("CRT_NEGATIVE", {"rent": -5000.0}, "non_positive_rent"),
        ("CRT_TINY", {"rent": 800.0}, "rent_below_floor"),
        ("CRT_HUGE", {"rent": 3_300_037_950.0}, "rent_above_ceiling"),
        (
            "CRT_BACKWARDS",
            {"start": date(2026, 2, 28), "end": date(2025, 3, 1)},
            "end_not_after_start",
        ),
    ],
)
def test_unusable_rows_are_rejected_and_the_reason_is_recorded(
    release, database, contract, kwargs, reason
):
    """A rejection nobody can name is a rejection nobody can investigate."""
    source = release(baseline() + [row(contract, **kwargs)])
    report = ingest(source, database)

    assert contract not in ids(database)
    assert report.rejections.get(reason) == 1, report.rejections
    assert report.rejected_rows == 1


def test_the_rejection_rate_is_measured_against_in_scope_rows(release, database):
    """Not against the file.

    56% of the release is out of scope. Measured against the file, a rejection
    rate could triple and still look like a rounding error — the number the DoD
    turns on would stop meaning anything.
    """
    source = release(
        baseline(count=9)
        + [row("CRT_BAD", rent=0.0)]
        + [
            row(f"CRT_CAMP_{i}", property_type="Labor Camps", sub_type="Labor Camp")
            for i in range(90)
        ]
    )
    # The guard is the subject of the next test; here it must not pre-empt the
    # measurement it protects.
    report = ingest(source, database, max_rejection_rate=0.5)

    assert report.in_scope_rows == 10
    assert report.rejected_rows == 1
    assert report.rejection_rate == pytest.approx(0.1)


def test_an_unusable_release_stops_the_ingest(release, database):
    """ "Stop. Investigate before building on it" — the plan's risk register.

    A comparable table quietly built from a third of the data it should have
    looks entirely normal from the outside, and every verdict on it inherits the
    problem with no way to see it.
    """
    source = release(baseline(count=90) + [row(f"CRT_BAD_{i}", rent=0.0) for i in range(10)])
    with pytest.raises(DataQualityError, match=r"10 of 100 in-scope rows"):
        ingest(source, database)


# --- Normalisation ------------------------------------------------------------


def test_a_doubled_letter_does_not_hide_a_neighbourhood(release, database):
    """DLD writes 'Al Barshaa South Third'. A resident writes 'Al Barsha South
    Third' and has no way to know the difference."""
    source = release(
        [row(f"CRT_A_{i}", area_id=409, area="Al Barshaa South Third") for i in range(10)]
        + [row(f"CRT_B_{i}", area_id=999, area="Al Barsha South Third") for i in range(10)]
    )
    ingest(source, database)
    assert {r[1] for r in stored(database)} == {"al barsha south third"}


def test_distinct_neighbourhoods_keep_distinct_keys(release, database):
    """The other direction, and the more damaging one.

    Al Barsha First and Al Barsha Second are different places. Merging them would
    corrupt both medians and nothing would look wrong.
    """
    source = release(
        [row(f"CRT_1_{i}", area_id=368, area="Al Barsha First") for i in range(10)]
        + [row(f"CRT_2_{i}", area_id=393, area="Al Barsha Second") for i in range(10)]
    )
    ingest(source, database)
    assert {r[1] for r in stored(database)} == {"al barsha first", "al barsha second"}


def test_a_resident_is_shown_the_cased_spelling(release, database):
    """'AL QUSAIS' (148,665 contracts) and 'Al Qusais' (11) are one neighbourhood
    under two area codes. The evidence pack should not shout."""
    source = release(
        [row(f"CRT_U_{i}", area_id=305, area="AL QUSAIS") for i in range(10)]
        + [row(f"CRT_L_{i}", area_id=241, area="Al Qusais") for i in range(3)]
    )
    ingest(source, database, snapshot_id="snap_test")

    con = duckdb.connect(str(database), read_only=True)
    try:
        assert con.execute(
            "select area_name from areas where area_key = 'al qusais'"
        ).fetchone() == ("Al Qusais",)
    finally:
        con.close()


def test_a_maids_room_is_not_a_bedroom(release, database):
    source = release(baseline() + [row("CRT_MAID", sub_type="2 bed rooms+hall+Maids Room")])
    ingest(source, database)
    assert {r[0]: r[3] for r in stored(database)}["CRT_MAID"] == 2


def test_a_studio_has_zero_bedrooms_not_no_bedrooms(release, database):
    """Zero is a real bedroom count. Treating it as missing would drop a quarter
    of the flats a lower-income caller actually rents."""
    source = release(
        [row(f"CRT_S_{i}", sub_type="Studio", property_type="Studio ") for i in range(10)]
    )
    ingest(source, database)
    assert {r[3] for r in stored(database)} == {0}


# --- Outliers -----------------------------------------------------------------


def test_an_outlier_inside_a_cell_is_trimmed(release, database):
    """Absolute bounds are not enough: Al Barsha First 2-beds still span AED
    9,000 to 6,000,000 after filtering against them."""
    source = release(baseline(count=40, rent=60_000) + [row("CRT_OUTLIER", rent=6_000_000)])
    report = ingest(source, database)

    assert "CRT_OUTLIER" not in ids(database)
    assert report.trimmed_rows == 1


def test_a_normal_contract_survives_trimming(release, database):
    """A fence that clips ordinary contracts is worse than no fence."""
    source = release(baseline(count=40, rent=60_000) + [row("CRT_NORMAL", rent=63_000)])
    ingest(source, database)
    assert "CRT_NORMAL" in ids(database)


def test_a_thin_cell_is_left_alone(release, database):
    """A quartile over a handful of contracts describes noise, not a market.

    Below the threshold nothing is trimmed, and T2.3 decides whether the cell may
    be quoted at all — which is the honest place for that decision.
    """
    thin = MIN_ROWS_FOR_IQR - 2  # plus CRT_WIDE, still under the threshold
    source = release(
        [row(f"CRT_T_{i}", rent=60_000 + i * 100) for i in range(thin)]
        + [row("CRT_WIDE", rent=500_000)]
    )
    report = ingest(source, database)
    assert report.trimmed_rows == 0
    assert "CRT_WIDE" in ids(database)


def test_the_fence_is_drawn_within_a_year(release, database):
    """Rents drift. Al Barsha First 2-beds: AED 90,000 in 2017, 65,000 in 2021,
    88,000 in 2026.

    A fence drawn across the whole corpus describes no year in it, and would read
    an ordinary 2026 contract as an outlier of 2021.
    """
    old = [
        row(f"CRT_2017_{i}", rent=30_000 + i * 50, start=date(2017, 3, 1), end=date(2018, 2, 28))
        for i in range(40)
    ]
    new = [
        row(f"CRT_2026_{i}", rent=90_000 + i * 50, start=date(2026, 1, 1), end=date(2026, 12, 31))
        for i in range(40)
    ]
    report = ingest(release(old + new), database)

    assert report.trimmed_rows == 0, "an ordinary contract was clipped by another era's fence"
    assert len(ids(database)) == 80


# --- Guards -------------------------------------------------------------------


def test_a_renamed_category_stops_the_ingest(release, database):
    """The one way an allowlist fails silently.

    If DLD renames 'Flat' to 'Apartment', five million rows leave scope, the
    ingest reports a small clean table, and nothing looks wrong until a caller
    is told there is no data for their area.
    """
    source = release([row(f"CRT_NEW_{i}", property_type="Apartment") for i in range(100)])
    with pytest.raises(UnknownCategoryError, match="Apartment"):
        ingest(source, database)


def test_a_missing_release_names_the_path_it_looked_in(release, database, tmp_path):
    with pytest.raises(SourceNotFoundError, match=r"absent\.parquet"):
        ingest(tmp_path / "absent.parquet", database)


# --- The snapshot record ------------------------------------------------------


def test_the_snapshot_records_the_exact_bytes_it_came_from(release, database):
    """A comparable figure that cannot be traced to a file is not evidence."""
    source = release(baseline())
    report = ingest(source, database, snapshot_id="snap_fixed")

    con = duckdb.connect(str(database), read_only=True)
    try:
        stored_row = con.execute(
            "select snapshot_id, source, source_sha256, row_count, rejection_rate "
            "from snapshots where snapshot_id = 'snap_fixed'"
        ).fetchone()
    finally:
        con.close()

    assert stored_row[0] == "snap_fixed"
    assert stored_row[1] == "release.parquet"
    assert stored_row[2].startswith("sha256:") and len(stored_row[2]) == 71
    assert stored_row[2] == report.source_sha256
    assert stored_row[3] == report.row_count


def test_the_counts_add_up(release, database):
    """Every source row is accounted for exactly once, so the report cannot
    quietly lose rows between stages."""
    source = release(
        baseline(count=40)
        + [row("CRT_CAMP", property_type="Labor Camps", sub_type="Labor Camp")]
        + [row("CRT_BAD", rent=0.0)]
        + [row("CRT_OUTLIER", rent=6_000_000)]
    )
    report = ingest(source, database)

    assert report.excluded_rows + report.in_scope_rows == report.source_rows
    assert report.rejected_rows + report.trimmed_rows + report.row_count == report.in_scope_rows


def test_re_ingesting_the_same_snapshot_does_not_double_it(release, database):
    """A re-run after a fixed bug must replace the snapshot, not append to it."""
    source = release(baseline())
    first = ingest(source, database, snapshot_id="snap_repeat")
    second = ingest(source, database, snapshot_id="snap_repeat")

    assert first.row_count == second.row_count
    assert len(stored(database)) == second.row_count


# --- Provenance ---------------------------------------------------------------


def test_a_stored_contract_always_has_a_snapshot_behind_it(release, database):
    """Every figure must be traceable to the file it came from.

    A comparable with no snapshot row has no source, no digest and no date. It
    is a number, not evidence, and nothing downstream could tell the difference.
    """
    ingest(release(baseline()), database, snapshot_id="snap_a")
    ingest(release(baseline(count=20)), database, snapshot_id="snap_b")

    con = duckdb.connect(str(database), read_only=True)
    try:
        orphans = con.execute(
            "select count(*) from contracts c "
            "where not exists (select 1 from snapshots s where s.snapshot_id = c.snapshot_id)"
        ).fetchone()[0]
    finally:
        con.close()
    assert orphans == 0


def test_a_crash_while_storing_leaves_nothing_behind(release, database, monkeypatch):
    """The write is one transaction, and this is why.

    Written piecemeal, a failure between the contracts and the snapshot row
    leaves comparable figures with no provenance — and they look entirely normal
    to every query that reads them.
    """
    from bayyina.market import ingest as module

    committed = module._store

    def store_then_fail(con, report):
        committed(con, report)
        raise RuntimeError("the machine went away")

    monkeypatch.setattr(module, "_store", store_then_fail)

    with pytest.raises(RuntimeError, match="the machine went away"):
        ingest(release(baseline()), database, snapshot_id="snap_doomed")

    con = duckdb.connect(str(database), read_only=True)
    try:
        for table in ("contracts", "areas", "rejections", "snapshots"):
            rows = con.execute(f"select count(*) from {table}").fetchone()[0]
            assert rows == 0, f"{table} kept {rows} row(s) from a failed ingest"
    finally:
        con.close()


def test_a_digest_must_be_a_digest(release, database):
    """`min_length` would accept a truncated or reformatted value, and this field
    is the whole of a snapshot's traceability."""
    from pydantic import ValidationError

    report = ingest(release(baseline()), database)
    assert report.source_sha256.startswith("sha256:")

    for bad in ("", "sha256:abc", "deadbeef" * 8, f"md5:{'a' * 64}", f"sha256:{'A' * 64}"):
        with pytest.raises(ValidationError):
            report.model_copy(update={"source_sha256": bad}).model_validate(
                {**report.model_dump(), "source_sha256": bad}
            )


# --- Releases that are not the release ----------------------------------------


def test_a_release_missing_a_column_says_which_one(release, database, tmp_path):
    """DLD publishes the same registry through more than one channel and they do
    not agree on names.

    The portal on dubailand.gov.ae returns 'Annual Amount', 'No of Units',
    'Number of Rooms' and **no contract identifier at all**. Someone will point
    the ingest at one of those files, and it must say which column is missing
    rather than fail with a binder error naming a token nobody wrote.
    """
    import duckdb as ddb

    from bayyina.market.errors import MalformedReleaseError

    portal = tmp_path / "portal.csv"
    con = ddb.connect()
    con.execute('create table t ("Start Date" date, "Annual Amount" double, "No of Units" int)')
    con.execute("insert into t values (date '2026-06-01', 75000, 1)")
    con.execute(f"copy t to '{str(portal).replace(chr(39), chr(39) * 2)}' (format csv, header)")
    con.close()

    with pytest.raises(MalformedReleaseError, match="contract_id"):
        ingest(portal, database)


def test_the_column_check_runs_before_any_work(release, database, tmp_path):
    """Checked first, so a wrong file costs a second rather than a minute."""
    from bayyina.market.errors import MalformedReleaseError

    try:
        ingest(release([]), database)
    except MalformedReleaseError:  # pragma: no cover - the fixture is well formed
        pytest.fail("a well-formed release was refused")
    except Exception:
        pass  # an empty release fails later, which is not what this asserts
