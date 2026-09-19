"""Cash-move reason validation.

Pure Python: no `odoo` import. See specs/cash-move-reasons/spec.md
(Requirement: Pure Reason Validation Rule and the definition-time defense in
depth referenced by design.md's "Vault Reasons Must Be Out-Only" note).
"""

from dataclasses import dataclass

from .errors import ReasonError


@dataclass(frozen=True)
class ReasonSnapshot:
    id: int
    active: bool
    company_id: object  # int, or None for a shared (company-less) reason
    direction: str  # "out" / "in" / "both"
    is_vault: bool


def validate_reason_definition(direction, is_vault):
    """Reject a vault reason whose direction is not `out`."""
    if is_vault and direction != "out":
        raise ReasonError("VAULT_NOT_OUT")


def is_direction_compatible(direction, move_type):
    """True when a reason's `direction` may be used for `move_type`."""
    if move_type == "out":
        return direction in ("out", "both")
    if move_type == "in":
        return direction in ("in", "both")
    return False


def validate_reason(reason, move_type, company_id):
    """Validate a reason snapshot against a move type and company.

    Raises `ReasonError` with code MISSING, INACTIVE, WRONG_COMPANY,
    VAULT_NOT_OUT, or DIRECTION_MISMATCH.
    """
    if reason is None:
        raise ReasonError("MISSING")
    if not reason.active:
        raise ReasonError("INACTIVE")
    if reason.company_id is not None and reason.company_id != company_id:
        raise ReasonError("WRONG_COMPANY")
    if reason.is_vault and move_type != "out":
        raise ReasonError("VAULT_NOT_OUT")
    if not is_direction_compatible(reason.direction, move_type):
        raise ReasonError("DIRECTION_MISMATCH")
