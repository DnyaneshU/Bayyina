"""The deployment configuration, checked here rather than in front of a judge.

Everything in this file failed once, or would have. The container crash-looped on
its first CI run because the image set `BAYYINA_ENV=production` without the https
base URL that production requires — the guardrail worked exactly as designed, and
the image was wrong. Worse, a comment saying the variable was *deliberately not
set* sat directly above the line setting it, so the file read as correct.

These are the checks that only fail at deploy time, which is the worst time.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


# --- The image must not assume where it runs ---------------------------------


def test_the_image_does_not_set_the_environment_name(dockerfile):
    """`BAYYINA_ENV=production` in the image makes `docker run` crash.

    Production requires an https BAYYINA_BASE_URL (D-045), which the image cannot
    know. The platform config sets the pair together, because they are only
    meaningful together.
    """
    assignments = re.findall(r"^\s*BAYYINA_ENV=.*$", dockerfile, re.MULTILINE)
    assert not assignments, f"the image sets the environment name: {assignments}"


def test_the_image_does_not_bake_in_a_base_url(dockerfile):
    """It is per-deployment, and a stale one would send residents a dead link."""
    assert not re.findall(r"^\s*BAYYINA_BASE_URL=", dockerfile, re.MULTILINE)


def test_the_image_sets_the_paths_it_needs(dockerfile):
    """Each must name a real Settings field, or it is silently ignored."""
    from bayyina.settings import Settings

    declared = {name.upper() for name in Settings.model_fields}
    for variable in ("RULES_DIR", "DATA_DIR", "FRONTEND_DIST"):
        assert re.search(rf"^\s*{variable}=", dockerfile, re.MULTILINE), f"{variable} unset"
        assert variable in declared, f"{variable} is not a Settings field"


# --- Guardrails that must survive containerisation ---------------------------


def test_the_corpus_is_verified_while_building_the_image(dockerfile):
    """G7 as early as it can go: an image with an unreviewed rule cannot exist."""
    assert re.search(r"RUN\s+python\s+scripts/verify_corpus\.py", dockerfile)


def test_the_container_does_not_run_as_root(dockerfile):
    """A process that reads signed rules and appends to an audit log has no
    reason to be able to modify its own code."""
    assert re.search(r"^USER\s+bayyina", dockerfile, re.MULTILINE)
    assert re.search(r"useradd.*--uid\s+10001", dockerfile)

    user_line = dockerfile.index("\nUSER ")
    assert dockerfile.index("\nCMD ") > user_line, "CMD must come after USER"


def test_uvicorn_trusts_the_proxy_headers(dockerfile):
    """Without these the app believes every request is plain HTTP from the proxy,
    which suppresses HSTS and collapses the rate limiter onto one client."""
    assert "--proxy-headers" in dockerfile
    assert "--forwarded-allow-ips" in dockerfile


# --- The build context -------------------------------------------------------


def test_the_build_context_excludes_secrets_and_data():
    ignored = DOCKERIGNORE.read_text(encoding="utf-8")
    for pattern in (".env", "*.pem", "*.key", "backend/data/", "**/node_modules/"):
        assert pattern in ignored, f"{pattern} is not excluded from the image"
    assert "!.env.example" in ignored, "the template should still ship"


# --- Platform configuration --------------------------------------------------


def test_platform_configs_set_production_and_arrange_a_base_url():
    """Setting one without the other is the crash this file exists to prevent."""
    fly = (ROOT / "fly.toml").read_text(encoding="utf-8")
    assert 'BAYYINA_ENV = "production"' in fly
    # Not a literal value: it belongs in `fly secrets`, and the file must say so.
    assert "BAYYINA_BASE_URL" in fly
    assert "fly secrets set BAYYINA_BASE_URL" in fly

    render = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    env_vars = {entry["key"]: entry for entry in render["services"][0]["envVars"]}
    assert env_vars["BAYYINA_ENV"]["value"] == "production"
    assert env_vars["BAYYINA_BASE_URL"].get("sync") is False, "must be set in the dashboard"


def test_both_platform_configs_health_check_the_corpus():
    """A machine whose rules did not verify must not receive traffic."""
    fly = (ROOT / "fly.toml").read_text(encoding="utf-8")
    assert 'path = "/healthz"' in fly

    render = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    assert render["services"][0]["healthCheckPath"] == "/healthz"


def test_neither_platform_config_uses_a_sleeping_free_tier():
    """A cold start in front of the judge opening the Box Q link is a cost we
    decided not to pay. See the notes at the top of both files."""
    fly = (ROOT / "fly.toml").read_text(encoding="utf-8")
    assert "auto_stop_machines = false" in fly
    assert "min_machines_running = 1" in fly

    render = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    assert render["services"][0]["plan"] != "free"
