"""The deployment configuration, checked here rather than in front of a judge.

Everything in this file failed once, or would have. The container crash-looped on
its first CI run because the image set `BAYYINA_ENV=production` without the https
base URL that production requires — the guardrail worked exactly as designed, and
the image was wrong. Worse, a comment saying the variable was *deliberately not
set* sat directly above the line setting it, so the file read as correct.

These are the checks that only fail at deploy time, which is the worst time.
"""

import re
import shutil
import subprocess
import sys
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


def test_a_sleeping_tier_is_only_used_with_its_mitigation_written_down():
    """We are on Render's free tier, and it sleeps after fifteen minutes.

    That was not the plan. Hugging Face gated Docker behind a paid plan and Fly
    and Railway both want a card, so a free tier that sleeps is what running the
    real container without one costs (D-101).

    The test therefore changed from "never use a sleeping tier" to "if you do,
    the mitigation is in the file". A cold start in front of the judge opening
    the Box Q link is still a real cost; what makes it acceptable is a keep-alive
    that somebody set up, and the only way that survives being forgotten is to
    write it beside the setting that makes it necessary.
    """
    render_text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    render = yaml.safe_load(render_text)

    if render["services"][0]["plan"] == "free":
        assert "uptimerobot" in render_text.lower() or "cron-job" in render_text.lower(), (
            "the free tier sleeps and no keep-alive is documented, so the first "
            "visitor waits fifty seconds"
        )
        assert "/healthz" in render_text
        assert "750" in render_text, (
            "the free instance-hour ceiling is not recorded, and a keep-alive runs into it"
        )


def test_fly_would_be_kept_warm_if_we_used_it():
    """`fly.toml` is the config we switch to the moment there is a card.

    Kept correct rather than deleted: it is a one-line decision to move, and a
    config that has silently rotted is not a decision anybody can take quickly.
    """
    fly = (ROOT / "fly.toml").read_text(encoding="utf-8")
    assert "auto_stop_machines = false" in fly
    assert "min_machines_running = 1" in fly


def test_the_host_we_use_still_runs_our_own_container():
    """The line we did not cross.

    A free Gradio Space was available and would have meant no Dockerfile: no
    build-time corpus verification, no non-root container, and no tamper demo —
    that demo exists only because there is an image build to refuse. Paying a
    cold start is the cheaper of the two costs.
    """
    render = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    service = render["services"][0]

    assert service["runtime"] == "docker"
    assert service["dockerfilePath"] == "./Dockerfile"


# --- The development proxy ---------------------------------------------------


