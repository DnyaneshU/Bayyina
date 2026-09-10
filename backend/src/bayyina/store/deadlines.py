"""Deadlines: a reminder before a notice period runs out.

**Guardrail G8.** A deadline is a future text message about someone's tenancy, so
it is armed only on an explicit opt-in and it stops the moment consent does. That
second half is the one that gets forgotten: honouring an opt-out from tomorrow is
not honouring it, and a reminder that arrives after someone said stop is the most
visible way a service can look like it was not listening.

`Consent.opt_out()` cancels armed deadlines in the same transaction that records
the withdrawal, and `arm()` refuses to create one without consent. Both halves,
because either alone leaves a window.

`due_on` is a date. A notice period ends on a day, and storing a timestamp would
invent a precision the law does not have — which shows up as reminders landing on
the wrong side of midnight.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from .consent import Consent


class DeadlineError(RuntimeError):
    """A deadline could not be armed."""


class NoConsentError(DeadlineError):
    """Asked to schedule contact with someone who has not agreed to it."""


@dataclass(frozen=True)
class Deadline:
    deadline_id: str
    call_id: str
    case_id: str
    rule_id: str
    due_on: str
    cancelled_at: str | None = None
    fired_at: str | None = None


class Deadlines:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def arm(self, case_id: str, due: date | str, rule_id: str) -> Deadline:
        """Schedule a reminder, if we are allowed to contact this person.

        The `call_id` is read from the case rather than passed in. Two arguments
        that must agree are two arguments that eventually will not, and a
        deadline armed against the wrong call is a text to the wrong person.
        """
        row = self._db.execute("select call_id from cases where case_id = ?", (case_id,)).fetchone()
        if row is None:
            raise DeadlineError(f"no case {case_id!r} to arm a deadline against")
        call_id = row["call_id"]

        if not Consent(self._db).has(call_id):
            raise NoConsentError(
                f"no consent to contact {call_id!r}, so no deadline is armed. "
                f"A reminder is contact, and G8 does not have an exception for "
                f"a helpful one."
            )

        due_on = due.isoformat() if isinstance(due, date) else str(due)
        deadline = Deadline(
            deadline_id=f"dl_{uuid4().hex[:12]}",
            call_id=call_id,
            case_id=case_id,
            rule_id=rule_id,
            due_on=due_on,
        )

        try:
            self._db.execute("begin")
            self._db.execute(
                """
                insert into deadlines (deadline_id, call_id, case_id, rule_id, due_on)
                values (?, ?, ?, ?, ?)
                """,
                (
                    deadline.deadline_id,
                    call_id,
                    case_id,
                    rule_id,
                    due_on,
                ),
            )
            self._db.execute(
                "insert into audit (call_id, case_id, event, detail) values (?, ?, ?, ?)",
                (call_id, case_id, "deadline_armed", due_on),
            )
            self._db.execute("commit")
        except sqlite3.Error:
            self._db.execute("rollback")
            raise

        return deadline

    def due(self, on: date | str) -> list[Deadline]:
        """Everything to send on a given day, opt-outs already excluded.

        The consent join is here rather than in the caller. A query that returns
        rows the caller must remember to filter is a query that will one day be
        used by a caller who does not.
        """
        when = on.isoformat() if isinstance(on, date) else str(on)
        rows = self._db.execute(
            """
            select d.* from deadlines d
             where d.due_on <= ?
               and d.cancelled_at is null
               and d.fired_at is null
               and not exists (
                   select 1 from consent c
                    where c.call_id = d.call_id and c.event = 'opt_out'
               )
             order by d.due_on
            """,
            (when,),
        )
        return [
            Deadline(
                deadline_id=row["deadline_id"],
                call_id=row["call_id"],
                case_id=row["case_id"],
                rule_id=row["rule_id"],
                due_on=row["due_on"],
                cancelled_at=row["cancelled_at"],
                fired_at=row["fired_at"],
            )
            for row in rows
        ]

    def mark_fired(self, deadline_id: str) -> None:
        self._db.execute(
            "update deadlines set fired_at = datetime('now') where deadline_id = ?",
            (deadline_id,),
        )
        self._db.commit()

    def cancel(self, deadline_id: str) -> None:
        self._db.execute(
            "update deadlines set cancelled_at = datetime('now') where deadline_id = ?",
            (deadline_id,),
        )
        self._db.commit()
