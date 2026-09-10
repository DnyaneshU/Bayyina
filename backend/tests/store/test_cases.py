"""Cases, and the states no agent may reach.

**G4 is asserted here, not assumed.** The claim is that nothing on the agent path
can move a case to a decided state, and the way that claim fails in practice is
someone adding a convenient `status=` parameter eighteen months from now.
"""

import inspect
import sqlite3

import pytest

from bayyina.store.cases import (
    INITIAL_STATUS,
    TERMINAL_STATUSES,
    Cases,
    NotAnOfficerDecisionError,
    UnknownCaseError,
)


def test_a_new_case_is_not_decided(db, record):
    case = Cases(db).create(record, call_id="call-1")

    assert case.status == INITIAL_STATUS
    assert case.status not in TERMINAL_STATUSES


def test_create_has_no_parameter_that_could_produce_a_decision(db):
    """The signature is the guardrail.

    `status` is absent rather than defaulted, so there is no argument a caller
    in a hurry can pass. A default would be a door with a sign on it; this is
    no door.
    """
    parameters = set(inspect.signature(Cases.create).parameters)
    assert "status" not in parameters
    assert parameters == {"self", "record", "call_id"}


def test_the_schema_refuses_a_status_nobody_defined(db, record):
    """Belt and braces: a hand-written UPDATE from a console cannot invent one."""
    case = Cases(db).create(record, call_id="call-1")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "update cases set status = 'definitely_approved' where case_id = ?",
            (case.case_id,),
        )


def test_a_decision_requires_a_person(db, record):
    case = Cases(db).create(record, call_id="call-1")

    with pytest.raises(NotAnOfficerDecisionError, match="name the person"):
        Cases(db).record_decision(case.case_id, "approved", officer="")

    with pytest.raises(NotAnOfficerDecisionError, match="name the person"):
        Cases(db).record_decision(case.case_id, "approved", officer="   ")


def test_only_the_three_decided_states_are_decisions(db, record):
    """`record_decision` is not a general-purpose status setter."""
    case = Cases(db).create(record, call_id="call-1")

    with pytest.raises(NotAnOfficerDecisionError, match="not a decision"):
        Cases(db).record_decision(case.case_id, "awaiting_review", officer="officer-1")


def test_an_officer_can_decide_and_the_case_names_them(db, record):
    cases = Cases(db)
    case = cases.create(record, call_id="call-1")

    decided = cases.record_decision(case.case_id, "approved", officer="officer-1")

    assert decided.status == "approved"
    assert decided.decided_by == "officer-1"
    assert decided.decided_at is not None


def test_claiming_a_case_is_not_deciding_it(db, record):
    """A person picking a case up has not yet reached a conclusion."""
    cases = Cases(db)
    case = cases.create(record, call_id="call-1")

    claimed = cases.claim(case.case_id, officer="officer-1")

    assert claimed.status == "in_review"
    assert claimed.status not in TERMINAL_STATUSES
    assert claimed.decided_by is None


def test_every_case_carries_the_call_that_opened_it(db, record):
    case = Cases(db).create(record, call_id="call-42")

    assert case.call_id == "call-42"
    assert [found.case_id for found in Cases(db).for_call("call-42")] == [case.case_id]


def test_a_case_records_the_evaluation_it_came_from(db, record):
    case = Cases(db).create(record, call_id="call-1")

    assert case.eval_id == record.eval_id
    assert case.rule_id == record.rule_id
    assert case.outcome_state == str(getattr(record.state, "value", record.state))


def test_opening_a_case_is_written_to_the_audit_trail(db, record):
    case = Cases(db).create(record, call_id="call-1")

    events = [
        row["event"] for row in db.execute("select * from audit where case_id = ?", (case.case_id,))
    ]
    assert "case_opened" in events


def test_a_decision_is_written_to_the_audit_trail(db, record):
    cases = Cases(db)
    case = cases.create(record, call_id="call-1")
    cases.record_decision(case.case_id, "rejected", officer="officer-7")

    rows = list(db.execute("select * from audit where case_id = ?", (case.case_id,)))
    decision = [row for row in rows if row["event"] == "status_rejected"]
    assert decision, "a decision left no audit entry"
    assert decision[0]["detail"] == "officer-7"


def test_an_unknown_case_raises_rather_than_updating_nothing(db):
    """A silent no-op would report success for a case that does not exist."""
    with pytest.raises(UnknownCaseError):
        Cases(db).record_decision("case_nope", "approved", officer="officer-1")

    with pytest.raises(UnknownCaseError):
        Cases(db).get("case_nope")


def test_terminal_statuses_are_exactly_the_three_the_plan_names(db):
    assert frozenset({"approved", "rejected", "amended"}) == TERMINAL_STATUSES
