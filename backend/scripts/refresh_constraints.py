"""Re-resolve `constraints.txt` from the floors in `pyproject.toml`.

Upgrading dependencies should be something somebody did on purpose, in a diff
that says so — not something that happens to whoever pushes next. This script is
that deliberate act.

It resolves inside `python:3.11-slim`, because the resolution has to match the
runtime rather than whatever the developer's machine happens to be. On
2026-09-10 the machine was Python 3.13 on Windows and CI was 3.11 on Linux, and
that difference is exactly where a "works for me" build comes from.

    python scripts/refresh_constraints.py            # resolve and rewrite
    python scripts/refresh_constraints.py --check    # CI: is anything unpinned?

Then run the tests. A refresh nobody tested is a pin that lies.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS = ROOT / "constraints.txt"
IMAGE = "python:3.11-slim"


def requirements() -> list[str]:
    """The floors, exactly as declared. One source of truth for what we need."""
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    return [*project["dependencies"], *project["optional-dependencies"]["dev"]]


def normalise(name: str) -> str:
    """PEP 503: `pydantic_core` and `pydantic-core` are the same package."""
    return name.strip().lower().replace("_", "-").replace(".", "-")


def declared() -> set[str]:
    """Just the names from the floors, without their version specifiers."""
    names = set()
    for requirement in requirements():
        head = requirement.split(";")[0]
        for separator in (">=", "==", "<=", "~=", "!=", ">", "<", "["):
            head = head.split(separator)[0]
        names.add(normalise(head))
    return names


def pinned() -> set[str]:
    """Package names already pinned, normalised the way pip compares them."""
    if not CONSTRAINTS.is_file():
        return set()
    names = set()
    for line in CONSTRAINTS.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "==" in stripped:
            names.add(normalise(stripped.split("==")[0]))
    return names


def resolve() -> str:
    quoted = " ".join(f"'{requirement}'" for requirement in requirements())
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            IMAGE,
            "bash",
            "-c",
            f"pip install -q {quoted} >/dev/null 2>&1 && pip freeze --exclude-editable",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"resolution failed:\n{result.stderr}")
    return result.stdout.strip()


def header() -> str:
    """Keep everything above the first pin: it explains why the file exists."""
    existing = CONSTRAINTS.read_text(encoding="utf-8") if CONSTRAINTS.is_file() else ""
    lines: list[str] = []
    for line in existing.splitlines():
        if line.strip() and not line.startswith("#"):
            break
        lines.append(line)
    return "\n".join(lines).rstrip() + "\n\n"


def check() -> int:
    """Is every declared dependency pinned?

    Deliberately cheap: no Docker, no network, no resolution. Whether these are
    the versions a fresh resolve would produce is not a question CI should ask,
    because the answer changes every time somebody else publishes a release —
    which is the whole reason this file exists.

    What CI must catch is a dependency added to `pyproject.toml` and never
    pinned. That one installs unconstrained and quietly reintroduces the failure
    the constraints were written to stop.
    """
    missing = sorted(declared() - pinned())
    if missing:
        print("these dependencies are declared but not pinned:", file=sys.stderr)
        for name in missing:
            print(f"    {name}", file=sys.stderr)
        print(
            "Run `python scripts/refresh_constraints.py`, then run the tests.",
            file=sys.stderr,
        )
        return 1

    print(f"constraints.txt pins all {len(declared())} declared dependencies")
    return 0


def main() -> int:
    if "--check" in sys.argv:
        return check()

    resolved = resolve()
    CONSTRAINTS.write_text(header() + resolved + "\n", encoding="utf-8")
    print(f"wrote {CONSTRAINTS} ({len(resolved.splitlines())} pins)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
