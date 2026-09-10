-- The case store.
--
-- Every table carries `call_id`. One identifier threads the whole journey: the
-- call that asked, the case it opened, the pack it produced, the deadline it
-- armed, the consent it rests on. Without that, answering "what happened to this
-- person?" means joining on timestamps and hoping.
--
-- Times are ISO-8601 UTC text. SQLite has no date type, and a unix integer is
-- unreadable in the one place this data gets looked at — a console, during an
-- incident.

-- --------------------------------------------------------------------------
-- Consent. Append-only, and opt-out is absorbing.
-- --------------------------------------------------------------------------
--
-- G8. There is no `granted` column to flip back, because a column that can be
-- set to 1 can be set to 1 again by anything holding a connection. Consent is a
-- log of events, and `Consent.has()` answers false whenever an `opt_out` exists
-- for that call. Irreversible by the shape of the data rather than by the care
-- of the code that touches it.
create table if not exists consent (
    id         integer primary key autoincrement,
    call_id    text    not null,
    event      text    not null check (event in ('granted', 'withdrawn', 'opt_out')),
    recorded_at text   not null default (datetime('now')),
    note       text
);

create index if not exists consent_by_call on consent (call_id);

-- --------------------------------------------------------------------------
-- Cases.
-- --------------------------------------------------------------------------
--
-- G4: an agent can never move a case to a decided state. `status` is checked
-- against the full set here so a bad value cannot be written at all, and the
-- terminal three are set only through the officer interface — `Cases.create()`
-- has no parameter that can produce one.
create table if not exists cases (
    case_id       text primary key,
    call_id       text not null,
    status        text not null check (
                      status in ('awaiting_review', 'in_review',
                                 'approved', 'rejected', 'amended')
                  ),
    rule_id       text not null,
    eval_id       text not null,
    outcome_state text not null,
    created_at    text not null default (datetime('now')),
    updated_at    text not null default (datetime('now')),

    -- Who decided, and when. Null until a person does. Never written by the
    -- agent path: the column exists so that a decided case can always name the
    -- human who decided it.
    decided_by    text,
    decided_at    text
);

create index if not exists cases_by_call on cases (call_id);
create index if not exists cases_by_status on cases (status);

-- --------------------------------------------------------------------------
-- Evidence packs.
-- --------------------------------------------------------------------------
--
-- The rendered document is stored, not regenerated on demand. A pack a person
-- was sent is a record of what they were told; re-rendering it after a rule is
-- re-signed would produce a different document under the same reference.
create table if not exists evidence_packs (
    pack_id    text primary key,
    call_id    text not null,
    case_id    text references cases (case_id),
    language   text not null,
    body       text not null,
    signature  text not null,
    created_at text not null default (datetime('now'))
);

create index if not exists packs_by_call on evidence_packs (call_id);

-- --------------------------------------------------------------------------
-- Deadlines.
-- --------------------------------------------------------------------------
--
-- G8 again: armed only on an explicit opt-in, and cancelled by an opt-out that
-- cannot be undone. `due_on` is a date, not a timestamp — a notice period ends
-- on a day, and pretending to a precision the law does not have would produce
-- off-by-one reminders around midnight.
create table if not exists deadlines (
    deadline_id text primary key,
    call_id     text not null,
    case_id     text not null references cases (case_id),
    rule_id     text not null,
    due_on      text not null,
    armed_at    text not null default (datetime('now')),
    cancelled_at text,
    fired_at    text
);

create index if not exists deadlines_by_due on deadlines (due_on)
    where cancelled_at is null and fired_at is null;

-- --------------------------------------------------------------------------
-- Audit.
-- --------------------------------------------------------------------------
--
-- Distinct from the hash-chained evaluation log in `bayyina/audit.py`, which
-- attests to what was computed. This one records what was *done* — consent
-- taken, a pack sent, a case decided — so the two answer different questions
-- and neither is asked to do the other's job.
create table if not exists audit (
    id         integer primary key autoincrement,
    call_id    text not null,
    case_id    text,
    event      text not null,
    detail     text,
    at         text not null default (datetime('now'))
);

create index if not exists audit_by_call on audit (call_id);

-- --------------------------------------------------------------------------
-- Idempotency.
-- --------------------------------------------------------------------------
--
-- A voice agent retries. Sending one person two texts about their tenancy, or
-- arming the same deadline twice, is the failure this table exists to prevent:
-- the stored response is replayed rather than the action repeated.
-- `request_fingerprint` is the half that is easy to leave out. Without it a
-- client that reuses a key by mistake — a constant, a badly seeded generator, a
-- copied line — is handed *someone else's* stored response. With it, that is a
-- 409 instead of a data leak.
create table if not exists idempotency (
    key                 text primary key,
    call_id             text not null,
    operation           text not null,
    request_fingerprint text not null,
    response            text not null,
    created_at          text not null default (datetime('now'))
);
