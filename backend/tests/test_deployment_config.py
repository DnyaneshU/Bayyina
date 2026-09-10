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


# --- The development proxy ---------------------------------------------------


def test_the_dev_proxy_forwards_every_backend_route():
    """A route the proxy does not list 404s against the Vite dev server.

    `/evaluate` was missing, so the interface loaded, the health check resolved,
    and the one button that matters returned "Request failed (404)". Nothing in
    either test suite noticed, because each side was correct on its own.
    """
    import tempfile

    from fastapi.routing import APIRoute

    from bayyina.api.app import create_app

    config = (ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    app = create_app(audit_path=Path(tempfile.mkdtemp()) / "audit.jsonl")

    served = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute) and not route.path.startswith("/openapi")
    }
    assert served, "no API routes found — has the app changed?"

    missing = [path for path in sorted(served) if f'"{path}"' not in config]
    assert not missing, (
        f"these backend routes are not proxied in frontend/vite.config.ts, so they "
        f"404 in development: {missing}"
    )


# --- Market data in the image -------------------------------------------------


def test_the_image_carries_the_serving_database_not_the_build_one(dockerfile):
    """343 MB of contract rows must not ride along to serve 1,324 numbers.

    The request path reads `comparables`, `areas` and one provenance row. The
    build database beside them holds 5.3 million individual tenancy records that
    nothing at runtime touches, and shipping them in a public image would be
    needless in both size and disclosure.
    """
    assert re.search(r"^COPY\s+backend/data/\s+\./data/", dockerfile, re.MULTILINE), (
        "the image does not copy the data directory"
    )

    ignored = DOCKERIGNORE.read_text(encoding="utf-8")
    assert "backend/data/" in ignored, "the data directory must be excluded by default"
    assert "!backend/data/comparables.duckdb" in ignored, (
        "the serving database is excluded, so the image would ship with no market data"
    )
    assert "!backend/data/market.duckdb" not in ignored, (
        "the 359 MB build database is being re-included into the image"
    )
    assert "!backend/data/raw" not in ignored, "the 200 MB release is being re-included"


def test_the_directory_is_copied_rather_than_the_file():
    """`COPY backend/data/comparables.duckdb` would fail the build when there is
    no market data — and market data is optional by design (D-074).

    Copying the directory succeeds either way, and `/healthz` reports which
    happened instead of the image refusing to exist.
    """
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY backend/data/comparables.duckdb" not in dockerfile, (
        "copying the file directly makes a build without market data fail"
    )


def test_the_service_and_the_image_agree_on_which_database_to_read():
    """The app defaults to one filename; the ingest writes two. A mismatch means
    a container that ships market data and then reports it missing."""
    from bayyina.api.app import create_app  # noqa: F401

    app_source = (ROOT / "backend" / "src" / "bayyina" / "api" / "app.py").read_text("utf-8")
    served = re.search(r'Path\(settings\.data_dir\)\s*/\s*"([^"]+\.duckdb)"', app_source)
    assert served, "the app no longer names a default comparables database"

    script = (ROOT / "backend" / "scripts" / "ingest_market.py").read_text("utf-8")
    written = re.search(
        r'"--serving-database".*?default=Path\("data/([^"]+\.duckdb)"\)', script, re.S
    )
    assert written, "the ingest script no longer writes a serving database"

    assert served.group(1) == written.group(1), (
        f"the service reads {served.group(1)} but the ingest writes {written.group(1)}"
    )

    ignored = DOCKERIGNORE.read_text(encoding="utf-8")
    assert f"!backend/data/{served.group(1)}" in ignored, (
        f"the image excludes {served.group(1)}, which is the file the service reads"
    )


# --- Files that are not Python --------------------------------------------


def test_every_non_python_file_the_package_needs_is_declared_as_package_data():
    """`pip install .` copies `.py` and nothing else unless told otherwise.

    The evidence templates are `.j2`. Without a declaration the container builds,
    boots, verifies its corpus, serves `/healthz` — and then fails on the first
    evidence pack with "template not found", which is the worst possible moment
    and the least obvious cause.

    Written as a sweep rather than a single assertion so that the next
    non-Python file added to the package is caught by the same test.
    """
    import fnmatch
    import tomllib

    with (ROOT / "backend" / "pyproject.toml").open("rb") as handle:
        declared = tomllib.load(handle)["tool"]["setuptools"].get("package-data", {})

    source = ROOT / "backend" / "src" / "bayyina"
    ignored = {".pyc", ".pyo", ".pyi", ".typed"}
    undeclared: list[str] = []

    for path in sorted(source.rglob("*")):
        if path.is_dir() or path.suffix in {".py"} | ignored or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(source)
        package = f"bayyina.{relative.parts[0]}" if len(relative.parts) > 1 else "bayyina"
        within = "/".join(relative.parts[1:]) if len(relative.parts) > 1 else relative.name
        patterns = declared.get(package, []) + declared.get("bayyina", []) + declared.get("*", [])
        if not any(fnmatch.fnmatch(within, pattern) for pattern in patterns):
            undeclared.append(f"{relative.as_posix()} (looked for a pattern under {package!r})")

    assert not undeclared, (
        "these files ship in the source tree but not in an installed package:\n  "
        + "\n  ".join(undeclared)
    )
