"""G7 at the process level — the wow moment, as a test.

`create_app()` loads and verifies the corpus *before* it returns an app. There is
no window in which the service is listening on a port with rules nobody attested
to: the process either starts with a verified corpus or does not start.
"""

from copy import deepcopy

import pytest
import yaml

from bayyina.api.app import create_app
from bayyina.registry.loader import (
    EmptyCorpusError,
    MalformedRuleError,
    TamperedRuleError,
    UnsignedRuleError,
)
from bayyina.registry.schema import Rule
from bayyina.registry.signing import rule_digest
from tests.registry.test_schema import MINIMAL


def _write(tmp_path, data: dict, name: str = "r.v1.yaml"):
    (tmp_path / name).write_text(yaml.safe_dump(data), encoding="utf-8")
    return tmp_path


def _signed(data: dict) -> dict:
    signed = {
        **deepcopy(data),
        "approval": {
            "status": "provisional",
            "approved_by": "Bayyina team",
            "approved_at": "2026-09-09T00:00:00Z",
            "signature": None,
        },
    }
    signed["approval"]["signature"] = rule_digest(Rule.model_validate(signed))
    return signed


def test_the_app_refuses_to_start_on_an_unsigned_corpus(tmp_path):
    """G7 at the process level. This is the wow moment."""
    with pytest.raises(UnsignedRuleError):
        create_app(rules_dir=_write(tmp_path, deepcopy(MINIMAL)))


def test_the_app_refuses_to_start_on_a_tampered_corpus(tmp_path):
    """One digit changed after signing. The demo, run as a test."""
    data = _signed(deepcopy(MINIMAL))
    data["bands"][0]["max_increase"] = 0.99
    with pytest.raises(TamperedRuleError):
        create_app(rules_dir=_write(tmp_path, data))


def test_the_app_refuses_to_start_on_an_empty_corpus(tmp_path):
    """A service with no rules would report healthy while answering nothing."""
    with pytest.raises(EmptyCorpusError):
        create_app(rules_dir=tmp_path)


def test_the_app_refuses_to_start_on_a_malformed_corpus(tmp_path):
    (tmp_path / "broken.v1.yaml").write_text("id: [unclosed", encoding="utf-8")
    with pytest.raises(MalformedRuleError):
        create_app(rules_dir=tmp_path)


def test_the_app_starts_on_the_production_corpus(tmp_path):
    """The corpus we actually ship boots."""
    app = create_app(audit_path=tmp_path / "audit.jsonl")
    assert app.state.rule_count == 2


def test_the_access_log_actually_emits(tmp_path, caplog):
    """A logger with no handler drops every line, and uvicorn's own access log
    hides the fact. The timing measurements are the point of T1.7, so this
    asserts they reach a handler rather than a silent logger.
    """
    import logging

    from fastapi.testclient import TestClient

    app = create_app(audit_path=tmp_path / "audit.jsonl")
    with caplog.at_level(logging.INFO, logger="bayyina.access"):
        TestClient(app).get("/healthz")

    assert any("GET /healthz 200" in message for message in caplog.messages)


def test_the_log_level_comes_from_settings(tmp_path):
    """LOG_LEVEL was documented in .env.example and read by nothing."""
    import logging

    from bayyina.settings import Settings

    create_app(audit_path=tmp_path / "audit.jsonl", settings=Settings(log_level="WARNING"))
    assert logging.getLogger("bayyina").level == logging.WARNING

    create_app(audit_path=tmp_path / "audit.jsonl", settings=Settings(log_level="INFO"))
    assert logging.getLogger("bayyina").level == logging.INFO


# --- Serving the built frontend ----------------------------------------------


def test_the_built_frontend_is_served_when_present(tmp_path):
    from fastapi.testclient import TestClient

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Bayyina</title>", encoding="utf-8")

    client = TestClient(
        create_app(audit_path=tmp_path / "audit.jsonl", static_dir=dist),
    )
    response = client.get("/")
    assert response.status_code == 200
    assert "Bayyina" in response.text


def test_the_static_mount_never_shadows_the_api(tmp_path):
    """A mount at "/" catches everything after it, so ordering is the guarantee."""
    from fastapi.testclient import TestClient

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html>frontend", encoding="utf-8")

    client = TestClient(create_app(audit_path=tmp_path / "audit.jsonl", static_dir=dist))
    assert client.get("/healthz").json()["rule_count"] == 2


def test_a_missing_frontend_is_normal_not_a_failure(tmp_path):
    """In development Vite serves the frontend. The API must still start."""
    from fastapi.testclient import TestClient

    client = TestClient(
        create_app(audit_path=tmp_path / "audit.jsonl", static_dir=tmp_path / "no-dist"),
    )
    assert client.get("/healthz").status_code == 200


def test_the_app_is_built_once_however_often_it_is_looked_up(monkeypatch):
    """uvicorn accesses `bayyina.api.app:app` more than once.

    Unmemoised, `__getattr__` built a complete application on every access: the
    corpus verified twice, the comparables database read twice, and **two
    `AuditLog` objects with a lock each** over the same file. Only one was ever
    served, so the chain was never at risk — but a second audit log holding a
    second lock is the exact shape of the bug D-035 exists to prevent.

    Caught by counting boot lines in a running container, not by any test.
    """
    import bayyina.api.app as module

    builds = 0
    real = module.create_app

    def counted(**kwargs):
        nonlocal builds
        builds += 1
        return real(**kwargs)

    monkeypatch.setattr(module, "create_app", counted)
    monkeypatch.delitem(module.__dict__, "app", raising=False)

    first = module.app
    second = module.app
    third = module.app

    assert builds == 1, f"the app was built {builds} times"
    assert first is second is third
    monkeypatch.delitem(module.__dict__, "app", raising=False)


def test_an_unbuilt_module_still_has_no_import_side_effect():
    """The other half of the contract: importing must not build anything, so a
    broken corpus fails the process that asked for an app rather than every test
    collection that imported `create_app`."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "import bayyina.api.app as m; print('app' in m.__dict__)"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False", "importing the module built an application"
