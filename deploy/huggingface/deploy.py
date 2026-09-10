"""Push Bayyina to a Hugging Face Space.

    python deploy/huggingface/deploy.py --space <user>/<space-name>
    python deploy/huggingface/deploy.py --space <user>/<space-name> --dry-run

**Why a script and not eight remembered steps.** The Space needs one thing the
GitHub repository does not have: `backend/data/comparables.duckdb`. It is
gitignored — a 1.3 MB build artifact derived from Dubai Land Department open
data, regenerable by `scripts/ingest_market.py`, and a derived file in source
control goes stale silently.

A Space built from the GitHub tree therefore has no market data. It boots, it is
honest about it (`/healthz` reports `degraded`, the checker offers manual entry
only), and it cannot do the thing the product is for. Deploying from this machine
is what carries the database across — the same property `fly deploy` has, and the
reason this is a push rather than a GitHub Action.

**A staging directory, not a second remote on this repository.** Force-pushing a
rewritten tree from inside the working repository is how somebody eventually
force-pushes it to `origin`. The staging copy has its own git history, one commit
deep, and nothing it does can reach GitHub.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPACE_README = Path(__file__).parent / "README.md"

#: Never, under any circumstances. A Space is public: `.env` holds real
#: credentials, and the audit log and case store hold operational data about
#: real people.
FORBIDDEN = (
    ".env",
    "audit.jsonl",
    "cases.db",
    "cases.db-wal",
    "cases.db-shm",
    "market.duckdb",
)

#: The one file the Space needs that git does not track. Everything else comes
#: from `git ls-files`.
MARKET_DATA = "backend/data/comparables.duckdb"


def run(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"failed: {' '.join(command)}\n{result.stdout}\n{result.stderr}")


def tracked_files() -> list[str]:
    """Every file git tracks, which is exactly what CI builds the image from.

    **Derived, never enumerated.** The first version of this script listed the
    paths by hand and left out `frontend/tsconfig.test.json` — which
    `tsconfig.json` references, so `tsc -b` failed and the image did not build.
    An enumerated list is a second copy of "what the project consists of", and
    it drifts the first time somebody adds a file.

    Taking the tracked set means the Space builds the same tree CI does, so CI
    passing is evidence the Space will build. The only deliberate addition is
    the market database, which is gitignored.
    """
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def stage(target: Path) -> list[str]:
    """Copy the deployable tree into `target`. Returns a summary of what moved."""
    summary: list[str] = []

    tracked = tracked_files()
    copied = 0
    for entry in tracked:
        source = ROOT / entry
        if not source.is_file():
            continue  # tracked but deleted in the working tree
        destination = target / entry
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied += 1
    summary.append(f"{copied} tracked files (the same tree CI builds)")

    market = ROOT / MARKET_DATA
    if market.is_file():
        destination = target / MARKET_DATA
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(market, destination)
        summary.append(f"{MARKET_DATA} (gitignored - the reason this script exists)")
    else:
        print(
            "  WARNING: no comparables.duckdb. The Space will run without market\n"
            "           data: /healthz reports degraded and the checker offers\n"
            "           manual entry only. Build one with\n"
            "             python backend/scripts/ingest_market.py <release.parquet>",
            file=sys.stderr,
        )

    # The Space card replaces the project README: Hugging Face reads its
    # frontmatter to decide the SDK and which port to route to.
    shutil.copy2(SPACE_README, target / "README.md")
    summary.append("README.md (the Space card, replacing the project one)")
    return summary


def assert_nothing_secret(target: Path) -> None:
    """The check that matters more than any other in this file.

    A Space is public. This runs over the staged tree rather than trusting the
    copy logic, because the failure it prevents — a credential or a real
    person's case reaching a public URL — is not recoverable by deleting it
    afterwards.
    """
    offenders = [
        str(path.relative_to(target))
        for path in target.rglob("*")
        if path.is_file() and path.name in FORBIDDEN
    ]
    if offenders:
        raise SystemExit(
            "REFUSING TO DEPLOY - these must never reach a public Space:\n  "
            + "\n  ".join(offenders)
        )


def space_url(space: str) -> str:
    user, name = space.split("/", 1)
    return f"https://{user}-{name}.hf.space".replace("_", "-").lower()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space", required=True, help="the Space, as <user>/<space-name>")
    parser.add_argument("--dry-run", action="store_true", help="stage and check, but do not push")
    args = parser.parse_args()

    if "/" not in args.space:
        raise SystemExit("--space must be <user>/<space-name>")

    staging = Path(tempfile.mkdtemp(prefix="bayyina-space-"))
    print(f"staging into {staging}")
    for line in stage(staging):
        print(f"  + {line}")

    assert_nothing_secret(staging)
    print("  checked: no secrets, no case data, no 360 MB build database")

    size = sum(f.stat().st_size for f in staging.rglob("*") if f.is_file())
    print(f"  tree is {size / 1_048_576:.1f} MB")

    url = space_url(args.space)

    if args.dry_run:
        print(f"\ndry run: nothing pushed. Inspect {staging}")
        print(f"would deploy to {url}")
        return 0

    remote = f"https://huggingface.co/spaces/{args.space}"
    run(["git", "init", "-q"], staging)
    run(["git", "checkout", "-q", "-b", "main"], staging)
    run(["git", "add", "-A"], staging)
    run(
        [
            "git",
            "-c",
            "user.email=deploy@bayyina.local",
            "-c",
            "user.name=Bayyina deploy",
            "commit",
            "-q",
            "-m",
            "Deploy Bayyina",
        ],
        staging,
    )
    run(["git", "remote", "add", "space", remote], staging)

    print(f"\npushing to {remote}")
    print("  username: your Hugging Face username")
    print("  password: an access token with write scope (not your account password)")
    subprocess.run(["git", "push", "--force", "space", "main"], cwd=staging, check=True)

    print(f"\nPushed. The Space builds for a few minutes, then serves at:\n  {url}")
    print("\nSet these in Space settings -> Variables and secrets, or it will not boot:")
    print("  BAYYINA_ENV       = production")
    print(f"  BAYYINA_BASE_URL  = {url}")
    print("\nThen check:")
    print(f"  curl -s {url}/healthz")
    print("  expect status ok and market_data_loaded true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
