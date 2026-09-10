#!/usr/bin/env python
"""Look at a contract release and say whether the ingest can read it.

    python scripts/inspect_release.py ~/Downloads/rent_contracts.csv

DLD publishes the same registry through more than one channel and they do not
agree. The Dubai Pulse bulk file uses `annual_amount` and `no_of_prop`; the
portal on dubailand.gov.ae returns "Annual Amount", "No of Units", "Number of
Rooms" — and **no contract identifier at all**, which is what de-duplicates
multi-property contracts.

So before spending a minute on nine million rows, this answers three questions a
person actually has after clicking Download:

* did the export get truncated?
* which columns are missing, and what are they probably called here?
* how fresh is it — which is the whole reason for downloading a new one

Reads CSV or parquet. Exits non-zero if the ingest would refuse the file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

from bayyina.market.ingest import REQUIRED_COLUMNS, reader_for

#: What the same field is called in the other places DLD publishes it. Used only
#: to suggest a mapping — nothing here is applied automatically, because guessing
#: which column is the rent is exactly the kind of guess that produces a
#: confident wrong verdict.
KNOWN_ALIASES: dict[str, tuple[str, ...]] = {
    "contract_id": ("contract_number", "ejari_contract_number", "contract_no"),
    "line_number": ("line_no", "row_number"),
    "no_of_prop": ("no_of_units", "number_of_units", "units"),
    "annual_amount": ("annual_rent", "annual_amount_aed", "rent_amount"),
    "area_id": ("area_code",),
    "area_name_en": ("area", "area_name", "location"),
    "ejari_property_type_en": ("property_type",),
    "ejari_property_sub_type_en": ("property_sub_type", "property_subtype"),
    "property_usage_en": ("usage", "usage_en", "property_usage"),
    "contract_start_date": ("start_date",),
    "contract_end_date": ("end_date",),
}

#: A bedroom count as its own column, which the Pulse file does not have. Worth
#: reporting because it would replace parsing bedrooms out of free text.
BEDROOM_COLUMNS = ("number_of_rooms", "no_of_rooms", "rooms", "bedrooms")

#: Row counts a paginated web export tends to stop at.
SUSPICIOUS_ROW_COUNTS = (100, 500, 1_000, 5_000, 10_000, 50_000, 100_000)


def normalise(column: str) -> str:
    """`"Number of Rooms"` and `number_of_rooms` are the same column."""
    return "".join(character if character.isalnum() else "_" for character in column.lower()).strip(
        "_"
    )


def read(path: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    literal = str(path).replace("'", "''")
    # The same helper the ingest uses, so the two cannot disagree about which
    # files are readable — the whole point of this script is to predict that.
    con.execute(f"create view source as select * from {reader_for(path)}('{literal}')")
    return con


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="the release to inspect (csv or parquet)")
    args = parser.parse_args(argv)

    if not args.source.exists():
        print(f"no file at {args.source.resolve()}", file=sys.stderr)
        return 1

    con = read(args.source)
    columns = [name for (name, *_) in con.execute("describe source").fetchall()]
    by_normalised = {normalise(name): name for name in columns}
    rows = con.execute("select count(*) from source").fetchone()[0]

    print(f"file       {args.source.name}  ({args.source.stat().st_size / 1e6:.1f} MB)")
    print(f"rows       {rows:,}")
    print(f"columns    {len(columns)}")
    print()

    # --- Truncation ----------------------------------------------------------
    if rows in SUSPICIOUS_ROW_COUNTS:
        print(f"!  {rows:,} is a round number. A paginated export that hits its cap")
        print("   looks exactly like this. Check the portal said it exported everything.")
        print()

    # --- Columns -------------------------------------------------------------
    missing: list[str] = []
    for required in REQUIRED_COLUMNS:
        if required in columns:
            print(f"  ok       {required}")
            continue
        suggestion = next(
            (
                by_normalised[alias]
                for alias in (required, *KNOWN_ALIASES.get(required, ()))
                if alias in by_normalised
            ),
            None,
        )
        if suggestion:
            print(f"  MAP      {required:<30} probably {suggestion!r}")
        else:
            print(f"  MISSING  {required:<30} not present under any name we recognise")
        missing.append(required)

    bonus = [by_normalised[name] for name in BEDROOM_COLUMNS if name in by_normalised]
    if bonus:
        print()
        print(f"  BONUS    {bonus[0]} - a bedroom count as its own column.")
        print("    The Pulse file has none, so bedrooms are parsed out of the sub-type text.")

    print()
    print("all columns present:")
    for name in columns:
        print(f"    {name}")

    # --- Freshness -----------------------------------------------------------
    start = by_normalised.get("contract_start_date") or by_normalised.get("start_date")
    if start:
        low, high, horizon = con.execute(
            f'select min("{start}")::date, max("{start}")::date, '
            f'quantile_cont("{start}", 0.999)::date from source'
        ).fetchone()
        print()
        print(f"start dates  {low} .. {high}")
        print(f"horizon      {horizon}  (99.9th percentile; max is not usable, see D-069)")
        print()
        print("   The reason for downloading a new release is the horizon. Compare it")
        print("   against the one we already hold: 2026-03-01.")

    print()
    if missing:
        print(f"REFUSED - the ingest cannot read this file: {len(missing)} column(s) missing.")
        print("  Renames are cheap to map. A column that is genuinely absent, a contract")
        print("  identifier, say, is a design question rather than a mapping.")
        return 1

    print("READY - the ingest can read this file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