def test_the_dev_proxy_forwards_every_backend_route():
    """A route the proxy does not list 404s against the Vite dev server.

    `/evaluate` was missing, so the interface loaded, the health check resolved,
    and the one button that matters returned "Request failed (404)". Nothing in
    either test suite noticed, because each side was correct on its own.
    """
    import tempfile

    from bayyina.api.app import create_app

    config = (ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    app = create_app(audit_path=Path(tempfile.mkdtemp()) / "audit.jsonl")

    # The generated OpenAPI document, not `app.routes`.
    #
    # This walked the route table matching `isinstance(route, APIRoute)` until
    # FastAPI 0.141 / Starlette 1.6 stopped flattening included routers onto the
    # application: the paths now sit behind an internal `_IncludedRouter` and the
    # match found nothing. Asserting against a framework's private route objects
    # means a dependency release can turn this red with no change to our source,
    # which is exactly what happened. The OpenAPI schema is the published
    # contract and names precisely the paths the API answers on.
    #
    # It also excludes what it should: `/docs`, `/redoc` and `/openapi.json` are
    # plain Starlette routes rather than API operations, and the built frontend
    # is a Mount, so none of them appear here and none of them need proxying.
    served = set(app.openapi()["paths"])
    assert served, "no API routes found — has the app changed?"

    # Vite matches proxy keys as path *prefixes*, so `/provenance` forwards
    # `/provenance/rent_increase...` too. Comparing whole paths would demand a
    # config entry per path template - `/provenance/{rule_id}` and every future
    # one - which is not how the dev server works and would train whoever hits
    # it to add noise until the test went quiet.
    proxied = set(re.findall(r'"(/[^"]*)":\s*\{\s*target', config))
    assert proxied, "no proxy entries found - has vite.config.ts changed shape?"

    missing = [
        path
        for path in sorted(served)
        if not any(path == prefix or path.startswith(prefix + "/") for prefix in proxied)
    ]
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


def test_the_data_directory_survives_a_checkout_with_no_market_data():
    """The image build needs `backend/data/` to exist. Nothing in it is committed.

    Every file the directory normally holds is ignored - the 359 MB build
    database, the raw release, the audit log - so a fresh clone has no
    `backend/data/` at all and Docker fails at `COPY backend/data/ ./data/`
    with `"/backend/data": not found`. Copying the directory rather than the
    file (above) tolerates an *empty* directory, not an *absent* one.

    This is why the image job went red while every local build stayed green:
    the developer machine has 359 MB of market data sitting in that directory
    and the CI runner has none. A committed placeholder is what closes the gap.
    """
    keep = ROOT / "backend" / "data" / ".gitkeep"
    assert keep.is_file(), (
        "backend/data/.gitkeep is missing, so a clean checkout has no "
        "backend/data/ and `COPY backend/data/ ./data/` cannot resolve"
    )

    # The directory disappeared from CI because *everything* in it is ignored,
    # not because anyone forgot to `git add`. So the property under test is that
    # this one path is not ignored: a later `backend/data/*` rule would silently
    # undo the fix and turn the image build red again, here and nowhere else.
    #
    # Guarded on the checkout rather than on the binary. Running this from an
    # extracted tarball - which is what the container build does - there is no
    # repository to ask, and a `git` that answers 128 for "not a repository"
    # would otherwise read as a pass.
    if shutil.which("git") and (ROOT / ".git").exists():
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "backend/data/.gitkeep"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        # 0 means git ignores it; 1 means it does not. Anything else is git
        # failing to answer, and a test must not read that as success.
        assert ignored.returncode == 1, (
            "backend/data/.gitkeep is excluded by .gitignore, so it cannot reach "
            "a checkout, backend/data/ will not exist there, and the image build "
            "fails at `COPY backend/data/ ./data/` exactly as it did before"
        )

    ignored = DOCKERIGNORE.read_text(encoding="utf-8")
    assert "!backend/data/.gitkeep" in ignored, (
        "the placeholder is excluded from the build context, so backend/data/ "
        "is empty again and Docker cannot copy it"
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


# --- Reproducible installs ----------------------------------------------------


def test_every_declared_dependency_is_pinned():
    """A green build must stay green without anyone touching it.

    The floors in `pyproject.toml` say what the code needs. Alone, they mean
    every install resolves whatever was published that morning — and on
    2026-09-10 that turned three passing suites into three red CI jobs with no
    change to our source (D-087).
    """
    result = subprocess.run(
        [sys.executable, "scripts/refresh_constraints.py", "--check"],
        cwd=ROOT / "backend",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_ci_installs_the_pinned_set():
    """A constraints file nothing installs with is a file that documents a wish."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "-c constraints.txt" in workflow, (
        "CI does not install with constraints, so it still resolves whatever was "
        "released this morning"
    )


def test_the_image_installs_the_same_set_the_tests_ran_against(dockerfile):
    """Otherwise the container ships dependencies nothing ran the suite against."""
    assert "constraints.txt" in dockerfile, (
        "the image installs unpinned, so it can differ from what CI tested"
    )
    assert re.search(r"COPY .*constraints\.txt", dockerfile), (
        "constraints.txt is used but never copied into the build"
    )


#: Committed on purpose: 1,324 aggregate medians, no individual contract or
#: party, and the deployed service needs it to answer at all (D-102).
PUBLISHABLE = {".gitkeep", "comparables.duckdb"}


def test_no_operational_data_is_tracked_in_the_repository():
    """`backend/data/` holds two very different kinds of thing.

    One is a public aggregate derived from open data, committed deliberately so
    a host that builds from git can serve real comparables.

    The other is consent records, case rows and the full body of every evidence
    pack. The ignore rules covered `*.duckdb` and `*.jsonl` because those were
    the formats at the time; SQLite arrived with the case store and was
    committed before anyone noticed - 28 cases and 167 pack bodies, synthetic
    that time.

    The distinction the test encodes is not file format. It is whether the
    contents are about a person.
    """
    if not shutil.which("git") or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")

    tracked = subprocess.run(
        ["git", "ls-files", "backend/data/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.split()

    offenders = [path for path in tracked if Path(path).name not in PUBLISHABLE]
    assert not offenders, (
        "these are about real people and must not be in the repository:\n  "
        + "\n  ".join(offenders)
        + "\n\nUntrack them with `git rm --cached <path>` and commit."
    )


def test_the_committed_market_data_is_the_aggregate_and_not_the_release():
    """360 MB of individual tenancy contracts must never be committed.

    `comparables.duckdb` is the serving database: medians per cell, with no row
    describing anybody. `market.duckdb` beside it holds 9.8M contracts with
    parties and amounts, and it stays out of both the repository and the image.
    """
    if not shutil.which("git") or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")

    tracked = subprocess.run(
        ["git", "ls-files", "backend/data/"], cwd=ROOT, capture_output=True, text=True
    ).stdout.split()

    assert not [p for p in tracked if "market.duckdb" in p], (
        "the 360 MB build database is in the repository"
    )

    serving = ROOT / "backend" / "data" / "comparables.duckdb"
    if serving.is_file():
        size_mb = serving.stat().st_size / 1_048_576
        assert size_mb < 25, (
            f"comparables.duckdb is {size_mb:.0f} MB. The serving database is "
            f"aggregates; at this size it is carrying contract rows"
        )


# --- The Hugging Face Space ---------------------------------------------------


SPACE = ROOT / "deploy" / "huggingface"


def _space_frontmatter() -> dict:
    text = (SPACE / "README.md").read_text(encoding="utf-8")
    assert text.startswith("---\n"), "the Space card has no YAML frontmatter"
    return yaml.safe_load(text.split("---", 2)[1])


def test_the_space_declares_the_port_the_container_actually_serves():
    """Spaces route to `app_port`, and the default is 7860.

    Get this wrong and the build succeeds, the container starts, and the Space
    shows a blank page forever — because nothing is listening where Hugging Face
    is looking.
    """
    declared = _space_frontmatter()["app_port"]
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert f"EXPOSE {declared}" in dockerfile, (
        f"the Space routes to {declared} and the Dockerfile does not expose it"
    )
    assert f'"--port", "{declared}"' in dockerfile, (
        f"the Space routes to {declared} and uvicorn does not bind it"
    )


def test_the_space_builds_from_our_dockerfile():
    front = _space_frontmatter()
    assert front["sdk"] == "docker", "a Python SDK Space would ignore the Dockerfile"
    assert DOCKERFILE.is_file()


def test_the_space_card_does_not_overstate_what_this_is():
    """The card is the first thing anyone reads, so the disclosures live there too.

    A Space page describing a rent checker without saying it is not legal advice
    is the same failure as a pack without the disclosure, in the place most
    people will actually see.
    """
    # Whitespace-normalised: the card is prose wrapped at 80 columns, so a
    # phrase the test looks for is routinely split across a line break.
    raw = (SPACE / "README.md").read_text(encoding="utf-8").lower()
    text = " ".join(raw.split())

    assert "not legal advice" in text
    assert "not an official determination" in text
    assert "not a government entity" in text
    assert "rera" in text, "the card must not let our figure read as the official index"


def test_the_deploy_script_refuses_to_ship_secrets_or_case_data():
    """A Space is public, and a leaked case is not recoverable by deleting it."""
    script = (SPACE / "deploy.py").read_text(encoding="utf-8")

    for forbidden in (".env", "audit.jsonl", "cases.db", "market.duckdb"):
        assert f'"{forbidden}"' in script, (
            f"{forbidden} is not on the deploy script's forbidden list"
        )
    assert "assert_nothing_secret" in script


def test_the_deploy_script_carries_the_market_data():
    """The one thing the GitHub tree does not have, and the reason it exists."""
    script = (SPACE / "deploy.py").read_text(encoding="utf-8")
    assert "backend/data/comparables.duckdb" in script


def test_the_deploy_script_does_not_enumerate_the_project():
    """It stages `git ls-files`, not a hand-written list.

    The first version listed the paths and left out `frontend/tsconfig.test.json`,
    which `tsconfig.json` references - so `tsc -b` failed and the image did not
    build. A list of "what the project consists of" drifts the first time
    somebody adds a file, and it drifts silently until a deploy.

    Taking the tracked set means the Space builds the tree CI already proves.
    """
    script = (SPACE / "deploy.py").read_text(encoding="utf-8")

    assert "git" in script and "ls-files" in script, (
        "the deploy script no longer derives its file list from git"
    )
    assert "INCLUDE = (" not in script, (
        "an enumerated include list is back; it will drift and only a deploy will notice"
    )
