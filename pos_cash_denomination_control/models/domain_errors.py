"""Maps domain errors to translated, parameterized Odoo user-facing errors.

`domain/errors.py` only carries stable machine codes and raw parameters and
never imports `odoo`; this module is the one place in the addon that turns a
`DomainError` into an `_()` message, so translations live in the Odoo layer
only. Later phases extend `_MESSAGE_BUILDERS` for `BreakdownError` and
`ReasonError` as those enforcement paths are implemented.
"""

from odoo.exceptions import UserError
from odoo.tools.translate import _

from ..domain.errors import MoveTypeError, ReasonError


def _move_type_message(exc):
    if exc.code == "CASH_IN_DISABLED":
        return _("Cash-in operations are disabled for this point of sale.")
    if exc.code == "UNKNOWN_TYPE":
        return _(
            "Unknown cash-move type: %(move_type)s.",
            move_type=exc.params.get("move_type"),
        )
    return _("Cash-move type validation failed.")


def _reason_message(exc):
    if exc.code == "MISSING":
        return _("A reason is required for this cash move.")
    if exc.code == "NOT_FOUND":
        return _("The selected cash-move reason does not exist.")
    if exc.code == "INACTIVE":
        return _("This cash-move reason is archived and cannot be used.")
    if exc.code == "WRONG_COMPANY":
        return _("This cash-move reason does not belong to this company.")
    if exc.code == "DIRECTION_MISMATCH":
        return _("This cash-move reason cannot be used for this move type.")
    if exc.code == "VAULT_NOT_OUT":
        return _("A vault reason can only be used for cash-out operations.")
    return _("Cash-move reason validation failed.")


_MESSAGE_BUILDERS = {
    MoveTypeError: _move_type_message,
    ReasonError: _reason_message,
}


def raise_domain_error(exc, exc_class=UserError):
    """Translate `exc` (a `domain.errors.DomainError`) and raise it as
    `exc_class` (`UserError` by default), preserving the original exception
    as the cause. Model-level `@api.constrains` callers pass
    `exc_class=ValidationError`, matching Odoo's convention that a record
    constraint raises `ValidationError` while an action-level rejection
    raises `UserError`."""
    for error_type, build_message in _MESSAGE_BUILDERS.items():
        if isinstance(exc, error_type):
            raise exc_class(build_message(exc)) from exc
    raise exc_class(str(exc)) from exc
