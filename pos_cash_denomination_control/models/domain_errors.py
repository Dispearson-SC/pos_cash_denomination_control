"""Maps domain errors to translated, parameterized Odoo user-facing errors.

`domain/errors.py` only carries stable machine codes and raw parameters and
never imports `odoo`; this module is the one place in the addon that turns a
`DomainError` into an `_()` message, so translations live in the Odoo layer
only. Later phases extend `_MESSAGE_BUILDERS` for `BreakdownError` and
`ReasonError` as those enforcement paths are implemented.
"""

from odoo.exceptions import UserError
from odoo.tools.translate import _

from ..domain.errors import MoveTypeError


def _move_type_message(exc):
    if exc.code == "CASH_IN_DISABLED":
        return _("Cash-in operations are disabled for this point of sale.")
    if exc.code == "UNKNOWN_TYPE":
        return _(
            "Unknown cash-move type: %(move_type)s.",
            move_type=exc.params.get("move_type"),
        )
    return _("Cash-move type validation failed.")


_MESSAGE_BUILDERS = {
    MoveTypeError: _move_type_message,
}


def raise_domain_error(exc):
    """Translate `exc` (a `domain.errors.DomainError`) and raise it as a
    `UserError`, preserving the original exception as the cause."""
    for error_type, build_message in _MESSAGE_BUILDERS.items():
        if isinstance(exc, error_type):
            raise UserError(build_message(exc)) from exc
    raise UserError(str(exc)) from exc
