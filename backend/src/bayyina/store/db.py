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

import sqlite3
from pathlib import Path

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
        # The API runs handlers on a threadpool, so a connection made on one
        # thread is used on another. Serialising access is the caller's job and
        # SQLite's own locking does it here.
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


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    row = db.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?", (name,)
    ).fetchone()
    return row is not None
