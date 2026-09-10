"""A small, hand-built release that contains every hazard the real one does.

The real file is 9.8 million rows and 200 MB, is gitignored, and is not present
in CI. Testing the *mechanisms* against it would be slow and, worse, would leave
the mechanisms untested wherever the release happens not to exercise them.

So every row here exists because it is a specific failure we have seen in the
real data, and each one is named. `tests/market/test_release.py` then checks the
findings that only the real file can support.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

#: Column order matches the DLD release. Only the columns ingest reads.
COLUMNS = (
    "contract_id varchar",
    "line_number bigint",
    "no_of_prop bigint",
    "annual_amount double",
    "area_id bigint",
    "area_name_en varchar",
    "ejari_property_type_en varchar",
    "ejari_property_sub_type_en varchar",
    "property_usage_en varchar",
    "contract_start_date date",
    "contract_end_date date",
)

START = date(2025, 3, 1)
END = date(2026, 2, 28)


def row(
    contract_id: str,
    *,
    rent: float = 60_000,
    area_id: int = 368,
    area: str = "Al Barsha First",
    property_type: str = "Flat",
    sub_type: str = "2 bed rooms+hall",
    usage: str = "Residential",
    line: int = 1,
    properties: int = 1,
    start: date = START,
    end: date = END,
) -> tuple:
    return (
        contract_id,
        line,
        properties,
        rent,
        area_id,
        area,
        property_type,
        sub_type,
        usage,
        start,
        end,
    )


def build_release(path: Path, rows: list[tuple]) -> Path:
    """Write `rows` as a parquet file shaped like the DLD release."""
    con = duckdb.connect()
    con.execute(f"create table release ({', '.join(COLUMNS)})")
    con.executemany(f"insert into release values ({', '.join('?' * len(COLUMNS))})", rows)
    literal = str(path).replace("'", "''")
    con.execute(f"copy release to '{literal}' (format parquet)")
    con.close()
    return path


def baseline(count: int = 40, rent: float = 60_000) -> list[tuple]:
    """Enough ordinary contracts in one cell for a quartile to mean something.

    The spread is deliberately realistic. An early version stepped by AED 100,
    which made the interquartile range so narrow that every other row in these
    tests read as an outlier — a fixture that would have "proved" the fence
    worked by clipping everything put in front of it.
    """
    return [row(f"CRT_OK_{i}", rent=rent + i * 1_000) for i in range(count)]


@pytest.fixture
def release(tmp_path: Path):
    """Build a release from the given rows and return its path."""

    def _build(rows: list[tuple]) -> Path:
        return build_release(tmp_path / "release.parquet", rows)

    return _build


@pytest.fixture
def database(tmp_path: Path) -> Path:
    return tmp_path / "market.duckdb"


@pytest.fixture
def market(release, database):
    """An ingested *and* aggregated database, built from the given rows.

    Aggregation is a separate step in production too — you may re-aggregate with
    a different window without re-reading a 200 MB release — but a snapshot with
    no comparables answers nothing, so the tests always build both.
    """
    from bayyina.market.aggregate import aggregate
    from bayyina.market.ingest import ingest

    def _build(rows: list[tuple], *, settings=None, snapshot_id: str = "snap_test", **kwargs):
        ingest_report = ingest(release(rows), database, snapshot_id=snapshot_id)
        aggregate_report = aggregate(database, snapshot_id, settings=settings, **kwargs)
        return database, ingest_report, aggregate_report

    return _build


def cell(
    count: int,
    *,
    rent: float = 60_000,
    area: str = "Al Barsha First",
    area_id: int = 368,
    sub_type: str = "2 bed rooms+hall",
    property_type: str = "Flat",
    prefix: str = "C",
    start: date = START,
) -> list[tuple]:
    """`count` contracts in one (area, kind, bedrooms) cell.

    The rent steps by AED 1,000 so the interquartile range is realistic — a
    narrow spread makes the outlier fence clip everything and proves nothing.
    """
    return [
        row(
            f"CRT_{prefix}_{i}",
            rent=rent + i * 1_000,
            area=area,
            area_id=area_id,
            sub_type=sub_type,
            property_type=property_type,
            start=start,
        )
        for i in range(count)
    ]
