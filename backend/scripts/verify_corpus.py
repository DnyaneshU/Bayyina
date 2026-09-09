"""Verify every rule in a corpus. Exits non-zero on any problem.

    python scripts/verify_corpus.py rules/

This is guardrail G7 in CI. A rule edited without re-signing fails the build,
which is the control that catches an honest mistake rather than only an attack.
The same check runs again at service boot.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bayyina.registry.loader import CorpusError, load_rules


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default="rules", type=Path)
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help=(
            "accept a corpus with no rules. No longer used by CI: the corpus "
            "exists, so an empty rules/ means a deleted file or a container build "
            "that did not copy it. Kept only for bootstrapping a new jurisdiction."
        ),
    )
    args = parser.parse_args()

    if not args.directory.exists():
        print(f"No corpus directory: {args.directory}", file=sys.stderr)
        return 1

    try:
        rules = load_rules(args.directory, allow_empty=args.allow_empty)
    except CorpusError as exc:
        print("CORPUS REJECTED", file=sys.stderr)
        print(f"  {exc}", file=sys.stderr)
        return 1

    if not rules:
        print(f"No rules in {args.directory} (allowed explicitly)")
        return 0

    print(f"Corpus OK - {len(rules)} rule(s) in {args.directory}")
    for rule in rules.values():
        print(
            f"  {rule.id} v{rule.version}"
            f"  [{rule.approval.status.value}]"
            f"  {rule.source.clause}"
            f"  {rule.approval.signature}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
