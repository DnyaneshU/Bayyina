"""Deadlines: contact scheduled for the future, and the consent it rests on."""

from datetime import date, timedelta

import pytest

from bayyina.store.cases import Cases
from bayyina.store.consent import Consent
from bayyina.store.deadlines import DeadlineError, Deadlines, NoConsentError

SOON = date.today() + timedelta(days=30)
LATER = date.today() + timedelta(days=60)


def _case(store, record, call_id="call-1", *, consent=True):
    if consent:
        Consent(store).record(call_id, granted=True)
    return Cases(store).create(record, call_id=call_id)


def test_a_deadline_needs_consent(store, record):
    """A reminder is contact, and G8 has no exception for a helpful one."""
    case = _case(store, record, consent=False)

    with pytest.raises(NoConsentError, match="no consent"):
        Deadlines(store).arm(case.case_id, SOON, record.rule_id)


def test_it_arms_when_consent_is_given(store, record):
    case = _case(store, record)

    deadline = Deadlines(store).arm(case.case_id, SOON, record.rule_id)

    assert deadline.due_on == SOON.isoformat()
    assert deadline.call_id == "call-1"


def test_the_call_id_comes_from_the_case_not_the_caller(store, record):
    """Two arguments that must agree are two that eventually will not, and a
    deadline armed against the wrong call is a text to the wrong person."""
    case = _case(store, record, call_id="call-99")

    assert Deadlines(store).arm(case.case_id, SOON, record.rule_id).call_id == "call-99"


def test_it_refuses_a_case_that_does_not_exist(store, record):
    with pytest.raises(DeadlineError, match="no case"):
        Deadlines(store).arm("case_nope", SOON, record.rule_id)


def test_due_returns_what_is_ready_and_nothing_later(store, record):
    case = _case(store, record)
    deadlines = Deadlines(store)
    deadlines.arm(case.case_id, LATER, record.rule_id)

    assert deadlines.due(SOON) == []
    assert len(deadlines.due(LATER)) == 1


def test_a_fired_deadline_does_not_come_back(store, record):
    """Otherwise every run sends the same reminder again."""
    case = _case(store, record)
    deadlines = Deadlines(store)
    armed = deadlines.arm(case.case_id, SOON, record.rule_id)

    deadlines.mark_fired(armed.deadline_id)

    assert deadlines.due(LATER) == []


def test_a_cancelled_deadline_does_not_come_back(store, record):
    case = _case(store, record)
    deadlines = Deadlines(store)
    armed = deadlines.arm(case.case_id, SOON, record.rule_id)

    deadlines.cancel(armed.deadline_id)

    assert deadlines.due(LATER) == []


def test_due_excludes_anyone_who_opted_out(store, record):
    """The filter is in the query, not left to the caller.

    A query returning rows the caller must remember to filter is a query that
    will one day be used by a caller who does not.
    """
    case = _case(store, record)
    deadlines = Deadlines(store)
    deadlines.arm(case.case_id, SOON, record.rule_id)

    # Opt out *without* going through Consent.opt_out, so the row is not
    # cancelled: this asserts the read path defends itself rather than relying
    # on the write path having tidied up.
    with store.transaction() as raw:
        raw.execute("insert into consent (call_id, event) values ('call-1', 'opt_out')")

    assert deadlines.due(LATER) == []


def test_arming_is_written_to_the_audit_trail(store, record):
    case = _case(store, record)
    Deadlines(store).arm(case.case_id, SOON, record.rule_id)

    events = [
        row["event"]
        for row in store.execute("select * from audit where case_id = ?", (case.case_id,))
    ]
    assert "deadline_armed" in events


def test_a_due_date_is_a_date_and_not_a_timestamp(store, record):
    """A notice period ends on a day. Inventing a precision the law does not
    have produces reminders on the wrong side of midnight."""
    case = _case(store, record)

    stored = Deadlines(store).arm(case.case_id, SOON, record.rule_id).due_on

    assert stored == SOON.isoformat()
    assert "T" not in stored and ":" not in stored
