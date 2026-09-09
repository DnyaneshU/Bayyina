"""Explore the DLD rent contracts parquet.

Usage:
    python scripts/explore.py                     # preset overview
    python scripts/explore.py "SELECT ..."        # your own SQL, table is `rent`
    python scripts/explore.py --csv out.csv "SELECT ..."   # export to CSV
    python scripts/explore.py --areas barsha      # find area names matching text
    python scripts/explore.py --market "Al Barsha First" "2 bed"

The parquet is exposed as a view called `rent`. A cleaned view `clean` is also
available: residential only, plausible rents, last 12 months of the snapshot.
"""

import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RELATIVE_PARQUET = "data/raw/rent_contracts_20260226.parquet"
PARQUET = ROOT / RELATIVE_PARQUET
SNAPSHOT = "2026-02-26"


def connect() -> duckdb.DuckDBPyConnection:
    """Open DuckDB with the parquet exposed as `rent` and a cleaned `clean` view.

    We chdir to the project root and reference the file by a relative path. The
    home directory here contains an apostrophe ("Dnyanesh's Asus") which breaks a
    SQL string literal, and doubling the quote confuses DuckDB's path parser.
    A relative path avoids the problem entirely rather than escaping around it.
    """
    if not PARQUET.exists():
        sys.exit(f"Not found: {PARQUET}\nDownload the parquet release asset first.")
    os.chdir(ROOT)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW rent AS SELECT * FROM '{RELATIVE_PARQUET}'")
    con.execute(
        f"""CREATE VIEW clean AS SELECT * FROM rent
            WHERE property_usage_en = 'Residential'
              AND annual_amount BETWEEN 1000 AND 10000000
              AND area_name_en IS NOT NULL
              AND ejari_property_sub_type_en IS NOT NULL
              AND contract_start_date >= DATE '{SNAPSHOT}' - INTERVAL 12 MONTH"""
    )
    return con


def show(con, sql: str, limit: int = 40) -> None:
    """Print a query result as an aligned table."""
    rows = con.execute(sql).fetchall()
    cols = [d[0] for d in con.description]
    if not rows:
        print("  (no rows)")
        return
    widths = [
        max(
            len(str(c)),
            max(len(f"{r[i]:,}" if isinstance(r[i], int) else str(r[i])) for r in rows[:limit]),
        )
        for i, c in enumerate(cols)
    ]
    # ASCII separators only: the Windows console defaults to cp1252 and cannot
    # encode box-drawing characters.
    print("  " + " | ".join(c.ljust(w) for c, w in zip(cols, widths, strict=True)))
    print("  " + "-+-".join("-" * w for w in widths))
    for r in rows[:limit]:
        cells = [f"{v:,}" if isinstance(v, int) else str(v) for v in r]
        print("  " + " | ".join(c.ljust(w) for c, w in zip(cells, widths, strict=True)))
    if len(rows) > limit:
        print(f"  ... {len(rows) - limit:,} more rows")


def overview(con) -> None:
    print("\n=== SIZE ===")
    show(con, "SELECT count(*) AS total_contracts FROM rent")
    show(con, "SELECT count(*) AS residential_last_12mo FROM clean")

    print("\n=== SAMPLE ROW ===")
    row = con.execute(
        """SELECT contract_id, area_name_en, ejari_property_type_en,
                  ejari_property_sub_type_en, annual_amount, actual_area,
                  contract_start_date, contract_end_date, contract_reg_type_en
           FROM clean LIMIT 1"""
    ).fetchone()
    for name, value in zip([d[0] for d in con.description], row, strict=True):
        print(f"  {name:<30} {value}")

    print("\n=== TOP AREAS (residential, last 12 months) ===")
    show(
        con,
        """SELECT area_name_en AS area, count(*) AS contracts,
                        round(median(annual_amount)) AS median_rent
                 FROM clean GROUP BY 1 ORDER BY contracts DESC LIMIT 15""",
    )

    print("\n=== PROPERTY SUB-TYPES (this is where bedrooms live) ===")
    show(
        con,
        """SELECT ejari_property_sub_type_en AS sub_type, count(*) AS contracts,
                        round(median(annual_amount)) AS median_rent
                 FROM clean GROUP BY 1 ORDER BY contracts DESC LIMIT 15""",
    )

    print("\n=== DATA QUALITY (all residential, before cleaning) ===")
    show(
        con,
        """SELECT count(*) AS rows,
                    sum(CASE WHEN annual_amount < 1000 THEN 1 ELSE 0 END) AS below_1k,
                    sum(CASE WHEN annual_amount > 10000000 THEN 1 ELSE 0 END) AS above_10m,
                    round(median(annual_amount)) AS median,
                    round(avg(annual_amount)) AS mean
                 FROM rent WHERE property_usage_en = 'Residential'""",
    )
    print("  ^ mean is ~7x median: outliers. This is why we use median.")


def areas(con, needle: str) -> None:
    print(f"\n=== AREAS MATCHING '{needle}' ===")
    show(
        con,
        f"""SELECT area_name_en AS area, count(*) AS contracts,
                         round(median(annual_amount)) AS median_rent
                  FROM clean WHERE area_name_en ILIKE '%{needle}%'
                  GROUP BY 1 ORDER BY contracts DESC""",
    )


def market(con, area: str, sub_type: str) -> None:
    print(f"\n=== COMPARABLE: {area} - {sub_type} ===")
    show(
        con,
        f"""SELECT count(*) AS contracts,
                    round(median(annual_amount)) AS median_rent,
                    round(quantile_cont(annual_amount, 0.25)) AS q1,
                    round(quantile_cont(annual_amount, 0.75)) AS q3,
                    round(min(annual_amount)) AS min, round(max(annual_amount)) AS max
                  FROM clean
                  WHERE area_name_en = '{area}'
                    AND lower(ejari_property_sub_type_en) LIKE lower('{sub_type}%')""",
    )


def main() -> None:
    args = sys.argv[1:]
    con = connect()

    if not args:
        overview(con)
    elif args[0] == "--areas":
        areas(con, args[1])
    elif args[0] == "--market":
        market(con, args[1], args[2])
    elif args[0] == "--csv":
        out, sql = args[1], args[2]
        con.execute(f"COPY ({sql}) TO '{out}' (HEADER, DELIMITER ',')")
        print(f"Wrote {out}")
    else:
        show(con, args[0])


if __name__ == "__main__":
    main()
