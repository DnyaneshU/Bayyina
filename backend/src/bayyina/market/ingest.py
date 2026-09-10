"""Turn the DLD contract release into comparables we are willing to quote.

Ingestion is not `read_csv`. **Bad data produces confident wrong verdicts**,
which is the worst failure this product can have: the arithmetic is correct, the
citation is real, the rule is signed, and the answer is nonsense because the
market average came from a labour camp.

Three things are separated deliberately, because conflating them hides problems:

* **Exclusions** - rows that are not a single-unit residential tenancy. Nothing
  is wrong with them; they are simply not comparable to a resident's flat.
* **Rejections** - in-scope rows that are unusable: an impossible rent, a
  contract that ends before it starts. **The rejection rate is the data-quality
  signal**, and it is measured against in-scope rows, not against the file, or
  scope decisions would drown it.
* **Trimming** - in-scope, usable rows sitting far enough from their peers that
  including them would move a median we intend to stand behind.

Measured on `rent_contracts_20260226.parquet` (9,798,685 rows, 2026-09-09).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from .errors import (
    DataQualityError,
    MalformedReleaseError,
    SourceNotFoundError,
    UnknownCategoryError,
)
from .normalise import (
    KNOWN_PROPERTY_TYPES,
    area_key,
    bedrooms_from_sub_type,
    dwelling_kind,
)

# --- Thresholds, all measured rather than guessed ----------------------------

#: Below this, the figure is a deposit, a monthly instalment, or a typo. Measured
#: on residential stock: 35 rows at or below zero, 2,449 below AED 1,000.
RENT_FLOOR = 1_000

#: Above this it is a whole-building agreement wearing a flat's clothes. The
#: file's maximum annual_amount is AED 3,300,037,950.
RENT_CEILING = 10_000_000

#: Tukey's fence. Applied *within* a cell, not across the corpus.
IQR_MULTIPLIER = 1.5

#: A quartile over a handful of contracts describes noise. Below this the cell is
#: left untrimmed, and T2.3's thresholds decide whether it may be quoted at all.
MIN_ROWS_FOR_IQR = 8

#: Above this share of in-scope rows unusable, stop and investigate rather than
#: build on it (plan risk register, T2.1).
MAX_REJECTION_RATE = 0.05

#: An unrecognised property type holding at least this share of the release means
#: DLD renamed a category we depend on.
UNKNOWN_CATEGORY_SHARE = 0.01

#: Every column the ingest reads. Checked before any work happens, because DLD
#: publishes the same registry through more than one channel and they do not
#: agree: the Dubai Pulse bulk file uses these names, while the portal on
#: dubailand.gov.ae returns "Annual Amount", "No of Units", "Number of Rooms" and
#: **no contract identifier at all**. A release that is missing a column should
#: say which one, not fail somewhere inside a query.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "contract_id",
    "line_number",
    "no_of_prop",
    "annual_amount",
    "area_id",
    "area_name_en",
    "ejari_property_type_en",
    "ejari_property_sub_type_en",
    "property_usage_en",
    "contract_start_date",
    "contract_end_date",
)

#: How far the release's data actually runs, estimated robustly.
#:
#: **Not `max()`.** The real release contains a contract starting 2204-10-04, and
#: a rolling twelve-month window anchored on that maximum holds exactly one
#: contract - the whole comparables table, silently emptied by a single typo. A
#: high quantile is unmoved by the 41 rows that are obviously wrong.
HORIZON_QUANTILE = 0.999

#: A contract may legitimately start ahead of the release it appears in: 6,529
#: begin in the six months after 2026-02-26, which is a lease signed early. Past
#: a year it is a date-entry error, and 41 rows say so.
MAX_MONTHS_AFTER_HORIZON = 12

#: Ejari registration began well before this. A start date earlier is a typo, and
#: two rows are.
EARLIEST_PLAUSIBLE_START = "2005-01-01"


class IngestReport(BaseModel):
    """What one ingest did, in the terms the DoD is written in."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str
    computed_at: datetime
    source: str
    #: `sha256:` followed by 64 hex digits. A digest that is merely "long enough"
    #: would let a truncated or differently-formatted value through, and this
    #: field is what ties a comparable figure to the bytes it came from.
    source_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    source_rows: int = Field(ge=0)
    excluded_rows: int = Field(ge=0)
    in_scope_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    trimmed_rows: int = Field(ge=0)
    row_count: int = Field(ge=0)

    #: The far edge of the data, and the anchor for every rolling window built on
    #: it. Recorded so an aggregate reproduces exactly and cannot drift onto
    #: today's date, which the release knows nothing about.
    data_horizon: date

    rejection_rate: float = Field(ge=0.0, le=1.0)
    rejections: dict[str, int] = Field(default_factory=dict)
    areas: int = Field(ge=0)


