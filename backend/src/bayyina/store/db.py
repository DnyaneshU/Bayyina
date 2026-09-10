"""The database, and the migrations that shape it.

SQLite, deliberately. The whole product is one container serving one city's
rental rules; a separate database server would be an operational dependency
bought with nothing. What SQLite does need is configuring, and the defaults are
wrong for a service answering concurrent phone calls:

* **WAL.** The rollback journal takes a database-wide write lock, so one caller
  whose case is being written blocks every reader. WAL lets readers continue
  through a write, which is the difference between a pause and dead air.
* **A busy timeout.** Without one, a contended write raises `database is locked`
  immediately rather than waiting the few milliseconds it would take. That
  becomes an exception in the middle of a call.
* **Foreign keys.** Off by default in SQLite, which surprises everyone once. A
  deadline pointing at a case that does not exist is not a row we want.

Migrations are forward-only, numbered, and idempotent: applied ones are recorded
and skipped. There is no `down`. A rollback of a schema change on live data is a
data-loss event dressed as a convenience, and the honest recovery is a new
forward migration.
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

#: Where the numbered `.sql` files live. Read from the installed package, so a
#: container that shipped without them fails at migration time rather than
#: silently running against an empty schema.
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

#: How long a writer waits for a contended lock before giving up. Five seconds
#: is far longer than any write here takes, and still short enough that a real
#: deadlock surfaces rather than hanging the request.
BUSY_TIMEOUT_MS = 5_000


class StoreError(RuntimeError):
    """Base class for storage failures."""


class MigrationError(StoreError):
    """The schema could not be brought to the version the code expects."""


def get_db(path: Path | str) -> sqlite3.Connection:
    """Open the case store, configured for a service rather than a script."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        path,
        timeout=BUSY_TIMEOUT_MS / 1000,
        # `Store` opens one connection per thread, so cross-thread use should
        # not happen. This stays False only so that shutdown, which runs on a
        # different thread from the handlers, can close them all. Sharing a
        # connection between threads is the bug this whole module is shaped
        # around - see `Store`.
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row

    connection.execute("pragma journal_mode = wal")
    connection.execute(f"pragma busy_timeout = {BUSY_TIMEOUT_MS}")
    connection.execute("pragma foreign_keys = on")
    return connection


def _applied(db: sqlite3.Connection) -> set[str]:
    db.execute(
        """
        create table if not exists schema_migrations (
            name       text primary key,
            applied_at text not null default (datetime('now'))
        )
        """
    )
    return {row["name"] for row in db.execute("select name from schema_migrations")}


def migration_files() -> list[Path]:
    """The numbered migrations, in order.

    Sorted by filename, which is why they are numbered rather than named. A
    directory listing has no inherent order and applying `002` before `001`
    would fail in a way that depends on the filesystem.
    """
    if not MIGRATIONS_DIR.is_dir():
        raise MigrationError(
            f"no migrations directory at {MIGRATIONS_DIR}. `pip install .` copies "
            f"only .py unless package-data says otherwise, so this is what a "
            f"missing declaration looks like."
        )
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def statements(sql: str) -> list[str]:
    """Split a migration into statements, without a naive split on ";".

    `sqlite3.complete_statement` is the parser SQLite ships for exactly this: it
    knows a semicolon inside a string literal or a trigger body does not end a
    statement. Splitting by hand would work on today's migrations and break on
    the first one containing either.
    """
    found: list[str] = []
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement:
                found.append(statement)
            buffer = ""
    if buffer.strip():
        found.append(buffer.strip())
    return found


