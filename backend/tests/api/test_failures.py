"""What breaks, what the caller hears, and what a retry must not do twice.

Two subjects: the failure taxonomy is complete and honest, and a replayed
request replays its answer rather than repeating its action.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bayyina.api.app import create_app
from bayyina.api.errors import (
    BEHAVIOUR,
    Failure,
    MissingBehaviourError,
    as_markdown,
    behaviour,
)
from bayyina.settings import Settings

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "agent" / "scripts"

BODY = {
    "rule_id": "rent_increase.dubai.decree_43_2013",
    "inputs": {
        "current_annual_rent": "80000",
        "proposed_annual_rent": "96000",
        "market_average_rent": "87000",
    },
    "input_sources": {
        "current_annual_rent": "caller_stated",
        "proposed_annual_rent": "caller_stated",
        "market_average_rent": "user_supplied",
    },
    "market": {"snapshot_id": "user_supplied"},
    "caller_ref": "BYN-4821",
    "language": "en",
}


@pytest.fixture
def client(tmp_path) -> TestClient:
    """A fresh store per test: idempotency is about what a second call sees."""
    return TestClient(
        create_app(
            audit_path=tmp_path / "audit.jsonl",
            market_db=tmp_path / "absent.duckdb",
            case_db=tmp_path / "cases.db",
            settings=Settings(public_rate_limit_per_minute=10_000),
        )
    )


# --- The taxonomy -------------------------------------------------------------


def test_every_failure_has_a_decided_behaviour():
    """A failure with nothing decided is dead air on a live call."""
    missing = [failure.value for failure in Failure if failure not in BEHAVIOUR]
    assert not missing, f"these failures have no decided behaviour: {missing}"


def test_an_unknown_failure_raises_rather_than_improvising():
    with pytest.raises(MissingBehaviourError, match="dead air"):
        behaviour("something_nobody_planned_for")  # type: ignore[arg-type]


def test_every_failure_that_reaches_a_caller_has_something_to_say():
    """Silence is the worst failure mode a voice product has.

    The caller cannot tell whether the line dropped, whether they were
    understood, or whether anyone is coming back.
    """
    for failure, row in BEHAVIOUR.items():
        if row.status is None:
            continue  # the service never started; there is no call to speak on
        assert row.spoken.strip(), f"{failure.value} reaches a caller with nothing to say"
        assert row.then.strip(), f"{failure.value} has no next step"


def test_thin_data_is_an_answer_and_not_an_error():
    """G5. Returning it as a 4xx would teach every client to treat our honesty
    as a fault."""
    thin = behaviour(Failure.COMPARABLE_NOT_FOUND)

    assert thin.status == 200
    assert not thin.escalates
    assert "sorry" not in thin.spoken.lower()
    assert "error" not in thin.spoken.lower()


def test_an_unsigned_corpus_answers_no_calls_at_all():
    """A number that rings and then answers from an unverified corpus is worse
    than a number that does not ring."""
    unsigned = behaviour(Failure.CORPUS_UNSIGNED)

    assert unsigned.status is None
    assert unsigned.spoken == ""


def test_no_spoken_line_offers_advice():
    """The banned vocabulary applies to what the agent says out loud too."""
    banned = ("advice", "advise", "you should", "recommend", "your rights", "guarantee")
    for failure, row in BEHAVIOUR.items():
        lowered = row.spoken.lower()
        for word in banned:
            assert word not in lowered, f"{failure.value} says {word!r}"


def test_the_timeout_line_goes_out_before_the_retry():
    """Otherwise the caller hears exactly the silence the line exists to fill."""
    assert "before" in behaviour(Failure.TIMEOUT).then


def test_the_untranslated_language_failure_refuses_an_english_substitute():
    row = behaviour(Failure.UNSUPPORTED_LANGUAGE)
    assert "Do not send an English document" in row.then


# --- The script set -----------------------------------------------------------


def test_the_agent_scripts_match_the_taxonomy():
    """Generated, never authored.

    A line edited in a script that disagrees with the service is a caller told
    one thing while the tool does another, and nothing would catch it — a
    markdown file runs no tests.
    """
    result = subprocess.run(
        [sys.executable, "scripts/render_failures.py", "--check"],
        cwd=ROOT / "backend",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"the agent failure scripts are stale:\n{result.stdout}{result.stderr}"
    )


def test_the_generated_script_names_every_failure():
    rendered = as_markdown()
    for failure in Failure:
        assert f"`{failure.value}`" in rendered


def test_the_script_says_it_is_generated():
    """Or the next person edits it by hand and their change vanishes."""
    assert "GENERATED" in (SCRIPTS / "en" / "failures.md").read_text(encoding="utf-8")


# --- Idempotency --------------------------------------------------------------


def test_a_replayed_key_returns_the_first_document(client: TestClient):
    """**A voice agent retries.** The caller must experience one action because
    there was one action."""
    headers = {"Idempotency-Key": "call-1-pack-1"}

    first = client.post("/evidence-pack", json=BODY, headers=headers)
    second = client.post("/evidence-pack", json=BODY, headers=headers)

    assert first.status_code == second.status_code == 200
    assert first.text == second.text
    assert first.headers["idempotent-replay"] == "false"
    assert second.headers["idempotent-replay"] == "true"


def test_a_replay_returns_the_stored_bytes_not_a_fresh_render(client: TestClient):
    """Not a new document that happens to match.

    A pack quoted in a hearing must be the pack we produced, and a re-render
    after a rule is re-signed would differ under the same reference.
    """
    headers = {"Idempotency-Key": "call-1-pack-1"}
    first = client.post("/evidence-pack", json=BODY, headers=headers).text

    stored = client.app.state.store.execute(
        "select response from idempotency where key = ?", ("call-1-pack-1",)
    ).fetchone()["response"]

    assert stored == first
    assert client.post("/evidence-pack", json=BODY, headers=headers).text == stored


def test_the_same_key_for_a_different_request_is_refused(client: TestClient):
    """The half that is easy to leave out, and the one that matters.

    Without it a client that reuses a key by mistake receives somebody else's
    document.
    """
    headers = {"Idempotency-Key": "reused"}
    client.post("/evidence-pack", json=BODY, headers=headers)

    other = {**BODY, "inputs": {**BODY["inputs"], "current_annual_rent": "50000"}}
    response = client.post("/evidence-pack", json=other, headers=headers)

    assert response.status_code == 409
    assert "different request" in response.json()["detail"]


def test_a_replay_does_not_evaluate_again(client: TestClient):
    """Every evaluation is written to the audit log (G9).

    If a replay re-evaluated, one caller's single request would appear in the
    log twice and the count of what we answered would be wrong.
    """
    headers = {"Idempotency-Key": "call-1-pack-1"}
    audit = client.app.state.audit.path

    client.post("/evidence-pack", json=BODY, headers=headers)
    after_first = audit.read_text(encoding="utf-8").count("\n")

    client.post("/evidence-pack", json=BODY, headers=headers)
    after_replay = audit.read_text(encoding="utf-8").count("\n")

    assert after_replay == after_first


def test_without_a_key_each_request_is_its_own(client: TestClient):
    """Idempotency is opt-in. A caller that sends no key gets no deduplication,
    which is the correct behaviour for a browser hitting Download twice."""
    audit = client.app.state.audit.path

    client.post("/evidence-pack", json=BODY)
    first = audit.read_text(encoding="utf-8").count("\n")
    client.post("/evidence-pack", json=BODY)

    assert audit.read_text(encoding="utf-8").count("\n") == first + 1


def test_keys_do_not_collide_across_callers(client: TestClient):
    headers_one = {"Idempotency-Key": "pack-a"}
    headers_two = {"Idempotency-Key": "pack-b"}

    first = client.post("/evidence-pack", json=BODY, headers=headers_one).text
    other = {**BODY, "caller_ref": "BYN-9999"}
    second = client.post("/evidence-pack", json=other, headers=headers_two).text

    assert "BYN-4821" in first
    assert "BYN-9999" in second


def test_a_failed_request_is_not_remembered_as_a_success(client: TestClient):
    """A 422 must not poison the key.

    Otherwise a caller who asked in the wrong language once can never get a pack
    under that key, even after the client corrects itself.
    """
    headers = {"Idempotency-Key": "retry-me"}

    failed = client.post("/evidence-pack", json={**BODY, "language": "ml"}, headers=headers)
    assert failed.status_code == 422

    fixed = client.post("/evidence-pack", json=BODY, headers=headers)
    assert fixed.status_code == 200


# --- Timeouts on outbound calls -----------------------------------------------


def test_the_outbound_client_carries_the_configured_budget():
    """httpx defaults to five seconds. Three seconds of silence on a phone call
    is already long, and five is a caller who has hung up."""
    from bayyina.outbound import timeout

    budget = timeout(Settings(tool_timeout_seconds=3))

    assert budget.connect == 3
    assert budget.read == 3
    assert budget.write == 3


def test_a_caller_cannot_override_the_budget():
    """A per-call override is how one endpoint ends up with a thirty-second
    budget nobody remembers agreeing to."""
    from bayyina.outbound import client

    with client(Settings(tool_timeout_seconds=3), timeout=300) as made:
        assert made.timeout.read == 3


def test_nothing_else_in_the_package_builds_an_http_client():
    """The guard that keeps the budget from being optional.

    A timeout added after the first outbound call is written is a timeout added
    after the first outbound call has shipped without one. This fails the moment
    somebody reaches for httpx directly.
    """
    package = ROOT / "backend" / "src" / "bayyina"
    offenders: list[str] = []

    for path in package.rglob("*.py"):
        if path.name == "outbound.py":
            continue
        text = path.read_text(encoding="utf-8")
        for marker in ("httpx.Client(", "httpx.AsyncClient("):
            if marker in text:
                offenders.append(f"{path.relative_to(package)} uses {marker}")

    assert not offenders, (
        "these bypass the tool timeout budget - use bayyina.outbound.client "
        "instead:\n  " + "\n  ".join(offenders)
    )


# --- The taxonomy is the behaviour, not a document beside it ------------------


def test_the_declared_status_is_the_status_the_api_returns(client: TestClient):
    """The agent scripts promise these codes. The service must keep the promise.

    A taxonomy that lives only in markdown drifts the first time someone changes
    a status code, and the agent then treats a 503 it was told to expect as an
    unhandled failure — mid-call.
    """
    # An untranslated language.
    response = client.post("/evidence-pack", json={**BODY, "language": "ml"})
    assert response.status_code == behaviour(Failure.UNSUPPORTED_LANGUAGE).status

    # A derived figure with no comparables database behind it.
    derived = {
        "rule_id": BODY["rule_id"],
        "inputs": {"current_annual_rent": "80000", "proposed_annual_rent": "96000"},
        "input_sources": {
            "current_annual_rent": "caller_stated",
            "proposed_annual_rent": "caller_stated",
        },
        "dwelling": {"area": "Al Barsha First", "kind": "flat", "bedrooms": 2},
    }
    assert (
        client.post("/evaluate", json=derived).status_code
        == behaviour(Failure.MARKET_DATA_ABSENT).status
    )


def test_the_taxonomy_is_imported_by_the_code_that_answers(tmp_path):
    """The guard on the guard.

    Wiring can be undone by anyone hardcoding a number back in. This asserts the
    routes actually read the taxonomy rather than happening to agree with it
    today.
    """
    api = ROOT / "backend" / "src" / "bayyina" / "api"
    wired = [
        path.name
        for path in api.glob("*.py")
        if "behaviour(Failure." in path.read_text(encoding="utf-8")
    ]
    for required in ("routes_evaluate.py", "routes_pack.py", "rate_limit.py", "app.py"):
        assert required in wired, (
            f"{required} no longer reads the failure taxonomy, so its status codes "
            f"and the agent scripts can disagree"
        )


def test_rate_limiting_answers_the_code_the_taxonomy_names(tmp_path):
    """429 is in the agent scripts as 'back off and retry once'."""
    throttled = TestClient(
        create_app(
            audit_path=tmp_path / "audit.jsonl",
            market_db=tmp_path / "absent.duckdb",
            case_db=tmp_path / "cases.db",
            settings=Settings(public_rate_limit_per_minute=1),
        )
    )
    throttled.post("/evidence-pack", json=BODY)
    again = throttled.post("/evidence-pack", json=BODY)

    assert again.status_code == behaviour(Failure.RATE_LIMITED).status
