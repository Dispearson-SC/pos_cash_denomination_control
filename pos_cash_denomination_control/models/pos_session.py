"""`pos.session` extension: enforce the cash-in toggle before `super()`, load
the reason catalog to the frontend, and validate the cash-move reason.

Backs spec `cash-in-control`: `try_cash_in_out` must reject `_type == 'in'`
when the session's `pos.config.allow_cash_in` is `False`, before any
statement line is created, regardless of caller (POS UI, direct RPC, or an
offline-queued replay). This check is additive to the stock
`_has_cash_move_permission()` check performed by `super()`.

Backs spec `cash-move-reasons`: reasons load to the frontend the same way
`pos_hr` appends `hr.employee` (`_load_pos_data_models`, the `pos_hr` pattern
design.md's Verified Extension Points table cites); `try_cash_in_out` must
also validate `extras['reason_id']` before any statement line is created,
and `_prepare_account_bank_statement_line_vals` must compose the
`payment_ref` text from the reason's name (plus an optional note) and set
`cash_move_reason_id`.
"""

from odoo import api, models
from odoo.exceptions import AccessError
from odoo.tools.translate import _

from ..domain.cash_moves import validate_move_type
from ..domain.errors import MoveTypeError, ReasonError
from ..domain.reasons import validate_reason
from ..domain.text import compose_payment_text
from .domain_errors import raise_domain_error


class PosSession(models.Model):
    _inherit = "pos.session"

    @api.model
    def _load_pos_data_models(self, config):
        data = super()._load_pos_data_models(config)
        data.append("pos.cash.move.reason")
        return data

    def _pcdc_reason_record(self, extras):
        """Resolve `extras['reason_id']` to a `pos.cash.move.reason`
        record, raising `ReasonError("NOT_FOUND")` for an id that does not
        exist. Returns an empty recordset when no `reason_id` was given, so
        `domain.reasons.validate_reason` raises the "MISSING" error."""
        reason_id = extras.get("reason_id") if extras else None
        if not reason_id:
            return self.env["pos.cash.move.reason"]
        reason_record = self.env["pos.cash.move.reason"].sudo().browse(reason_id).exists()
        if not reason_record:
            raise ReasonError("NOT_FOUND")
        return reason_record

    def try_cash_in_out(self, _type, amount, reason, partner_id=False, extras=None):
        """Explicit guard-clause order, matching design.md's Server Flows
        "Cash IN/OUT" sequence: permission, move type, reason, [breakdown —
        Phase 9], then `super()` persists the statement line.

        Step 1 duplicates `super()`'s own `_has_cash_move_permission()`
        check (same message) so a caller without permission never reaches
        our reason lookup or validation; `super()` still re-checks it.
        """
        extras = extras or {}
        # 1. permission (super() re-checks; duplicated so our own checks
        #    below never run for a caller without cash-move permission)
        if not self.env.user._has_cash_move_permission():
            raise AccessError(
                _("You don't have the access rights to perform a cash in/out.")
            )
        try:
            reason_record = self._pcdc_reason_record(extras)
        except ReasonError as exc:
            raise_domain_error(exc)
        for session in self.filtered("cash_journal_id"):
            # 2. move type
            try:
                validate_move_type(_type, session.config_id.allow_cash_in)
            except MoveTypeError as exc:
                raise_domain_error(exc)
            # 3. reason
            snapshot = reason_record._to_domain_snapshot() if reason_record else None
            try:
                validate_reason(snapshot, _type, session.company_id.id)
            except ReasonError as exc:
                raise_domain_error(exc)
            # 4. breakdown — Phase 9 (denomination-enforcement) inserts its
            #    `domain.breakdown.validate_breakdown(...)` guard here.
        return super().try_cash_in_out(_type, amount, reason, partner_id, extras)

    def _prepare_account_bank_statement_line_vals(
        self, session, sign, amount, reason, partner_id, extras
    ):
        reason_id = extras.get("reason_id") if extras else None
        if not reason_id:
            # Only reachable by a caller other than `try_cash_in_out`,
            # which already rejects a missing `reason_id` before any
            # statement line is created.
            return super()._prepare_account_bank_statement_line_vals(
                session, sign, amount, reason, partner_id, extras
            )
        reason_record = self.env["pos.cash.move.reason"].sudo().browse(reason_id)
        text = compose_payment_text(reason_record.name, extras.get("note"))
        vals = super()._prepare_account_bank_statement_line_vals(
            session, sign, amount, text, partner_id, extras
        )
        vals["cash_move_reason_id"] = reason_record.id
        return vals
