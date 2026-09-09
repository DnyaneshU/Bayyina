"""Why a rule could not produce an answer.

Two different failures hide inside a bare `ValueError`, and they belong to
different people. A rent of zero is something the caller can correct. A band
table with no matching row is something *we* got wrong in a signed file, and no
amount of retrying will fix it.

Keeping them apart is what lets the API answer 422 to one and 500 to the other
without catching `ValueError` broadly and turning a genuine bug into a polite
message about the caller's input.

Both subclass `ValueError`, so existing callers that catch it still work.
"""

from __future__ import annotations


class RuleInputError(ValueError):
    """The values supplied cannot be used. The caller can fix this."""


class RuleLogicError(ValueError):
    """The rule itself cannot answer. The corpus is wrong, not the request.

    Reaching this means a signed rule passed load-time validation and still had
    no answer to give - so it is a defect in our encoding or in the validator
    that was supposed to catch it, and it must be loud rather than absorbed.
    """
