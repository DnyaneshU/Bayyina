"""Answering "what do places like yours rent for" — or declining to.

**No code path here returns a number below the evidence threshold.** That is not
a promise about how carefully the functions are written; it is a property of the
types. `Comparable` refuses to hold a `median_annual_rent` unless its status is
`ok`, so a thin cell cannot produce a figure even by mistake, and a caller cannot
be read a number that four contracts stand behind.

The table is small — 1,324 cells — so the whole of it is loaded at boot and a
request never touches the disk. This is the same shape as the rules corpus: read
once, verified once, held in memory, and the request path does no I/O it could
be blamed for later.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

import duckdb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..settings import Settings, get_settings
from .errors import IngestError
from .normalise import area_key


class ComparableStatus(StrEnum):
    """Why we can or cannot quote a figure. Every value is a legitimate answer."""

    #: Enough recent contracts, recent enough to describe today's market.
    OK = "ok"

    #: Fewer than `min_contracts_for_answer`, or a cell we hold nothing for.
    INSUFFICIENT_DATA = "insufficient_data"

    #: The snapshot's data is older than we are willing to quote, whatever the
    #: cell holds. Freshness is a property of the release, not of the cell.
    STALE = "stale"

    #: We do not recognise the area at all. Distinct from insufficient data: one
    #: means "not enough contracts there", the other "where?".
    UNKNOWN_AREA = "unknown_area"


class MarketDataUnavailableError(IngestError):
    """The comparables table is missing or empty where one was expected."""


class Comparable(BaseModel):
    """One answer about one kind of home in one area.

    The invariant below is the whole of G5 at this layer, and it is enforced by
    construction rather than by discipline.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ComparableStatus
    area_key: str
    area_name: str | None = None
    property_kind: str
    bedrooms: int = Field(ge=0)

    #: How many registered contracts stand behind this. Present for every status,
    #: because "we found only four" is the honest thing to say and needs the four.
    contract_count: int = Field(default=0, ge=0)

    median_annual_rent: Decimal | None = None

    #: False between the answer floor and the full-confidence threshold. The
    #: figure is quotable; its thinness is disclosed alongside it.
    full_confidence: bool = False

    snapshot_id: str
    window_start: date
    window_end: date

    #: How old the newest contract behind this figure is, in days. Spoken aloud,
    #: because "based on data to March" is a fact a resident can weigh.
    age_days: int = Field(ge=0)

    @model_validator(mode="after")
    def _a_figure_requires_a_quotable_status(self) -> Comparable:
        """A number may exist only when we are willing to stand behind it.

        Without this the guarantee lives in whichever branch of whichever
        function last touched the object, which is exactly how a thin figure
        reaches a caller with a citation attached and looks entirely sound.
        """
        if self.status is ComparableStatus.OK:
            if self.median_annual_rent is None:
                raise ValueError("an `ok` comparable must carry a figure")
        else:
            if self.median_annual_rent is not None:
                raise ValueError(
                    f"a {self.status.value!r} comparable must not carry a figure, "
                    f"and this one holds {self.median_annual_rent}"
                )
            if self.full_confidence:
                raise ValueError(f"a {self.status.value!r} comparable has no confidence to report")
        return self


