"""Sign a rule file in place.

    python scripts/sign_rule.py rules/<file>.yaml
    python scripts/sign_rule.py rules/<file>.yaml --approver "Jane Doe, UAE counsel" --certified

A signature is a human attestation that this encoding faithfully reflects its
source clause. Signing is deliberately manual and deliberately unautomated —
automating it would make it meaningless.

Default status is `provisional`: the encoding loads, and the agent discloses
aloud that it awaits qualified review. Pass --certified only when a qualified
reviewer has actually checked the encoding against the source document.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from bayyina.registry.schema import Rule
from bayyina.registry.signing import rule_digest

DEFAULT_APPROVER = "Bayyina team"


def _block_style_for_multiline(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    """Keep multi-line strings readable when the file is rewritten.

    Signing rewrites the whole file. Without this, a five-clause verbatim quote
    comes back as one escaped line, and "a non-programmer can read the diff" —
    a stated reason for keeping rules in YAML — stops being true.
    """
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, _block_style_for_multiline, Dumper=yaml.SafeDumper)


def sign(path: Path, approver: str, certified: bool) -> str:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    # Blank the signature before hashing: the digest covers the rule body only,
    # so whatever is currently recorded must not influence it.
    data["approval"] = {
        "status": "certified" if certified else "provisional",
        "approved_by": approver,
        "approved_at": datetime.now(UTC).isoformat(),
        "signature": None,
    }
    data["approval"]["signature"] = rule_digest(Rule.model_validate(data))

    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return data["approval"]["signature"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="rule YAML file to sign")
    parser.add_argument("--approver", default=DEFAULT_APPROVER)
    parser.add_argument(
        "--certified",
        action="store_true",
        help="only when a qualified reviewer has checked it against the source",
    )
    args = parser.parse_args()

    if not args.path.exists():
        print(f"Not found: {args.path}", file=sys.stderr)
        return 1

    signature = sign(args.path, args.approver, args.certified)
    status = "certified" if args.certified else "provisional"
    print(f"signed {args.path.name} [{status}] by {args.approver}")
    print(f"  {signature}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