#: Suffixes we read as parquet. Everything else is treated as delimited text.
PARQUET_SUFFIXES = frozenset({".parquet", ".pq"})


def reader_for(source: Path) -> str:
    """The DuckDB reader for this file.

    The Dubai Pulse bulk release is parquet. The portal on dubailand.gov.ae
    exports CSV, and that is the only channel reachable while Pulse is down - so
    refusing anything but parquet would refuse the only fresh data available.
    """
    if source.suffix.lower() in PARQUET_SUFFIXES:
        return "read_parquet"
    # `read_csv_auto` sniffs the delimiter, the header and the column types.
    return "read_csv_auto"


def file_sha256(path: Path) -> str:
    """Digest of the source, so a snapshot names the exact bytes it came from."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


_SCHEMA = """
create table if not exists snapshots (
    snapshot_id     varchar primary key,
    computed_at     timestamptz not null,
    source          varchar not null,
    source_sha256   varchar not null,
    source_rows     bigint  not null,
    excluded_rows   bigint  not null,
    in_scope_rows   bigint  not null,
    rejected_rows   bigint  not null,
    trimmed_rows    bigint  not null,
    row_count       bigint  not null,
    data_horizon    date    not null,
    rejection_rate  double  not null
);

create table if not exists rejections (
    snapshot_id varchar not null,
    reason      varchar not null,
    rows        bigint  not null,
    primary key (snapshot_id, reason)
);

create table if not exists areas (
    snapshot_id varchar not null,
    area_key    varchar not null,
    area_name   varchar not null,
    primary key (snapshot_id, area_key)
);

