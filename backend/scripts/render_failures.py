"""Render the failure taxonomy into the agent script set.

Generated, never authored. A spoken line edited in a script that disagrees with
what the service does is a caller told one thing while the tool does another —
and nothing would catch it, because a markdown file runs no tests.

    python scripts/render_failures.py [--check]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bayyina.api.errors import as_markdown  # noqa: E402

#: One directory per language the agent speaks. English only for now: a
#: translated failure line we have not had written would be worse than none,
#: because it would look finished (D-065).
TARGETS = (Path(__file__).resolve().parents[2] / "agent" / "scripts" / "en" / "failures.md",)


def main() -> int:
    check = "--check" in sys.argv
    expected = as_markdown()
    stale: list[Path] = []

    for target in TARGETS:
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current == expected:
            continue
        if check:
            stale.append(target)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected, encoding="utf-8")
        print(f"wrote {target}")

    if stale:
        for target in stale:
            print(f"STALE: {target}", file=sys.stderr)
        print(
            "Run `python scripts/render_failures.py` to bring them up to date.",
            file=sys.stderr,
        )
        return 1
    if check:
        print("failure scripts are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
