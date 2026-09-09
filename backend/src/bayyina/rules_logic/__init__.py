"""Rule logic — pure functions, one module per rule type.

Every function here is deterministic and total: given the same inputs it returns
the same result, and it raises rather than guessing when the inputs cannot
support an answer. No I/O, no clock, no language model.
"""