create table if not exists contracts (
    snapshot_id         varchar not null,
    contract_id         varchar not null,
    area_key            varchar not null,
    area_name           varchar not null,
    -- The raw DLD label, kept for provenance; `property_kind` is what a caller
    -- asks by, and what a comparable is grouped on.
    property_type       varchar not null,
    property_kind       varchar not null,
    bedrooms            integer not null,
    annual_rent         decimal(12, 2) not null,
    contract_start_date date not null,
    contract_end_date   date not null,
    primary key (snapshot_id, contract_id)
);
"""


def ingest(
    source: Path,
    database: Path,
    *,
    snapshot_id: str | None = None,
    computed_at: datetime | None = None,
    max_rejection_rate: float = MAX_REJECTION_RATE,
) -> IngestReport:
    """Load one DLD release into `database` and return what happened.

    Raises `DataQualityError` above `max_rejection_rate`, and
    `UnknownCategoryError` when the release contains a large property type the
    scope rules have never seen. Both stop the ingest: a comparable table built
    from data nobody looked at is worse than no table, because it looks fine.
    """
    source = Path(source)
    if not source.exists():
        raise SourceNotFoundError(f"no contract release at {source.resolve()}")

    snapshot_id = snapshot_id or f"snap_{uuid4().hex[:12]}"
    computed_at = computed_at or datetime.now(UTC)
    # Digested before anything is written, so reading 200 MB happens outside the
    # transaction rather than holding it open.
    digest = file_sha256(source)

    database.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(database))
    try:
        con.execute(_SCHEMA)
        # DuckDB cannot prepare DDL, so the path is inlined. It is escaped as a
        # SQL string literal rather than interpolated raw: this is a local file
        # path today, but it will one day be a value someone passes in. The
        # machine this was written on has an apostrophe in its home directory,
        # which found the unescaped version immediately.
        literal = str(source).replace("'", "''")
        con.execute(
            f"create or replace temp view source as select * from {reader_for(source)}('{literal}')"
        )

        _require_columns(con)
        source_rows = con.execute("select count(*) from source").fetchone()[0]
        _guard_against_renamed_categories(con, source_rows)
        _build_lookups(con)
        horizon = _stage(con)

        in_scope_rows, rejected_rows = con.execute(
            "select count(*), count(rejection) from staged"
        ).fetchone()
        rejection_rate = rejected_rows / in_scope_rows if in_scope_rows else 0.0

        if rejection_rate > max_rejection_rate:
            raise DataQualityError(
                f"{rejected_rows:,} of {in_scope_rows:,} in-scope rows were unusable "
                f"({rejection_rate:.2%}, limit {max_rejection_rate:.0%}). Stop and "
                f"investigate before building comparables on this release."
            )

        trimmed_rows, row_count, areas = _trim(con)
        report = IngestReport(
            snapshot_id=snapshot_id,
            computed_at=computed_at,
            source=source.name,
            source_sha256=digest,
            source_rows=source_rows,
            excluded_rows=source_rows - in_scope_rows,
            in_scope_rows=in_scope_rows,
            rejected_rows=rejected_rows,
            trimmed_rows=trimmed_rows,
            row_count=row_count,
            data_horizon=horizon,
            rejection_rate=rejection_rate,
            rejections=dict(
                con.execute(
                    "select rejection, count(*) from staged "
                    "where rejection is not null group by 1 order by 2 desc"
                ).fetchall()
            ),
            areas=areas,
        )

        # One transaction. Written piecemeal, a crash between the contracts and
        # the snapshot row leaves comparable figures in the database with **no
        # provenance** - no source, no digest, no date. A figure that cannot be
        # traced to a file is not evidence, and it would look entirely normal to
        # every query that reads it.
        con.execute("begin transaction")
        try:
            _store(con, report)
            con.execute("commit")
        except Exception:
            con.execute("rollback")
            raise

        return report
    finally:
        con.close()


def _require_columns(con: duckdb.DuckDBPyConnection) -> None:
    """Refuse a release that is missing a column, and say which.

    Checked first, before nine million rows are touched. Without it a renamed
    column surfaces as a binder error naming a token nobody wrote, several
    functions deep.
    """
    # `describe` returns six columns per row; only the first is the name.
    present = {row[0] for row in con.execute("describe source").fetchall()}
    missing = [column for column in REQUIRED_COLUMNS if column not in present]
    if missing:
        raise MalformedReleaseError(
            f"this release is missing {missing}. It has: {sorted(present)}. "
            f"DLD publishes the same registry under different column names in "
            f"different places - run `python scripts/inspect_release.py <file>` "
            f"to see what needs mapping."
        )


def _guard_against_renamed_categories(con: duckdb.DuckDBPyConnection, source_rows: int) -> None:
    """Stop if a large property type is one the scope rules have never seen.

    Scope is an allowlist, which is the safe default - but it fails silently in
    one direction. If DLD renames `Flat` to `Apartment`, five million rows leave
    scope, the ingest reports a small clean table, and nothing looks wrong.
    """
    seen = con.execute(
        """
        select trim(ejari_property_type_en) as property_type, count(*) as rows
        from source
        where property_usage_en = 'Residential' and ejari_property_type_en is not null
        group by 1 order by rows desc
        """
    ).fetchall()
    threshold = source_rows * UNKNOWN_CATEGORY_SHARE
    surprises = [
        (name, rows)
        for name, rows in seen
        if rows >= threshold and name.casefold() not in KNOWN_PROPERTY_TYPES
    ]
    if surprises:
        described = ", ".join(f"{name!r} ({rows:,} rows)" for name, rows in surprises)
        raise UnknownCategoryError(
            f"this release contains property types the scope rules have never seen: "
            f"{described}. Decide whether each is a dwelling before ingesting, or a "
            f"category rename will silently empty the comparable table."
        )


def _build_lookups(con: duckdb.DuckDBPyConnection) -> None:
    """Apply the Python normalisation rules to the source's distinct values.

    A few hundred rows go through Python; nine million go through a join. The
    rule therefore has one implementation, and there is no SQL transliteration
    of it to keep in step.
    """
    areas = [
        (area_id, name, area_key(name))
        for area_id, name in con.execute(
            "select distinct area_id, area_name_en from source where area_name_en is not null"
        ).fetchall()
        if name.strip()
    ]
    con.execute(
        "create or replace temp table area_map "
        "(area_id bigint, area_name varchar, area_key varchar)"
    )
    con.executemany("insert into area_map values (?, ?, ?)", areas)

    sub_types = [
        (sub_type, bedrooms)
        for (sub_type,) in con.execute(
            "select distinct ejari_property_sub_type_en from source "
            "where ejari_property_sub_type_en is not null"
        ).fetchall()
        if (bedrooms := bedrooms_from_sub_type(sub_type)) is not None
    ]
    con.execute("create or replace temp table sub_type_map (sub_type varchar, bedrooms integer)")
    con.executemany("insert into sub_type_map values (?, ?)", sub_types)

    dwellings = [
        (name, kind)
        for (name,) in con.execute(
            "select distinct trim(ejari_property_type_en) from source "
            "where ejari_property_type_en is not null"
        ).fetchall()
        if (kind := dwelling_kind(name)) is not None
    ]
    con.execute(
        "create or replace temp table dwelling_type (property_type varchar, property_kind varchar)"
    )
    con.executemany("insert into dwelling_type values (?, ?)", dwellings)


def _stage(con: duckdb.DuckDBPyConnection) -> date:
    """Narrow the release to scope, de-duplicate it, and judge every row.

    Scope is the intersection of three conditions, each of which admits junk on
    its own:

    * residential usage - includes labour camps and staff accommodation
    * a dwelling property type - 'Studio' still appears under 'Labor Camps'
    * a sub-type carrying a bedroom count - 'Room in labor Camp' still appears
      under 'Flat'

    `no_of_prop = 1` is the condition the plan did not have and needs most.
    `annual_amount` is the **whole-contract** figure: for a contract covering ten
    flats it is roughly ten times the rent of any one of them, and the ten lines
    each repeat that same total. 1,375,195 residential rows are multi-property.
    Left in, they inflate every median and count one contract ten times.

    The `row_number` filter is belt and braces: `no_of_prop` equals the line
    count for 99.94% of contracts and no contract's lines disagree with one
    another, but 5,263 contracts do not match, and a duplicated tenancy must not
    reach a median on the strength of a 99.94% assumption.

    Returns the snapshot's **horizon** - how far its data actually runs - because
    every rolling window built on this snapshot has to be anchored to the data
    rather than to the day someone happens to run a query.
    """
    con.execute(
        """
        create or replace temp table scoped as
        select
            s.contract_id,
            a.area_key,
            a.area_name,
            trim(s.ejari_property_type_en) as property_type,
            d.property_kind,
            t.bedrooms,
            s.annual_amount,
            s.contract_start_date,
            s.contract_end_date,
            row_number() over (
                partition by s.contract_id order by s.line_number
            ) as line_rank
        from source s
        join dwelling_type d on trim(s.ejari_property_type_en) = d.property_type
        join sub_type_map  t on s.ejari_property_sub_type_en = t.sub_type
        join area_map      a on s.area_id = a.area_id
        where s.property_usage_en = 'Residential'
          and s.no_of_prop = 1
        """
    )

    # Computed before anything is judged, and from the scoped rows only, so that
    # commercial stock and labour camps cannot move the horizon of a residential
    # snapshot.
    horizon = con.execute(
        f"""
        select quantile_cont(contract_start_date, {HORIZON_QUANTILE})::date
        from scoped where line_rank = 1 and contract_start_date is not null
        """
    ).fetchone()[0]

    con.execute(
        f"""
        create or replace temp table staged as
        select
            contract_id, area_key, area_name, property_type, property_kind, bedrooms,
            annual_amount, contract_start_date, contract_end_date,
            case
                when contract_start_date is null or contract_end_date is null
                    then 'missing_dates'
                when contract_end_date <= contract_start_date
                    then 'end_not_after_start'
                when contract_start_date < date '{EARLIEST_PLAUSIBLE_START}'
                    then 'start_before_ejari'
                when contract_start_date
                     > date '{horizon}' + interval {MAX_MONTHS_AFTER_HORIZON} month
                    then 'start_beyond_horizon'
                when annual_amount is null          then 'missing_rent'
                when annual_amount <= 0             then 'non_positive_rent'
                when annual_amount < {RENT_FLOOR}   then 'rent_below_floor'
                when annual_amount > {RENT_CEILING} then 'rent_above_ceiling'
                else null
            end as rejection
        from scoped
        where line_rank = 1
        """
    )
    return horizon


def _trim(con: duckdb.DuckDBPyConnection) -> tuple[int, int, int]:
    """Fence each cell and materialise what survives.

    Returns `(trimmed, kept, areas)`. Trimming is per
    `(area, property type, bedrooms, year)`. The year matters: a 2-bed flat in Al
    Barsha First had a median of AED 90,000 in 2017, 65,000 in 2021 and 88,000 in
    2026. A fence drawn across the whole corpus describes no year in it, and
    would read a normal 2026 contract as an outlier of 2021.
    """
    con.execute(
        f"""
        create or replace temp table kept as
        with usable as (
            select *, year(contract_start_date) as contract_year
            from staged where rejection is null
        ),
        fence as (
            select
                area_key, property_type, bedrooms, contract_year,
                count(*) as n,
                quantile_cont(annual_amount, 0.25) as q1,
                quantile_cont(annual_amount, 0.75) as q3
            from usable
            group by 1, 2, 3, 4
        )
        select u.*
        from usable u
        join fence f using (area_key, property_type, bedrooms, contract_year)
        where f.n < {MIN_ROWS_FOR_IQR}
           or u.annual_amount between f.q1 - {IQR_MULTIPLIER} * (f.q3 - f.q1)
                                 and f.q3 + {IQR_MULTIPLIER} * (f.q3 - f.q1)
        """
    )
    return con.execute(
        """
        select
            (select count(*) from staged where rejection is null)
                - (select count(*) from kept),
            (select count(*) from kept),
            (select count(distinct area_key) from kept)
        """
    ).fetchone()


def _store(con: duckdb.DuckDBPyConnection, report: IngestReport) -> None:
    """Write one snapshot and everything belonging to it.

    Called inside a transaction. Replacing rather than appending means a re-run
    after a fixed bug corrects a snapshot in place instead of doubling it.
    """
    snapshot_id = report.snapshot_id
    for table in ("contracts", "areas", "rejections"):
        con.execute(f"delete from {table} where snapshot_id = ?", [snapshot_id])

    con.execute(
        """
        insert into contracts
        select ?, contract_id, area_key, area_name, property_type, property_kind,
               bedrooms, annual_amount::decimal(12, 2),
               contract_start_date, contract_end_date
        from kept
        """,
        [snapshot_id],
    )
    # Where one neighbourhood is recorded under several spellings, show a person
    # the cased one. `min()` would put "AL QUSAIS" in an evidence pack, which is
    # DLD's data entry showing through to a resident.
    con.execute(
        """
        insert into areas
        select ?, area_key, arg_min(area_name, (area_name = upper(area_name))::int)
        from kept group by area_key
        """,
        [snapshot_id],
    )
    con.execute(
        "insert into rejections select ?, rejection, count(*) from staged "
        "where rejection is not null group by rejection",
        [snapshot_id],
    )
    # Columns named, not positional. Adding `data_horizon` to the table silently
    # left an 11-placeholder insert against 12 columns, and the failure surfaced
    # three tests away from the change that caused it.
    columns = (
        "snapshot_id",
        "computed_at",
        "source",
        "source_sha256",
        "source_rows",
        "excluded_rows",
        "in_scope_rows",
        "rejected_rows",
        "trimmed_rows",
        "row_count",
        "data_horizon",
        "rejection_rate",
    )
    con.execute(
        f"insert or replace into snapshots ({', '.join(columns)}) "
        f"values ({', '.join('?' * len(columns))})",
        [getattr(report, column) for column in columns],
    )
