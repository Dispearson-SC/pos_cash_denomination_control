"""Closing decision table.

Pure Python: no `odoo` import. See specs/closing-manager-override/spec.md.
"""

from enum import Enum


class ClosingDecision(Enum):
    ALLOWED = "allowed"
    ALLOWED_FLAGGED = "allowed_flagged"
    REJECTED = "rejected"


def evaluate_closing(count_required, has_valid_count, is_manager):
    """Decide whether a session may close without a recorded breakdown.

    Returns `ALLOWED` when no count is required or a valid count exists,
    `ALLOWED_FLAGGED` when a count is required, missing/invalid, and the
    acting user is a POS manager, and `REJECTED` otherwise.
    """
    if not count_required or has_valid_count:
        return ClosingDecision.ALLOWED
    if is_manager:
        return ClosingDecision.ALLOWED_FLAGGED
    return ClosingDecision.REJECTED
