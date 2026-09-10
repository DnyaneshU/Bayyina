"""The HTTP surface: /evaluate and /healthz.

The status codes carry meaning here. A caller who sent an unusable value gets a
4xx and can fix it; a corpus that cannot answer is a 5xx and is ours to fix. A
verdict of HUMAN_REVIEW_REQUIRED is **200** — it is an outcome, not an error, and
returning it as a failure would teach every client to treat honesty as a fault.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bayyina.api.app import create_app
from bayyina.settings import Settings

ROOT = Path(__file__).resolve().parents[3]

RENT = "rent_increase.dubai.decree_43_2013"
NOTICE = "notice_validity.dubai.law_26_2007_a14"

BODY = {
    "rule_id": RENT,
    "inputs": {
        "current_annual_rent": "80000",
        "market_average_rent": "87000",
        "proposed_annual_rent": "96000",
    },
    "input_sources": {
        "current_annual_rent": "caller_stated",
        "market_average_rent": "dld_open_rent_contracts_derived",
        "proposed_annual_rent": "caller_stated",
    },
    "market": {"contract_count": 5557, "snapshot_id": "2026-Q3"},
}

NOTICE_BODY = {
    "rule_id": NOTICE,
    "inputs": {"contract_expiry": "2026-12-31", "notice_served": "2026-11-01"},
    "input_sources": {"contract_expiry": "caller_stated", "notice_served": "caller_stated"},
}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """A client for testing evaluation, not throttling.

    The module shares one client, so with the production limit of 30 requests a
    minute this file was permanently one test away from 429s that have nothing to
    do with what it asserts — a trap for whoever adds the next test. Throttling
    has its own file, where the real limit is the subject.
    """
    audit = tmp_path_factory.mktemp("audit") / "audit.jsonl"
    settings = Settings(public_rate_limit_per_minute=10_000)
    # `market_db` is named explicitly at a path that does not exist. Left to the
    # default, these tests would read `data/market.duckdb` if a developer happened
    # to have built one and not read it in CI - so the same suite would assert
    # different things on two machines. The market routes have their own tests.
    return TestClient(
        create_app(
            audit_path=audit,
            market_db=tmp_path_factory.mktemp("market") / "absent.duckdb",
            settings=settings,
        )
    )


def _thin(count: int) -> dict:
    return {**BODY, "market": {"contract_count": count, "snapshot_id": "2026-Q3"}}


# --- The happy path ----------------------------------------------------------


def test_evaluate_returns_a_verdict_with_a_citation(client):
    body = client.post("/evaluate", json=BODY).json()
    assert body["verdict"] == "not_permitted"
    assert body["citation"]["clause"] == "Article 1"
    assert body["review_status"] == "provisional"
    assert body["state"] == "CLEAR"


def test_the_citation_travels_over_the_wire_in_full(client):
    """G1 is worth nothing if the clause is dropped at the boundary."""
    citation = client.post("/evaluate", json=BODY).json()["citation"]
    assert "average rental value of similar units" in citation["verbatim"]
    assert citation["url"].startswith("https://")


def test_money_crosses_the_wire_as_a_string(client):
    """A rent is currency. It must not become a JSON float in transit."""
    body = client.post("/evaluate", json=BODY).json()
    assert body["computed"]["max_lawful_rent"] == "80000.00"
    assert isinstance(body["inputs"]["current_annual_rent"], str)


def test_the_signature_and_version_are_returned(client):
    body = client.post("/evaluate", json=BODY).json()
    assert body["rule_signature"].startswith("sha256:")
    assert body["rule_version"] == 1


def test_the_notice_rule_needs_no_market_block(client):
    response = client.post("/evaluate", json=NOTICE_BODY)
    assert response.status_code == 200
    assert response.json()["computed"]["shortfall_days"] == 30


# --- G5 over HTTP ------------------------------------------------------------


def test_thin_data_is_a_200_not_an_error(client):
    """HUMAN_REVIEW_REQUIRED is an outcome. A 4xx would teach clients otherwise."""
    response = client.post("/evaluate", json=_thin(4))
    assert response.status_code == 200

    body = response.json()
    assert body["state"] == "HUMAN_REVIEW_REQUIRED"
    assert body["verdict"] is None
    assert body["computed"] == {}
    assert body["confidence"] is None


def test_thin_data_still_returns_the_citation_and_the_count(client):
    body = client.post("/evaluate", json=_thin(4)).json()
    assert body["citation"]["clause"] == "Article 1"
    assert body["evidence"]["contract_count"] == 4


def test_reduced_confidence_is_reported(client):
    body = client.post("/evaluate", json=_thin(12)).json()
    assert body["state"] == "CLEAR_WITH_CONDITIONS"
    assert 0 < body["confidence"] < 1


# --- Status codes carry meaning ----------------------------------------------


def test_evaluate_rejects_a_negative_rent(client):
    bad = {**BODY, "inputs": {**BODY["inputs"], "current_annual_rent": "-1"}}
    assert client.post("/evaluate", json=bad).status_code == 422


def test_evaluate_rejects_a_float_amount(client):
    """Binary floating point cannot hold currency. Refused at the boundary."""
    bad = {**BODY, "inputs": {**BODY["inputs"], "current_annual_rent": 80000.5}}
    assert client.post("/evaluate", json=bad).status_code == 422


def test_an_unknown_rule_is_a_404(client):
    response = client.post("/evaluate", json={**BODY, "rule_id": "nope"})
    assert response.status_code == 404
    assert RENT in response.json()["detail"]


def test_a_missing_input_is_a_422_naming_the_field(client):
    inputs = {k: v for k, v in BODY["inputs"].items() if k != "proposed_annual_rent"}
    response = client.post("/evaluate", json={**BODY, "inputs": inputs})
    assert response.status_code == 422
    assert "proposed_annual_rent" in response.json()["detail"]


def test_an_input_with_no_recorded_source_is_a_422(client):
    """G9 is per-field provenance, enforced at the boundary too."""
    sources = {k: v for k, v in BODY["input_sources"].items() if k != "current_annual_rent"}
    response = client.post("/evaluate", json={**BODY, "input_sources": sources})
    assert response.status_code == 422
    assert "current_annual_rent" in response.json()["detail"]


def test_a_market_rule_without_a_market_block_is_a_422(client):
    body = {k: v for k, v in BODY.items() if k != "market"}
    response = client.post("/evaluate", json=body)
    assert response.status_code == 422
    assert "market" in response.json()["detail"].lower()


def test_an_unparseable_date_is_a_422(client):
    bad = {**NOTICE_BODY, "inputs": {**NOTICE_BODY["inputs"], "notice_served": "last Tuesday"}}
    assert client.post("/evaluate", json=bad).status_code == 422


def test_an_unknown_request_field_is_rejected(client):
    """A typo in a tool call must fail loudly, not be silently ignored."""
    assert client.post("/evaluate", json={**BODY, "rule": RENT}).status_code == 422


# --- G9: the evaluation is recorded ------------------------------------------


def test_every_evaluation_is_written_to_the_audit_log(client):
    from bayyina.audit import AuditLog

    log: AuditLog = client.app.state.audit
    before = log.verify_chain()
    eval_id = client.post("/evaluate", json=BODY).json()["eval_id"]
    after = log.entries()

    assert len(after) == before + 1
    assert after[-1].record["eval_id"] == eval_id
    assert log.verify_chain() == before + 1


def test_a_refused_request_writes_nothing(client):
    """Only evaluations are recorded. A rejected call produced no verdict."""
    log = client.app.state.audit
    before = len(log.entries())
    client.post("/evaluate", json={**BODY, "rule_id": "nope"})
    assert len(log.entries()) == before


# --- /healthz ----------------------------------------------------------------


def test_healthz_reports_corpus_state(client):
    body = client.get("/healthz").json()
    assert body["corpus_signed"] is True
    assert body["rule_count"] == 2
    assert body["checks"]["corpus_loaded"] is True
    assert body["checks"]["corpus_signed"] is True


def test_healthz_names_every_rule_and_its_signature(client):
    """A deployment must be checkable against the corpus it claims to run."""
    rules = client.get("/healthz").json()["rules"]
    assert {rule["id"] for rule in rules} == {RENT, NOTICE}
    assert all(rule["signature"].startswith("sha256:") for rule in rules)
    assert all(rule["approval_status"] == "provisional" for rule in rules)


def test_healthz_reports_missing_market_data_rather_than_hiding_it(client):
    """A green health check that lies is worse than none.

    This client has no comparables database, which is a supported state - the
    notice rule and a caller-supplied figure both still work. What is not
    supported is looking healthy while a dataset the product advertises is
    absent, so `status` degrades and the failing check is named.
    """
    body = client.get("/healthz").json()
    assert body["checks"]["market_data_loaded"] is False
    assert body["checks"]["market_data_usable"] is False
    assert body["status"] == "degraded"
    assert body["market_data_age_days"] is None, "no data has no age"


def test_healthz_no_longer_defers_the_market_snapshot(client):
    """It was in `not_yet_checked` from T1.7 until T2.3. It is checked now, so
    it must not still be advertised as unchecked - a deferral list that outlives
    its deferrals stops being worth reading (D-067)."""
    body = client.get("/healthz").json()
    assert "market_snapshot" not in body["not_yet_checked"]
    assert set(body["checks"]) >= {"corpus_loaded", "corpus_signed", "audit_writable"}


# --- Latency -----------------------------------------------------------------


def test_every_response_carries_a_latency_header(client):
    """We publish a latency budget; we measure it from the first deploy."""
    assert "x-response-ms" in client.post("/evaluate", json=BODY).headers
    assert "x-response-ms" in client.get("/healthz").headers


def test_the_latency_header_is_present_on_errors_too(client):
    """A slow failure is the one you most want to see in the numbers."""
    response = client.post("/evaluate", json={**BODY, "rule_id": "nope"})
    assert float(response.headers["x-response-ms"]) >= 0


def test_evaluation_is_well_inside_the_webhook_budget(client):
    """The budget is <150ms p95 for the whole hop. The rule itself is <5ms.

    Asserted at p95 rather than at the maximum, because that is the number we
    published - and because one scheduling outlier on a shared CI runner is not
    a regression.
    """
    client.post("/evaluate", json=BODY)  # warm
    timings = sorted(
        float(client.post("/evaluate", json=BODY).headers["x-response-ms"]) for _ in range(20)
    )
    p95 = timings[18]
    assert p95 < 150, f"p95 evaluation {p95}ms, slowest {timings[-1]}ms"


# --- A broken rule is ours, not the caller's ---------------------------------


def test_a_rule_that_cannot_answer_is_a_500_not_a_422(tmp_path):
    """The distinction matters: a 422 would tell the caller to fix their request.

    `RuleLogicError` means a signed rule passed load-time validation and still
    had no answer. Reported as a 4xx, a caller would retry a corrected request
    forever against a corpus defect only we can fix.

    The real corpus cannot reach this - the band-table and notice validators
    close every route to it - so the handler is exercised directly.
    """
    from bayyina.api.app import create_app
    from bayyina.rules_logic.errors import RuleLogicError

    app = create_app(audit_path=tmp_path / "audit.jsonl")

    def _boom() -> None:
        raise RuleLogicError("no band matched a gap of 0.5000")

    app.add_api_route("/_test_broken_rule", _boom, methods=["GET"])

    response = TestClient(app, raise_server_exceptions=False).get("/_test_broken_rule")
    assert response.status_code == 500
    # The caller is told nothing actionable, because there is nothing they can do.
    assert "0.5000" not in response.text


def test_the_web_checker_payload_is_accepted_exactly_as_it_is_sent(client):
    """The seam. Each side has been correct on its own before and still broken.

    `Checker.tsx` deliberately sends `market` with **only** a snapshot_id: we did
    not derive the figure, and inventing a contract_count would be inventing
    evidence. If `MarketEvidenceIn` ever made that field required, the backend
    suite would still pass (it builds its own payloads) and the frontend suite
    would still pass (it mocks fetch) while the one button that matters returned
    422. That is exactly how `/evaluate` went missing from the dev proxy.
    """
    checker = (ROOT / "frontend" / "src" / "components" / "Checker.tsx").read_text(encoding="utf-8")

    market = re.search(r"market:\s*\{([^}]*)\}", checker)
    assert market, "Checker.tsx no longer sends a `market` object — has the payload changed?"
    assert "contract_count" not in market.group(1), (
        "the checker is claiming a contract count for a figure it did not derive"
    )

    response = client.post(
        "/evaluate",
        json={
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
        },
    )

    assert response.status_code == 200, response.json()
    record = response.json()
    assert record["state"] == "CLEAR_WITH_CONDITIONS"
    assert record["conditions"] == ["market_average_not_derived"]
    assert record["confidence"] is None, "a figure we did not derive carries no confidence"
