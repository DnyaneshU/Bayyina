"""Materialise the medians a request will read, at build time.

**A `GROUP BY` over 5.3M rows cannot meet a 150 ms webhook budget.** Voice
latency is 20% of the Stage 2 score and our webhook is one of five things
happening between a caller finishing a sentence and hearing a reply, so the
aggregation happens when the image is built and a request only ever reads a
small table.

Two decisions here are load-bearing, and both are about *when*:

**The window ends at the data, not at today.** The release runs to 2026-03-01. A
rolling twelve months to `now()` would quietly slide off the end of it — six
months after publication it would cover 267,252 contracts instead of 567,652,
and would keep shrinking with no error and no signal. The window is anchored to
the snapshot's own horizon, and both ends are recorded so any past answer
reproduces exactly.

**Below the answer floor no median is computed at all.** Not computed and
withheld — never computed. G5 says a thin cell produces no figure, and the
surest way to keep a number from being spoken is for it not to exist. The
contract count is still stored, because "we found only four" is the honest thing
to say and needs the four.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from ..settings import Settings, get_settings
from .errors import IngestError

#: A rolling year. Long enough for a thin neighbourhood to reach a quotable
#: count, short enough that the median still describes the current market.
WINDOW_MONTHS = 12


class SnapshotNotFoundError(IngestError):
    """Asked to aggregate a snapshot the database does not hold."""


class AggregateReport(BaseModel):
    """What one aggregation covered, in the terms the provenance page needs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str
    computed_at: datetime
    window_start: date
    window_end: date
    window_months: int = Field(gt=0)

    #: The G5 floor this table was built under, recorded on the artefact itself.
    answer_floor: int = Field(gt=0)

    contracts_in_window: int = Field(ge=0)
    cells: int = Field(ge=0)
    quotable_cells: int = Field(ge=0)

    #: The quotable cell whose newest contract is oldest. A build can produce a
    #: table that already contains figures too old to quote, and saying so at
    #: build time is cheaper than discovering it per request.
    oldest_quotable_contract: date | None = None


_SCHEMA = """
create table if not exists aggregates (
    snapshot_id         varchar primary key,
    computed_at         timestamptz not null,
    window_start        date    not null,
    window_end          date    not null,
    window_months       integer not null,
    answer_floor        integer not null,
    contracts_in_window bigint  not null,
    cells               bigint  not null,
    quotable_cells      bigint  not null,
    oldest_quotable_contract date
);

create table if not exists comparables (
    snapshot_id        varchar not null,
    area_key           varchar not null,
    property_kind      varchar not null,
    bedrooms           integer not null,
    contract_count     integer not null,
    -- **This cell's** newest contract, not the release's. A cell can trail the
    -- snapshot badly: 11.7% are more than a month behind it and one is 418 days
    -- old inside a release we call 193 days old. Recency is disclosed and it
    -- decides refusals, so it has to be the age of the evidence actually being
    -- quoted rather than the age of the file it arrived in.
    newest_contract    date not null,
    median_annual_rent decimal(12, 2),
    primary key (snapshot_id, area_key, property_kind, bedrooms)
);
"""


def aggregate(
    database: Path,
    snapshot_id: str,
    *,
    window_months: int = WINDOW_MONTHS,
    settings: Settings | None = None,
) -> AggregateReport:
    """Build the comparables table for one snapshot and return what it covers."""
    if window_months <= 0:
        raise ValueError(f"window_months must be positive, not {window_months}")

    settings = settings or get_settings()
    floor = settings.min_contracts_for_answer

    con = duckdb.connect(str(database))
    try:
        con.execute(_SCHEMA)

        row = con.execute(
            "select data_horizon from snapshots where snapshot_id = ?", [snapshot_id]
        ).fetchone()
        if row is None:
            known = [
                found for (found,) in con.execute("select snapshot_id from snapshots").fetchall()
            ]
            raise SnapshotNotFoundError(
                f"no snapshot {snapshot_id!r} in {database}. "
                f"Known: {known or 'none - run the ingest first'}"
            )

        window_end: date = row[0]
        window_start = con.execute(
            f"select (date '{window_end}' - interval {window_months} month)::date"
        ).fetchone()[0]

        con.execute("begin transaction")
        try:
            con.execute("delete from comparables where snapshot_id = ?", [snapshot_id])
            con.execute("delete from aggregates where snapshot_id = ?", [snapshot_id])
            con.execute(
                """
                insert into comparables
                select
                    snapshot_id, area_key, property_kind, bedrooms,
                    count(*) as contract_count,
                    max(contract_start_date) as newest_contract,
                    case when count(*) >= ?
                         then median(annual_rent)::decimal(12, 2) end
                from contracts
                where snapshot_id = ?
                  and contract_start_date > ?
                  and contract_start_date <= ?
                group by snapshot_id, area_key, property_kind, bedrooms
                """,
                [floor, snapshot_id, window_start, window_end],
            )

            covered, cells, quotable, oldest = con.execute(
                """
                select coalesce(sum(contract_count), 0), count(*),
                       count(*) filter (where median_annual_rent is not null),
                       min(newest_contract) filter (where median_annual_rent is not null)
                from comparables where snapshot_id = ?
                """,
                [snapshot_id],
            ).fetchone()

            report = AggregateReport(
                snapshot_id=snapshot_id,
                computed_at=datetime.now(UTC),
                window_start=window_start,
                window_end=window_end,
                window_months=window_months,
                answer_floor=floor,
                contracts_in_window=covered,
                cells=cells,
                quotable_cells=quotable,
                oldest_quotable_contract=oldest,
            )
            columns = (
                "snapshot_id",
                "computed_at",
                "window_start",
                "window_end",
                "window_months",
                "answer_floor",
                "contracts_in_window",
                "cells",
                "quotable_cells",
            )
            con.execute(
                f"insert into aggregates ({', '.join(columns)}) "
                f"values ({', '.join('?' * len(columns))})",
                [getattr(report, column) for column in columns],
            )
            con.execute("commit")
        except Exception:
            con.execute("rollback")
            raise

        return report
    finally:
        con.close()


#: What the running service reads. Everything else stays in the build database.
SERVING_TABLES = ("snapshots", "aggregates", "comparables", "areas")


def export_for_serving(source: Path, target: Path, snapshot_id: str) -> int:
    """Write the small database the service actually reads. Returns its bytes.

    The build database is **343 MB**, almost all of it the 5.3M-row `contracts`
    table, and a request never touches a single row of it. Shipping that inside a
    container would mean a 343 MB image to serve 1,324 numbers.

    It would also put 5.3 million individual tenancy records — a rent, an area, a
    date, a contract id — into every copy of a public image, for no purpose. The
    data is published openly and this is not a disclosure, but the smallest thing
    that answers the question is the right thing to ship.

    Contracts stay in the build database, where re-aggregating over a different
    window and auditing a figure back to its rows are both still possible.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)

    con = duckdb.connect(str(target))
    try:
        literal = str(source).replace("'", "''")
        con.execute(f"attach '{literal}' as build (read_only)")
        for table in SERVING_TABLES:
            con.execute(
                f"create table {table} as select * from build.{table} where snapshot_id = ?",
                [snapshot_id],
            )
        empty = [
            table
            for table in SERVING_TABLES
            if con.execute(f"select count(*) from {table}").fetchone()[0] == 0
        ]
        if empty:
            raise SnapshotNotFoundError(
                f"snapshot {snapshot_id!r} produced an empty serving database: {empty} "
                f"have no rows. Shipping it would boot a service that answers nothing."
            )
        con.execute("detach build")
    finally:
        con.close()

    return target.stat().st_size
