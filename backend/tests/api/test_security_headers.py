"""Headers that constrain what a browser will do with our pages.

The checker shows someone a figure they may act on. A page that can be framed
inside another site, or that a browser will re-fetch over plain HTTP, is a page
whose result can be misrepresented.
"""

import pytest
from fastapi.testclient import TestClient

from bayyina.api.app import create_app
from bayyina.api.security import CONTENT_SECURITY_POLICY


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    audit = tmp_path_factory.mktemp("audit") / "audit.jsonl"
    return TestClient(create_app(audit_path=audit))


def test_the_page_cannot_be_framed(client):
    """Clickjacking a verdict is misrepresenting a legal result."""
    headers = client.get("/healthz").headers
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


def test_content_type_is_not_sniffed(client):
    assert client.get("/healthz").headers["X-Content-Type-Options"] == "nosniff"


def test_the_policy_allows_no_third_party_origin(client):
    """No analytics, no CDN. A policy that permits one invites adding one."""
    policy = client.get("/healthz").headers["Content-Security-Policy"]
    assert "connect-src 'self'" in policy
    assert "script-src 'self'" in policy
    assert "https://" not in policy


def test_headers_are_present_on_the_api_too(client):
    body = {
        "rule_id": "notice_validity.dubai.law_26_2007_a14",
        "inputs": {"contract_expiry": "2026-12-31", "notice_served": "2026-11-01"},
        "input_sources": {"contract_expiry": "caller_stated", "notice_served": "caller_stated"},
    }
    assert client.post("/evaluate", json=body).headers["X-Frame-Options"] == "DENY"


def test_hsts_is_sent_only_over_tls(client):
    """Sent on a plain-HTTP dev server it pins localhost to HTTPS in the
    developer's browser, which is genuinely painful to undo."""
    assert "Strict-Transport-Security" not in client.get("/healthz").headers

    forwarded = client.get("/healthz", headers={"X-Forwarded-Proto": "https"})
    assert forwarded.headers["Strict-Transport-Security"].startswith("max-age=31536000")


def test_hsts_is_not_submitted_for_preloading(client):
    """Preload is effectively irreversible and this host may move."""
    response = client.get("/healthz", headers={"X-Forwarded-Proto": "https"})
    assert "preload" not in response.headers["Strict-Transport-Security"]


def test_the_policy_matches_what_the_build_actually_needs():
    """Verified against the built page, not assumed.

    The Vite build emits external scripts and an external stylesheet with no
    inline script and no inline style, which is what lets this policy stay
    strict. If a build starts inlining, this is the reminder of why it broke.
    """
    assert "'unsafe-inline'" not in CONTENT_SECURITY_POLICY
    assert "'unsafe-eval'" not in CONTENT_SECURITY_POLICY
