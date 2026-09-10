"""The schema, and the settings a service needs that a script does not."""

import sqlite3

import pytest

from bayyina.store.db import (
    MigrationError,
    get_db,
    migration_files,
    run_migrations,
    table_exists,
)

#: Every table the plan names. Listed here rather than derived from the schema,
#: so a migration that drops one is caught rather than described.
EXPECTED_TABLES = (
    "cases",
    "evidence_packs",
    "deadlines",
    "consent",
    "audit",
    "idempotency",
)


def test_migrations_create_every_table_the_journey_needs(store):
    for table in EXPECTED_TABLES:
        assert table_exists(store, table), f"{table} is missing from the schema"


def test_migrations_are_idempotent(tmp_path):
    """Running twice must not fail or duplicate.

    Every boot runs them. A migration that is not safe to re-run is a service
    that starts once.
    """
    connection = get_db(tmp_path / "t.db")

    first = run_migrations(connection)
    second = run_migrations(connection)

    assert first, "the first run applied nothing"
    assert second == [], "the second run applied a migration again"
    assert table_exists(connection, "cases")


def test_wal_mode_is_enabled(tmp_path):
    """The default journal mode locks the whole database on write.

    One caller whose case is being written would block every reader, which
    during a phone call is dead air.
    """
    connection = get_db(tmp_path / "t.db")
    mode = connection.execute("pragma journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_a_busy_writer_waits_rather_than_raising(tmp_path):
    """Without a busy timeout, contention raises immediately."""
    connection = get_db(tmp_path / "t.db")
    assert connection.execute("pragma busy_timeout").fetchone()[0] >= 1000


def test_foreign_keys_are_enforced(store):
    """Off by default in SQLite, which surprises everyone exactly once."""
    assert store.execute("pragma foreign_keys").fetchone()[0] == 1

    with pytest.raises(sqlite3.IntegrityError):
        store.execute(
            """
            insert into deadlines (deadline_id, call_id, case_id, rule_id, due_on)
            values ('dl_1', 'call-1', 'case-that-does-not-exist', 'r', '2026-12-01')
            """
        )


def test_every_table_carries_the_call_id(store):
    """One identifier threads the whole journey.

    Without it, answering "what happened to this person?" means joining on
    timestamps and hoping.
    """
    for table in EXPECTED_TABLES:
        columns = {row["name"] for row in store.execute(f"pragma table_info({table})")}
        assert "call_id" in columns, f"{table} cannot be traced to a call"


def test_migrations_are_numbered_so_their_order_is_not_the_filesystems(tmp_path):
    for path in migration_files():
        assert path.name[:3].isdigit(), (
            f"{path.name} has no number, so its position depends on the filesystem"
        )


def test_a_failed_migration_is_not_recorded_as_applied(tmp_path, monkeypatch):
    """The property that makes a half-applied schema recoverable.

    A migration recorded as applied but not actually applied is the worst case:
    every later boot skips it, and the schema stays broken with nothing saying
    why.
    """
    connection = get_db(tmp_path / "t.db")
    broken = tmp_path / "002_broken.sql"
    broken.write_text("create table oops (", encoding="utf-8")

    monkeypatch.setattr(
        "bayyina.store.db.migration_files",
        lambda: [*_first_migration(), broken],
    )

    with pytest.raises(MigrationError, match="002_broken"):
        run_migrations(connection)

    recorded = {row["name"] for row in connection.execute("select name from schema_migrations")}
    assert "002_broken.sql" not in recorded


def _first_migration():
    from bayyina.store.db import MIGRATIONS_DIR

    return sorted(MIGRATIONS_DIR.glob("*.sql"))