class ComparableStore:
    """The comparables table, read once and held in memory.

    Constructed at boot. A missing or empty table raises here rather than at the
    first request, for the same reason the rules corpus is verified before any
    route exists: a service that starts and then cannot answer is worse than one
    that refuses to start.
    """

    def __init__(
        self,
        database: Path,
        *,
        snapshot_id: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        if not Path(database).exists():
            raise MarketDataUnavailableError(
                f"no comparables database at {Path(database).resolve()}. "
                f"Run `python scripts/ingest_market.py <release.parquet>` to build one."
            )

        con = duckdb.connect(str(database), read_only=True)
        try:
            snapshot_id = snapshot_id or self._latest_snapshot(con)
            row = con.execute(
                "select window_start, window_end, answer_floor from aggregates "
                "where snapshot_id = ?",
                [snapshot_id],
            ).fetchone()
            if row is None:
                raise MarketDataUnavailableError(
                    f"snapshot {snapshot_id!r} has no aggregate. The ingest ran but the "
                    f"aggregation did not, so there is nothing to quote."
                )
            self.snapshot_id = snapshot_id
            self.window_start, self.window_end, self.built_answer_floor = row

            self._cells: dict[tuple[str, str, int], tuple[int, Decimal | None, date]] = {
                (area, kind, bedrooms): (count, median, newest)
                for area, kind, bedrooms, count, median, newest in con.execute(
                    "select area_key, property_kind, bedrooms, contract_count, "
                    "median_annual_rent, newest_contract from comparables "
                    "where snapshot_id = ?",
                    [snapshot_id],
                ).fetchall()
            }
            self._areas: dict[str, str] = dict(
                con.execute(
                    "select area_key, area_name from areas where snapshot_id = ?",
                    [snapshot_id],
                ).fetchall()
            )
        finally:
            con.close()

        if not self._cells:
            raise MarketDataUnavailableError(
                f"snapshot {snapshot_id!r} holds no comparable cells at all"
            )

    @staticmethod
    def _latest_snapshot(con: duckdb.DuckDBPyConnection) -> str:
        row = con.execute(
            "select snapshot_id from aggregates order by window_end desc, computed_at desc limit 1"
        ).fetchone()
        if row is None:
            raise MarketDataUnavailableError(
                "the database holds no aggregated snapshot. Run the ingest."
            )
        return row[0]

    @property
    def areas(self) -> list[str]:
        """Every area we can resolve, by display name."""
        return sorted(self._areas.values())

    def age_days(self, as_of: date) -> int:
        """How old the release is, at its own horizon.

        Snapshot-level, and used by the health check. **A lookup does not use
        this** — see `Comparable.age_days`, which is the age of the cell actually
        being quoted. The two differ by more than a month for 11.7% of cells.
        """
        return max((as_of - self.window_end).days, 0)

    def is_stale(self, as_of: date) -> bool:
        """Whether the release as a whole is past quoting.

        The health check's question. An individual cell can be past quoting while
        the release is not, and that is decided per lookup.
        """
        return self.age_days(as_of) > self._settings.market_snapshot_max_age_days

    def lookup(
        self,
        area: str,
        property_kind: str,
        bedrooms: int,
        *,
        as_of: date | None = None,
    ) -> Comparable:
        """The market figure for one kind of home in one area, or why there is none.

        The order of the checks is deliberate. Staleness is asked first because it
        is a property of the whole release: if the data is too old to quote, no
        cell in it is quotable and saying "not enough contracts" would be both
        wrong and misleading.
        """
        as_of = as_of or date.today()
        key = area_key(area)
        kind = property_kind.strip().casefold()
        count, median, newest = self._cells.get((key, kind, bedrooms), (0, None, self.window_end))

        # **This cell's** recency, not the release's. A cell with 72 contracts
        # whose newest is 418 days old sits inside a release we would otherwise
        # describe as 193 days old, and it is the cell we are about to quote.
        age_days = max((as_of - newest).days, 0)
        common = {
            "area_key": key,
            "area_name": self._areas.get(key),
            "property_kind": kind,
            "bedrooms": bedrooms,
            "snapshot_id": self.snapshot_id,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "age_days": age_days,
        }

        if age_days > self._settings.market_snapshot_max_age_days:
            return Comparable(status=ComparableStatus.STALE, contract_count=count, **common)

        if key not in self._areas:
            return Comparable(status=ComparableStatus.UNKNOWN_AREA, **common)

        if median is None or count < self._settings.min_contracts_for_answer:
            # `median is None` and a low count are the same refusal reached two
            # ways: the aggregate declined to compute one, or this run's floor is
            # higher than the one the table was built under. Either is a no.
            return Comparable(
                status=ComparableStatus.INSUFFICIENT_DATA, contract_count=count, **common
            )

        return Comparable(
            status=ComparableStatus.OK,
            contract_count=count,
            median_annual_rent=median,
            full_confidence=count >= self._settings.min_contracts_for_full_confidence,
            **common,
        )
