"""Law 26 of 2007, Article 14 — notice of a change to tenancy terms.

Notice must be served at least a set number of days before the contract expires.
The number comes from the signed rule file, never from a constant here, so an
amendment or a different jurisdiction changes only data.

This rule needs no market data, which is why a caller whose comparable is too
thin to answer still leaves with something (guardrail G5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from bayyina.rules_logic.errors import RuleLogicError


@dataclass(frozen=True)
class NoticeResult:
    """What the rule determined, and the working behind it."""

    verdict: str
    days_notice: int
    required_days: int
    shortfall_days: int


def evaluate(contract_expiry: date, notice_served: date, required_days: int) -> NoticeResult:
    """Count the days of notice given and compare against what the rule requires.

    `days_notice` may be negative when notice was served after expiry. The
    shortfall is computed from the signed difference rather than from a clamped
    one, so a notice thirty days late reports 120 days short, not 90.
    """
    if required_days <= 0:
        # RuleLogicError, not RuleInputError: required_days comes from the
        # signed rule file, never from the caller. Reaching this means the
        # corpus is wrong, so it must not be reported as the caller's mistake.
        raise RuleLogicError(
            f"required_days must be positive; {required_days} would validate every notice"
        )

    days_notice = (contract_expiry - notice_served).days
    shortfall = max(0, required_days - days_notice)

    return NoticeResult(
        verdict="valid" if days_notice >= required_days else "invalid",
        days_notice=days_notice,
        required_days=required_days,
        shortfall_days=shortfall,
    )