def run_migrations(db: sqlite3.Connection) -> list[str]:
    """Bring the schema up to date. Returns what this call applied.

    Idempotent: running twice applies nothing the second time.

    Each migration and the record of it having run go in together, so a failure
    part-way can never leave a migration *marked* as applied that is not — which
    is the worst case, because every later boot then skips it and the schema
    stays broken with nothing saying why.

    Statements are executed one at a time rather than through `executescript`,
    which **issues a COMMIT before it runs**. That silently ends the transaction
    opened above it: the migration would apply outside any transaction, a
    failure half-way would leave the schema partly changed, and the `rollback`
    in the handler would itself raise "no transaction is active" — losing the
    name of the migration that actually failed.
    """
    already = _applied(db)
    applied: list[str] = []

    for migration in migration_files():
        if migration.name in already:
            continue
        sql = migration.read_text(encoding="utf-8")
        try:
            db.execute("begin")
            for statement in statements(sql):
                db.execute(statement)
            db.execute("insert into schema_migrations (name) values (?)", (migration.name,))
            db.execute("commit")
        except sqlite3.Error as exc:
            if db.in_transaction:
                db.execute("rollback")
            raise MigrationError(f"{migration.name} failed: {exc}") from exc
        applied.append(migration.name)

    return applied


class Store:
    """The case store: **one connection per thread**, never one shared between.

    This class exists because of two measured bugs, not a theory. FastAPI runs
    sync handlers on a threadpool, so the obvious design — open one connection at
    boot and let every handler use it — fails twice over:

    **Writes trample each other.** Four threads each opening a transaction on one
    connection lost 72 of 100 rows and raised `cannot start a transaction within
    a transaction`. A transaction is state on the *connection*, not on the
    statement, so two threads interleaving begin/commit corrupt each other's
    units of work. SQLite's own locking prevents file corruption and does nothing
    about this.

    **Reads go stale.** Adding a lock around writes fixed the first bug and
    revealed the second: a handler that writes a row and reads it back could get
    nothing, because once another thread opened a transaction on that same
    connection, *every* read on it ran inside that thread's older snapshot. The
    symptom was `no case 'case_844e1d0dedf2'` for a case that had just been
    committed — a caller told their case was open when it was not.

    A connection per thread fixes both by construction: transactions are private
    to the thread that opened them, and WAL lets readers run through a write
    without blocking. SQLite serialises the writers itself, and `busy_timeout`
    makes the loser wait rather than raise.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._local = threading.local()
        # Every connection handed out, so shutdown can close them all. Guarded
        # because threads append to it concurrently.
        self._opened: list[sqlite3.Connection] = []
        self._registry = threading.Lock()
        self._closed = False

    @property
    def path(self) -> Path:
        return self._path

    @property
    def connection(self) -> sqlite3.Connection:
        """This thread's connection, opened on first use."""
        existing: sqlite3.Connection | None = getattr(self._local, "connection", None)
        if existing is not None:
            return existing

        if self._closed:
            raise StoreError("the case store is closed")

        connection = get_db(self._path)
        self._local.connection = connection
        with self._registry:
            self._opened.append(connection)
        return connection

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        """Read, on this thread's own connection."""
        return self.connection.execute(sql, params)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """A unit of work, committed or rolled back whole.

        `begin immediate` rather than `begin`: it takes SQLite's write lock at
        the start instead of on the first write, so contention waits out the
        busy timeout at a point where nothing has happened yet. A deferred
        transaction that fails to upgrade half-way through has already done part
        of its work.
        """
        connection = self.connection
        connection.execute("begin immediate")
        try:
            yield connection
            connection.execute("commit")
        except BaseException:
            # BaseException, not Exception: a cancelled request must not leave a
            # transaction open holding SQLite's write lock against every other
            # thread.
            if connection.in_transaction:
                connection.execute("rollback")
            raise

    def close(self) -> None:
        """Close every connection this store handed out.

        Without this the `-wal` and `-shm` files outlive the process, and the
        next reader opens a database that needs recovery rather than one that
        was closed cleanly.
        """
        with self._registry:
            self._closed = True
            for connection in self._opened:
                # Closing an already-closed connection is not an error worth
                # propagating out of shutdown.
                with contextlib.suppress(sqlite3.Error):
                    connection.close()
            self._opened.clear()
        self._local = threading.local()


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    row = db.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?", (name,)
    ).fetchone()
    return row is not None
