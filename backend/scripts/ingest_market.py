#!/usr/bin/env python
"""Build the comparables database from a DLD contract release.

    python scripts/ingest_market.py data/raw/rent_contracts_20260226.parquet

Exits non-zero if the release is unusable, so it can gate a build. Nothing here
runs at request time: the 150 ms webhook budget forbids touching nine million
rows during a call, so this is where that work happens instead.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bayyina.market.aggregate import WINDOW_MONTHS, aggregate, export_for_serving
from bayyina.market.errors import IngestError
from bayyina.market.ingest import ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="the DLD contract release (parquet)")
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/market.duckdb"),
        help="where to build, contracts and all (default: data/market.duckdb)",
    )
    parser.add_argument(
        "--serving-database",
        type=Path,
        default=Path("data/comparables.duckdb"),
        help=(
            "the small database the service reads and the image ships "
            "(default: data/comparables.duckdb)"
        ),
    )
    parser.add_argument(
        "--snapshot-id",
        default=None,
        help="name this snapshot; re-running with the same id replaces it",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help=(
            "delete the build database first. DuckDB does not reclaim space, so "
            "re-ingesting into an existing one grows it (359 MB -> 433 MB on a "
            "single re-run) and the checkpoint on close gets slow. The build "
            "database is regenerable, so this is usually what you want"
        ),
    )
    parser.add_argument(
        "--window-months",
        type=int,
        default=WINDOW_MONTHS,
        help=f"the rolling window the medians cover (default: {WINDOW_MONTHS})",
    )
    args = parser.parse_args(argv)

    # Both steps, always. They are separate modules because you may re-aggregate
    # with a different window without re-reading 200 MB — but a snapshot with no
    # comparables answers nothing, so the operator command builds the whole
    # artefact rather than something that looks finished and is not.
    if args.fresh:
        args.database.unlink(missing_ok=True)
        Path(f"{args.database}.wal").unlink(missing_ok=True)

    try:
        report = ingest(args.source, args.database, snapshot_id=args.snapshot_id)
        covered = aggregate(args.database, report.snapshot_id, window_months=args.window_months)
        serving_bytes = export_for_serving(args.database, args.serving_database, report.snapshot_id)
    except IngestError as error:
        print(f"ingest failed: {error}", file=sys.stderr)
        return 1

    print(f"snapshot   {report.snapshot_id}")
    print(f"source     {report.source}")
    print(f"           {report.source_sha256}")
    print(f"read       {report.source_rows:>12,} rows")
    print(f"excluded   {report.excluded_rows:>12,}  not a single-unit residential tenancy")
    print(f"in scope   {report.in_scope_rows:>12,}")
    print(f"rejected   {report.rejected_rows:>12,}  {report.rejection_rate:.3%} of in-scope")
    for reason, rows in report.rejections.items():
        print(f"           {rows:>12,}  {reason}")
    print(f"trimmed    {report.trimmed_rows:>12,}  outside 1.5x IQR within their cell")
    print(f"stored     {report.row_count:>12,} contracts across {report.areas} areas")
    print(f"horizon    {report.data_horizon}  the far edge of this release's data")
    print()
    print(
        f"window     {covered.window_start} .. {covered.window_end}  "
        f"({covered.window_months} months, anchored on the data)"
    )
    print(f"covering   {covered.contracts_in_window:>12,} contracts")
    print(f"cells      {covered.cells:>12,}")
    print(f"quotable   {covered.quotable_cells:>12,}  at or above {covered.answer_floor} contracts")
    print()
    print(f"serving    {args.serving_database}  {serving_bytes / 1e6:.1f} MB")
    print("           comparables, areas and provenance only - no contract rows")
    if not covered.quotable_cells:
        print("nothing is quotable: every cell is under the answer floor", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
