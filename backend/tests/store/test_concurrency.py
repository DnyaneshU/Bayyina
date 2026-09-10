"""Concurrent writers, which is the ordinary case for a phone service.

**This file exists because of a measured failure, not a theory.** Four threads
writing through one shared connection, each opening its own transaction, lost
**72 of 100 rows** and raised `cannot start a transaction within a transaction`.
`sqlite3.threadsafety` is 3, so nothing was corrupted — but a transaction is
state on the *connection*, and two threads interleaving begin/commit trample one
another.

The symptom in production is a case that silently fails to open while the caller
is told it did.
"""

import threading

from bayyina.store.cases import Cases
from bayyina.store.consent import Consent

WRITERS = 4
PER_WRITER = 25


def _run(target) -> list[str]:
    """Run `target(n)` on several threads and collect what went wrong."""
    failures: list[str] = []

    def wrapped(n: int) -> None:
        try:
            target(n)
        except Exception as exc:  # noqa: BLE001 - the point is to report anything
            failures.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=wrapped, args=(n,)) for n in range(WRITERS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return failures


def test_concurrent_case_creation_loses_nothing(store, record):
    """Every write lands, and none of them raises.

    Before `Store` took a lock this failed both ways at once: exceptions from
    the interleaved `begin`, and rows missing from a `commit` that belonged to
    another thread's transaction.
    """
    cases = Cases(store)

    def write(n: int) -> None:
        for _ in range(PER_WRITER):
            cases.create(record, call_id=f"call-{n}")

    failures = _run(write)

    assert not failures, "concurrent writers raised:\n  " + "\n  ".join(failures)
    written = store.execute("select count(*) as c from cases").fetchone()["c"]
    assert written == WRITERS * PER_WRITER


def test_concurrent_consent_writes_all_land(store):
    consent = Consent(store)

    def write(n: int) -> None:
        for _ in range(PER_WRITER):
            consent.record(f"call-{n}", granted=True)

    failures = _run(write)

    assert not failures, "concurrent consent writes raised: " + "; ".join(failures)
    rows = store.execute("select count(*) as c from consent").fetchone()["c"]
    assert rows == WRITERS * PER_WRITER


def test_an_opt_out_under_load_still_wins(store, record):
    """The guardrail must hold when the system is busy, or it does not hold.

    An opt-out racing a burst of re-grants is exactly the shape of a retry storm,
    and it is the moment G8 is most likely to be quietly violated.
    """
    consent = Consent(store)
    consent.record("call-1", granted=True)

    def write(n: int) -> None:
        if n == 0:
            consent.opt_out("call-1")
        else:
            for _ in range(PER_WRITER):
                consent.record("call-1", granted=True)

    _run(write)

    assert consent.has("call-1") is False
    assert consent.opted_out("call-1") is True


def test_a_failing_transaction_leaves_the_connection_usable(store, record):
    """A rollback must not strand the next writer.

    An open transaction on a shared connection blocks every other thread, so a
    handler that raises mid-write has to leave the connection clean.
    """
    try:
        with store.transaction() as db:
            db.execute(
                "insert into cases (case_id, call_id, status, rule_id, eval_id, "
                "outcome_state) values ('c1', 'call-1', 'nonsense', 'r', 'e', 'CLEAR')"
            )
    except Exception:  # noqa: BLE001 - the check constraint is expected to fire
        pass

    assert not store.connection.in_transaction, "a failed write left a transaction open"
    # And the store still works.
    assert Cases(store).create(record, call_id="call-2").case_id
