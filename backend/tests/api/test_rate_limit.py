"""The public endpoints refuse to be hammered.

`PUBLIC_RATE_LIMIT_PER_MINUTE` was documented as an abuse guard from T1.1 and
implemented by nothing until T1.7. These are the tests that keep it real.
"""

import pytest
from fastapi.testclient import TestClient

from bayyina.api.app import create_app
from bayyina.api.rate_limit import FixedWindowLimiter
from bayyina.settings import Settings

BODY = {
    "rule_id": "notice_validity.dubai.law_26_2007_a14",
    "inputs": {"contract_expiry": "2026-12-31", "notice_served": "2026-11-01"},
    "input_sources": {"contract_expiry": "caller_stated", "notice_served": "caller_stated"},
}


@pytest.fixture
def client(tmp_path):
    settings = Settings(public_rate_limit_per_minute=3)
    return TestClient(create_app(audit_path=tmp_path / "audit.jsonl", settings=settings))


def test_requests_under_the_limit_are_served(client):
    for _ in range(3):
        assert client.post("/evaluate", json=BODY).status_code == 200


def test_the_limit_is_enforced(client):
    for _ in range(3):
        client.post("/evaluate", json=BODY)

    response = client.post("/evaluate", json=BODY)
    assert response.status_code == 429
    assert "3 per minute" in response.json()["detail"]


def test_a_throttled_response_says_when_to_retry(client):
    for _ in range(4):
        response = client.post("/evaluate", json=BODY)

    assert response.status_code == 429
    assert 0 < int(response.headers["Retry-After"]) <= 60


def test_a_throttled_response_is_still_timed(client):
    """A 429 is a response we serve, so it belongs in the latency numbers."""
    for _ in range(4):
        response = client.post("/evaluate", json=BODY)

    assert "x-response-ms" in response.headers


def test_healthz_is_never_rate_limited(client):
    """Platforms poll it every few seconds. Limiting it would fake an outage."""
    for _ in range(30):
        assert client.get("/healthz").status_code == 200


def test_throttling_writes_nothing_to_the_audit_log(client):
    """A refused request produced no evaluation, so there is nothing to record."""
    log = client.app.state.audit
    for _ in range(10):
        client.post("/evaluate", json=BODY)

    assert len(log.entries()) == 3
    assert log.verify_chain() == 3


# --- The limiter itself ------------------------------------------------------


def test_clients_are_counted_separately():
    """One caller must not be able to lock everyone else out."""
    limiter = FixedWindowLimiter(per_minute=2)
    assert limiter.check("1.1.1.1", now=0.0)[0]
    assert limiter.check("1.1.1.1", now=0.0)[0]
    assert not limiter.check("1.1.1.1", now=0.0)[0]

    assert limiter.check("2.2.2.2", now=0.0)[0]


def test_the_window_resets():
    limiter = FixedWindowLimiter(per_minute=1)
    assert limiter.check("1.1.1.1", now=0.0)[0]
    assert not limiter.check("1.1.1.1", now=30.0)[0]
    assert limiter.check("1.1.1.1", now=61.0)[0]


def test_the_counter_map_does_not_grow_without_bound():
    """A long-running process must not accumulate one entry per address seen."""
    limiter = FixedWindowLimiter(per_minute=1_000_000)
    for index in range(10_050):
        limiter.check(f"10.0.{index // 256}.{index % 256}", now=0.0)

    stale = limiter.check("9.9.9.9", now=120.0)
    assert stale[0]
    assert len(limiter._counts) < 10_050
