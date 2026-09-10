"""Findings only the real release can support.

The DLD file is 200 MB and gitignored, so these skip where it is absent — which
includes CI. That is a deliberate and stated limit: the mechanisms are covered by
`test_ingest.py` against a fixture that runs everywhere, and these are the claims
about *this dataset* that would otherwise be assertions in a document nobody
re-checks.

Run them before shipping a new release:

    pytest tests/market/test_release.py -v

If a release lands and one of these fails, the data changed shape and the scope
rules need a decision — which is exactly the moment we want to hear about it,
rather than after a resident has been quoted a labour camp's rent.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from bayyina.market.ingest import ingest
from bayyina.market.normalise import area_key

RELEASE = Path(__file__).resolve().parents[2] / "data" / "raw" / "rent_contracts_20260226.parquet"

pytestmark = [
    pytest.mark.dataset,
    pytest.mark.skipif(
        not RELEASE.exists(),
        reason=f"the DLD release is not present at {RELEASE} (200 MB, gitignored)",
    ),
]

#: The release these numbers were measured against. A different file is not a
#: failure; it means these expectations need re-measuring.
EXPECTED_SHA256 = "sha256:72d347b23f123166b622bc88406d3b2dda8e973ac8e5440e94f61161d47c7715"
EXPECTED_ROWS = 9_798_685

#: What a flat in Dubai plausibly costs per year. Wide on purpose: the point is
#: to catch a labour-camp figure, not to encode a market view.
PLAUSIBLE_FLAT_RENT = (10_000, 400_000)


@pytest.fixture(scope="module")
def ingested(tmp_path_factory) -> tuple:
    database = tmp_path_factory.mktemp("release") / "market.duckdb"
    report = ingest(RELEASE, database, snapshot_id="snap_test")
    con = duckdb.connect(str(database), read_only=True)
    yield report, con
    con.close()


def test_the_release_is_the_one_these_numbers_came_from(ingested):
    report, _ = ingested
    assert report.source_rows == EXPECTED_ROWS
    assert report.source_sha256 == EXPECTED_SHA256


def test_the_rejection_rate_is_under_the_limit(ingested):
    """The DoD's number. Expected around 0.02%; the plan budgets 5%."""
    report, _ = ingested
    assert report.rejection_rate < 0.05
    assert report.rejected_rows > 0, "a release with no bad rows means the checks stopped running"


def test_an_industrial_area_returns_a_flats_rent(ingested):
    """**The failure that would hurt the exact residents this is built for.**

    Jabal Ali Industrial First is where people live next to where they work.
    Before scope rules, `property_usage_en = 'Residential'` there has a median of
    AED 829,720, because most of it is labour-camp blocks. A caller asking
    whether their AED 32,000 rent may rise to 38,000 would have been told the
    market rate was over three quarters of a million — and told it with a
    correct citation and signed arithmetic.
    """
    _, con = ingested
    low, high = PLAUSIBLE_FLAT_RENT

    rows = con.execute(
        """
        select area_name, bedrooms, count(*) as n, median(annual_rent) as median_rent
        from contracts
        where area_key like 'jabal ali industrial%'
        group by 1, 2 having count(*) >= 30
        """
    ).fetchall()

    assert rows, "no comparable cells at all for Jabal Ali Industrial"
    for area, bedrooms, _n, median_rent in rows:
        assert low <= median_rent <= high, (
            f"{area} {bedrooms}-bed median is AED {median_rent:,.0f}, which is not a "
            f"flat's rent — labour-camp or whole-block contracts are getting through"
        )


def test_every_area_keeps_its_own_identity(ingested):
    """No two genuinely different neighbourhoods may share a key.

    That is a property of the rule *and this dataset*, not of the rule alone, so
    it is checked against the real 213 area names rather than assumed. On the
    2026-02-26 release exactly one pair merges: 'AL QUSAIS' and 'Al Qusais',
    which are the same place recorded under two codes.
    """
    con = duckdb.connect()
    try:
        names = [
            name
            # Parameterised, not interpolated. This machine's home directory
            # contains an apostrophe, which is exactly the case the escaping in
            # `ingest` exists for — and this test found it the hard way.
            for (name,) in con.execute(
                "select distinct area_name_en from read_parquet(?) where area_name_en is not null",
                [str(RELEASE)],
            ).fetchall()
            if name.strip()
        ]
    finally:
        con.close()

    # Names are kept verbatim. Case-folding them here would erase the very
    # difference under test and the check would pass on an empty result.
    merged: dict[str, set[str]] = {}
    for name in names:
        merged.setdefault(area_key(name), set()).add(name.strip())

    collisions = {key: sorted(found) for key, found in merged.items() if len(found) > 1}
    assert collisions == {"al qusais": ["AL QUSAIS", "Al Qusais"]}, (
        f"the area key merges neighbourhoods it should not: {collisions}"
    )


def test_the_familiar_cells_look_like_dubai(ingested):
    """A sanity check a person can read.

    These are neighbourhoods anyone in Dubai can price from memory. If the
    pipeline silently breaks, this is the test that reads wrong to a human before
    any threshold notices.
    """
    _, con = ingested
    rows = dict(
        con.execute(
            """
            select area_key || ' ' || bedrooms::varchar, median(annual_rent)
            from contracts
            where property_type = 'Flat'
              and area_key in ('al barsha first', 'marsa dubai')
              and contract_start_date >= date '2025-09-09'
            group by 1
            """
        ).fetchall()
    )

    assert 60_000 <= rows["al barsha first 1"] <= 110_000
    assert 70_000 <= rows["al barsha first 2"] <= 140_000
    assert rows["marsa dubai 1"] > rows["al barsha first 1"], "the Marina is not cheaper"


def test_the_whole_block_contracts_are_gone(ingested):
    """1,375,195 residential rows cover more than one property, and their
    `annual_amount` is the total for all of them."""
    _, con = ingested
    duplicated = con.execute(
        "select count(*) from (select contract_id from contracts group by 1 having count(*) > 1)"
    ).fetchone()[0]
    assert duplicated == 0


def test_enough_survives_to_be_worth_quoting(ingested):
    """Scope rules that are too strict fail as badly as ones that are too loose,
    and are harder to notice — a caller is simply told there is no data."""
    report, con = ingested
    assert report.row_count > 5_000_000
    assert report.areas > 150

    thick_cells = con.execute(
        """
        select count(*) from (
            select 1 from contracts
            where contract_start_date >= date '2025-09-09'
            group by area_key, property_type, bedrooms having count(*) >= 30
        )
        """
    ).fetchone()[0]
    assert thick_cells > 200, f"only {thick_cells} cells could be quoted with confidence"
