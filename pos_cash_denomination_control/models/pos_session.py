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

Backs spec `vault-withdrawal-alert` (Requirement: Server Method With Parity
To `get_closing_control_data`): `get_vault_withdrawal_state` reuses the same
`group_pos_user` access check and the same input collection as core's
`get_closing_control_data` (`point_of_sale/models/pos_session.py:778-810`),
then delegates the arithmetic to the pure `domain.cash_position` module. It
deliberately does NOT override `get_closing_control_data` itself (design.md
ADR-4): that method is also extended by `pos_hr`, and widening its blast
radius is unnecessary when a parity test can guard the two formulas instead.
"""

from odoo import api, models
from odoo.exceptions import AccessError
from odoo.tools.translate import _

from ..domain.cash_moves import validate_move_type
from ..domain.cash_position import compute_expected_cash, is_withdrawal_required
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

    def _pcdc_default_cash_payment_amounts(self):
        """Amounts of the default cash payment method's payments on this
        session's closed non-`pay_later` orders — the same "default cash
        payments" query `get_closing_control_data` runs at
        `point_of_sale/models/pos_session.py:782-787`. Private to
        `_pcdc_expected_cash_inputs`; not reused elsewhere."""
        self.ensure_one()
        orders = self._get_closed_orders()
        payments = orders.payment_ids.filtered(
            lambda p: p.payment_method_id.type != "pay_later"
        )
        cash_payment_method_ids = self.payment_method_ids.filtered(
            lambda pm: pm.type == "cash"
        )
        default_cash_payment_method_id = (
            cash_payment_method_ids[0] if cash_payment_method_ids else None
        )
        if not default_cash_payment_method_id:
            return []
        return payments.filtered(
            lambda p: p.payment_method_id == default_cash_payment_method_id
        ).mapped("amount")

    def _pcdc_expected_cash_inputs(self):
        """Collect the same inputs `get_closing_control_data` uses to
        compute `default_cash_details.amount`
        (`point_of_sale/models/pos_session.py:782-787,803`): the opening
        balance, the default cash payment method's amounts on closed
        non-`pay_later` orders, and the cash statement line amounts.

        Returns `(opening, cash_payment_amounts, statement_line_amounts)`,
        the positional inputs `domain.cash_position.compute_expected_cash`
        expects.
        """
        self.ensure_one()
        return (
            self.cash_register_balance_start,
            self._pcdc_default_cash_payment_amounts(),
            self.sudo().statement_line_ids.mapped("amount"),
        )

    def get_vault_withdrawal_state(self):
        """`{expected_cash, threshold, required}` for this session, using
        the same access check as `get_closing_control_data`. `required` is
        always `False` when cash control is off or the threshold is `0`."""
        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise AccessError(
                _(
                    "You don't have the access rights to get the point of "
                    "sale vault withdrawal state."
                )
            )
        self.ensure_one()
        config = self.config_id
        threshold = config.vault_withdrawal_threshold
        opening, cash_payment_amounts, statement_line_amounts = (
            self._pcdc_expected_cash_inputs()
        )
        expected_cash = compute_expected_cash(
            opening, cash_payment_amounts, statement_line_amounts
        )
        required = bool(config.cash_control) and is_withdrawal_required(
            expected_cash, threshold, config.currency_id.rounding
        )
        return {
            "expected_cash": expected_cash,
            "threshold": threshold,
            "required": required,
        }
