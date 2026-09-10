"""Consent, and the one property that matters: opt-out cannot be undone.

**Guardrail G8.** A person who says "stop contacting me" has said it once and for
good. The obvious implementation is a `granted` boolean, and the obvious bug is
that anything holding a connection can set it back to true — a retry, a replayed
webhook, a well-meaning "re-confirm consent" step added six months later.

So there is no boolean. `consent` is an append-only log of events and `opt_out`
is **absorbing**: once one exists for a call, `has()` answers false regardless of
what is written afterwards. Irreversibility is a property of the shape of the
data, not of the discipline of the code that touches it.

`record(granted=True)` after an opt-out is not an error. It is logged and it
changes nothing, because the caller of that method is a retrying voice agent that
should not have to know, and raising would turn a harmless replay into a failed
call.
"""

from __future__ import annotations

import sqlite3

from .db import Store

#: Written when a person withdraws consent for good. Nothing supersedes it.
OPT_OUT = "opt_out"


class Consent:
    """The consent log for one database."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def record(self, call_id: str, *, granted: bool, note: str | None = None) -> None:
        """Log a grant or a withdrawal.

        Has no effect on a call that has already opted out — the event is still
        written, because the log records what happened rather than what counted.
        """
        event = "granted" if granted else "withdrawn"
        with self._store.transaction() as db:
            db.execute(
                "insert into consent (call_id, event, note) values (?, ?, ?)",
                (call_id, event, note),
            )

    def opt_out(self, call_id: str, *, note: str | None = None) -> None:
        """Withdraw consent permanently, and say so in the audit trail.

        Both writes happen in one transaction. An opt-out the audit trail did not
        record is the one thing worse than an opt-out that did not take: it
        leaves nothing to point at when someone asks why the texts stopped, or
        why they did not.
        """
        with self._store.transaction() as db:
            db.execute(
                "insert into consent (call_id, event, note) values (?, ?, ?)",
                (call_id, OPT_OUT, note),
            )
            db.execute(
                "insert into audit (call_id, event, detail) values (?, ?, ?)",
                (call_id, OPT_OUT, note or "consent withdrawn permanently"),
            )
            # Anything scheduled for this person stops. An armed deadline is a
            # future text message, and honouring an opt-out tomorrow is not
            # honouring it.
            db.execute(
                """
                update deadlines
                   set cancelled_at = datetime('now')
                 where call_id = ?
                   and cancelled_at is null
                   and fired_at is null
                """,
                (call_id,),
            )

    def has(self, call_id: str) -> bool:
        """Whether we may contact this person.

        False the moment an opt-out exists, whatever was written after it.
        """
        opted_out = self._store.execute(
            "select 1 from consent where call_id = ? and event = ? limit 1",
            (call_id, OPT_OUT),
        ).fetchone()
        if opted_out is not None:
            return False

        latest = self._store.execute(
            """
            select event from consent
             where call_id = ?
             order by id desc
             limit 1
            """,
            (call_id,),
        ).fetchone()
        return latest is not None and latest["event"] == "granted"

    def opted_out(self, call_id: str) -> bool:
        """The absorbing state, asked directly."""
        return (
            self._store.execute(
                "select 1 from consent where call_id = ? and event = ? limit 1",
                (call_id, OPT_OUT),
            ).fetchone()
            is not None
        )

    def history(self, call_id: str) -> list[sqlite3.Row]:
        """Every event for one call, oldest first."""
        return list(
            self._store.execute("select * from consent where call_id = ? order by id", (call_id,))
        )
