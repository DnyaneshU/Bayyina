"""Cases, and the states an agent may never reach.

**Guardrail G4: the agent can never decide anything.** A case it opens is
`awaiting_review` and it stays there until a person moves it. That is enforced
three ways rather than documented once:

* `Cases.create()` takes no status parameter at all, so there is no argument that
  produces a decided case.
* `record_decision()` requires an officer id and accepts only the terminal three,
  so the decided states have exactly one door and it needs a name on it.
* The `status` check constraint in the schema refuses anything else, so a
  hand-written UPDATE from a console cannot invent a fourth state either.

The distinction is not cosmetic. "Approved" from a machine that read a decree is
a determination, and Bayyina does not make determinations — it lays out what the
published rule says and hands that to someone who can.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from uuid import uuid4

#: Where a case starts, and the only status `create()` can produce.
INITIAL_STATUS = "awaiting_review"

#: A person has picked it up. Still not decided.
IN_REVIEW = "in_review"

#: Decided. Reachable only through `record_decision`, which requires an officer.
TERMINAL_STATUSES = frozenset({"approved", "rejected", "amended"})

#: Everything the schema will accept.
STATUSES = frozenset({INITIAL_STATUS, IN_REVIEW}) | TERMINAL_STATUSES


class CaseError(RuntimeError):
    """A case could not be created or moved."""


class UnknownCaseError(CaseError):
    """No case with that id."""


class NotAnOfficerDecisionError(CaseError):
    """Something tried to reach a decided state without a person behind it."""


@dataclass(frozen=True)
class Case:
    case_id: str
    call_id: str
    status: str
    rule_id: str
    eval_id: str
    outcome_state: str
    created_at: str
    decided_by: str | None = None
    decided_at: str | None = None


def _row_to_case(row: sqlite3.Row) -> Case:
    return Case(
        case_id=row["case_id"],
        call_id=row["call_id"],
        status=row["status"],
        rule_id=row["rule_id"],
        eval_id=row["eval_id"],
        outcome_state=row["outcome_state"],
        created_at=row["created_at"],
        decided_by=row["decided_by"],
        decided_at=row["decided_at"],
    )


class Cases:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def create(self, record, call_id: str) -> Case:
        """Open a case from an evaluation record.

        **There is no `status` parameter.** Not defaulted to `awaiting_review` —
        absent, so that no caller, and no future caller in a hurry, can pass one.
        G4 is a property of this signature.

        Takes the record rather than its parts for the same reason `build_pack`
        does: what opens a case is something we computed, never something a
        caller assembled.
        """
        case = Case(
            case_id=f"case_{uuid4().hex[:12]}",
            call_id=call_id,
            status=INITIAL_STATUS,
            rule_id=record.rule_id,
            eval_id=record.eval_id,
            outcome_state=str(getattr(record.state, "value", record.state)),
            created_at="",
        )

        try:
            self._db.execute("begin")
            self._db.execute(
                """
                insert into cases (case_id, call_id, status, rule_id, eval_id,
                                   outcome_state)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    case.case_id,
                    case.call_id,
                    INITIAL_STATUS,
                    case.rule_id,
                    case.eval_id,
                    case.outcome_state,
                ),
            )
            self._db.execute(
                "insert into audit (call_id, case_id, event, detail) values (?, ?, ?, ?)",
                (call_id, case.case_id, "case_opened", case.rule_id),
            )
            self._db.execute("commit")
        except sqlite3.Error:
            self._db.execute("rollback")
            raise

        return self.get(case.case_id)

    def get(self, case_id: str) -> Case:
        row = self._db.execute("select * from cases where case_id = ?", (case_id,)).fetchone()
        if row is None:
            raise UnknownCaseError(f"no case {case_id!r}")
        return _row_to_case(row)

    def for_call(self, call_id: str) -> list[Case]:
        return [
            _row_to_case(row)
            for row in self._db.execute(
                "select * from cases where call_id = ? order by created_at", (call_id,)
            )
        ]

    def claim(self, case_id: str, officer: str) -> Case:
        """A person picks the case up. Still not a decision."""
        self._move(case_id, IN_REVIEW, officer=officer, decided=False)
        return self.get(case_id)

    def record_decision(self, case_id: str, status: str, officer: str) -> Case:
        """The only door to a decided state, and it needs a name on it.

        `officer` is required and must be non-empty. An empty string would let a
        caller satisfy the signature while recording a decision nobody made,
        which is the failure this argument exists to prevent.
        """
        if status not in TERMINAL_STATUSES:
            raise NotAnOfficerDecisionError(
                f"{status!r} is not a decision. One of: {sorted(TERMINAL_STATUSES)}"
            )
        if not officer or not officer.strip():
            raise NotAnOfficerDecisionError(
                "a decided case must name the person who decided it (G4)"
            )
        self._move(case_id, status, officer=officer.strip(), decided=True)
        return self.get(case_id)

    def _move(self, case_id: str, status: str, *, officer: str, decided: bool) -> None:
        self.get(case_id)  # raises UnknownCaseError rather than updating nothing
        try:
            self._db.execute("begin")
            if decided:
                self._db.execute(
                    """
                    update cases
                       set status = ?, updated_at = datetime('now'),
                           decided_by = ?, decided_at = datetime('now')
                     where case_id = ?
                    """,
                    (status, officer, case_id),
                )
            else:
                self._db.execute(
                    "update cases set status = ?, updated_at = datetime('now') where case_id = ?",
                    (status, case_id),
                )
            self._db.execute(
                """
                insert into audit (call_id, case_id, event, detail)
                select call_id, case_id, ?, ? from cases where case_id = ?
                """,
                (f"status_{status}", officer, case_id),
            )
            self._db.execute("commit")
        except sqlite3.Error:
            self._db.execute("rollback")
            raise
