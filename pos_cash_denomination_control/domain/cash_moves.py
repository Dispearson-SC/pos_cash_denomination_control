"""Cash-move type rule and count-required decision.

Pure Python: no `odoo` import. Backs the pure-rule portion of spec
`cash-in-control` and the `count_required` decision design.md's data model
section describes for each move type (opening/out/in/closing).
"""

from dataclasses import dataclass

from .errors import MoveTypeError

_KNOWN_MOVE_TYPES = ("in", "out")


@dataclass(frozen=True)
class CountToggles:
    """Snapshot of the four `pos.config` denomination-count toggles plus
    `cash_in_enabled`, which additionally gates the cash-IN toggle."""

    cash_in_enabled: bool = False
    opening_required: bool = False
    out_required: bool = False
    in_required: bool = False
    closing_required: bool = False


def validate_move_type(move_type, cash_in_enabled):
    """Reject an unknown move type, or cash-IN when it is disabled."""
    if move_type not in _KNOWN_MOVE_TYPES:
        raise MoveTypeError("UNKNOWN_TYPE", move_type=move_type)
    if move_type == "in" and not cash_in_enabled:
        raise MoveTypeError("CASH_IN_DISABLED")


def count_required(move_type, toggles, cash_control):
    """True when a denomination count is required for `move_type`.

    Every move type requires `cash_control` to be on. Cash-IN additionally
    requires `toggles.cash_in_enabled`, since a disabled cash-in toggle makes
    its count toggle moot.
    """
    if not cash_control:
        return False
    if move_type == "opening":
        return toggles.opening_required
    if move_type == "out":
        return toggles.out_required
    if move_type == "in":
        return toggles.in_required and toggles.cash_in_enabled
    if move_type == "closing":
        return toggles.closing_required
    return False
