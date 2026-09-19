"""`pos.session` extension: enforce the cash-in toggle before `super()`.

Backs spec `cash-in-control`: `try_cash_in_out` must reject `_type == 'in'`
when the session's `pos.config.allow_cash_in` is `False`, before any
statement line is created, regardless of caller (POS UI, direct RPC, or an
offline-queued replay). This check is additive to the stock
`_has_cash_move_permission()` check performed by `super()`.
"""

from odoo import models

from ..domain.cash_moves import validate_move_type
from ..domain.errors import MoveTypeError
from .domain_errors import raise_domain_error


class PosSession(models.Model):
    _inherit = "pos.session"

    def try_cash_in_out(self, _type, amount, reason, partner_id=False, extras=None):
        for session in self:
            try:
                validate_move_type(_type, session.config_id.allow_cash_in)
            except MoveTypeError as exc:
                raise_domain_error(exc)
        return super().try_cash_in_out(_type, amount, reason, partner_id, extras)
