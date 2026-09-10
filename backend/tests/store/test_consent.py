"""Consent, and the one property that must hold under every sequence.

**Opt-out is absorbing.** These tests exist because the obvious implementation —
a `granted` boolean — passes a naive test suite and fails the only case that
matters: someone re-grants after an opt-out, by retry, by replay, or by a
well-meaning re-confirmation step added later.
"""

from datetime import date, timedelta

from bayyina.store.cases import Cases
from bayyina.store.consent import Consent
from bayyina.store.deadlines import Deadlines


def audit_entries(db, call_id):
    return list(db.execute("select * from audit where call_id = ?", (call_id,)))


def test_consent_starts_absent(db):
    """Silence is not agreement."""
    assert Consent(db).has("call-1") is False


def test_it_is_granted_when_granted(db):
    Consent(db).record("call-1", granted=True)
    assert Consent(db).has("call-1") is True


def test_it_can_be_withdrawn_and_granted_again(db):
    """An ordinary withdrawal is reversible. Only opt-out is not."""
    consent = Consent(db)
    consent.record("call-1", granted=True)
    consent.record("call-1", granted=False)
    assert consent.has("call-1") is False

    consent.record("call-1", granted=True)
    assert consent.has("call-1") is True


def test_opt_out_is_irreversible(db):
    """The whole point. G8."""
    consent = Consent(db)
    consent.record("call-1", granted=True)
    consent.opt_out("call-1")

    consent.record("call-1", granted=True)  # a retry, a replay, a later "re-confirm"

    assert consent.has("call-1") is False


def test_opt_out_survives_any_number_of_regrants(db):
    consent = Consent(db)
    consent.opt_out("call-1")
    for _ in range(5):
        consent.record("call-1", granted=True)
    assert consent.has("call-1") is False


def test_opt_out_is_written_to_the_audit_trail(db):
    """An opt-out nothing recorded leaves nothing to point at afterwards."""
    consent = Consent(db)
    consent.record("call-1", granted=True)
    consent.opt_out("call-1")

    assert any(row["event"] == "opt_out" for row in audit_entries(db, "call-1"))


def test_opt_out_touches_only_the_call_that_asked(db):
    consent = Consent(db)
    consent.record("call-1", granted=True)
    consent.record("call-2", granted=True)

    consent.opt_out("call-1")

    assert consent.has("call-1") is False
    assert consent.has("call-2") is True


def test_the_log_keeps_what_happened_even_when_it_did_not_count(db):
    """The log records events, not conclusions.

    A re-grant after an opt-out changes nothing, and it is still written — so
    the record shows a retry happened rather than hiding it.
    """
    consent = Consent(db)
    consent.opt_out("call-1")
    consent.record("call-1", granted=True)

    events = [row["event"] for row in consent.history("call-1")]
    assert events == ["opt_out", "granted"]
    assert consent.has("call-1") is False


def test_nothing_is_due_for_someone_who_opted_out(db, record):
    """The outcome, however it is reached.

    Honouring an opt-out from tomorrow is not honouring it: an armed deadline is
    a future text message about someone's tenancy, and it is the most visible
    way a service can look like it was not listening.

    Deliberately named for the outcome and not the mechanism. Two independent
    things make this true — `opt_out` cancels armed rows, and `due()` excludes
    opted-out calls in its own query — so removing either one leaves this test
    green. That is defence in depth working, but it means this test alone proves
    neither half. `test_the_cancellation_and_the_withdrawal_are_one_transaction`
    is what pins the write path, and the read path is pinned in
    `test_due_excludes_anyone_who_opted_out`.
    """
    consent = Consent(db)
    consent.record("call-1", granted=True)
    case = Cases(db).create(record, call_id="call-1")
    deadlines = Deadlines(db)
    deadlines.arm(case.case_id, date.today() + timedelta(days=30), record.rule_id)

    assert deadlines.due(date.today() + timedelta(days=60))

    consent.opt_out("call-1")

    assert deadlines.due(date.today() + timedelta(days=60)) == []


def test_the_cancellation_and_the_withdrawal_are_one_transaction(db, record):
    """Either both happened or neither did.

    A withdrawal recorded without the cancellation is an opt-out that still
    sends the text.
    """
    consent = Consent(db)
    consent.record("call-1", granted=True)
    case = Cases(db).create(record, call_id="call-1")
    Deadlines(db).arm(case.case_id, date.today() + timedelta(days=30), record.rule_id)

    consent.opt_out("call-1")

    cancelled = db.execute("select cancelled_at from deadlines where call_id = 'call-1'").fetchone()
    assert cancelled["cancelled_at"] is not None
    assert consent.opted_out("call-1") is True
