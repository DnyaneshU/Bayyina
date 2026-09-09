"""Canonical hashing and signature verification — guardrail G7.

A signature is a human attestation that an encoding faithfully reflects its
source. Signing is therefore deliberately manual (see `scripts/sign_rule.py`);
automating it would make it meaningless.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from bayyina.registry.schema import Rule

DIGEST_PREFIX = "sha256:"


def canonical_bytes(body: dict[str, Any]) -> bytes:
    """Serialise deterministically.

    Sorted keys and no incidental whitespace, so that re-ordering a YAML file or
    reformatting it does not change the digest. `ensure_ascii=False` keeps Arabic
    source text as itself rather than escaping it.

    Shared with the audit log, so that the two hashes in the system - the one
    attesting to a rule and the one chaining an evaluation - are produced by the
    same rule about what the bytes are.
    """
    return json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def rule_digest(rule: Rule) -> str:
    """Hash of the rule body, excluding its approval block."""
    digest = hashlib.sha256(canonical_bytes(rule.body_for_signing())).hexdigest()
    return f"{DIGEST_PREFIX}{digest}"


def verify_signature(rule: Rule) -> bool:
    """True when the recorded signature matches the current rule body."""
    if not rule.approval.signature:
        return False
    return rule.approval.signature == rule_digest(rule)
