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

Backs spec `cash-count-records` (Requirement: Employee Attribution Without
Hard `pos_hr` Dependency): `_pcdc_resolve_employee` implements design.md's
ADR-8 soft reference — an employee id plus a name snapshot, with no hard
`hr`/`pos_hr` dependency. Cash moves read `extras['employee_id']` (the key
`pos_hr`'s own `CashMovePopup` patch injects); opening/closing read
`session.employee_id`, only when `'employee_id' in session._fields` (i.e.
only when `pos_hr` actually added that field). The name is resolved only
when `'hr.employee' in self.env`, since referential integrity for cash
moves already exists on `account.bank.statement.line.employee_id`
(`pos_hr/models/account_bank_statement.py`).

Backs spec `cash-denomination-enforcement`: `set_opening_control`,
`try_cash_in_out`, and `post_closing_cash_details` each require a
denomination breakdown whenever their matching `pos.config` toggle is on,
via `domain.breakdown.validate_breakdown`, and persist an accepted
breakdown through `_pcdc_create_count`. `_pcdc_validate_and_maybe_persist`
is the one place that resolves toggles/allowed-bills/rounding fresh from
`self.config_id` on every call (spec Requirement: Offline Replay Safety —
no caching, so a queued RPC is validated against the server's state *at
replay time*).

Backs spec `closing-manager-override`: `_validate_session` (the single
writer of `state='closed'`, `point_of_sale/models/pos_session.py:482`) is
overridden as a guard that every public close path reaches — the
back-office button, the force-close/imbalance wizard
(`wizard/pos_close_session_wizard.py`), and direct RPC calls to
`action_pos_session_validate`/`action_pos_session_close`. With the closing
toggle on, a session with no valid closing count can close only for a POS
manager (`domain.closing.evaluate_closing`); a non-manager gets
`UserError` before `super()` runs (design.md ADR-9). A manager is instead
flagged (`closed_without_denomination_count` + user/date, plus a chatter
message), written only once `super()` reports `self.state == 'closed'` so
an imbalance-wizard redirect is never flagged. The guard reads
`self.env.user` — the real acting user — entirely before `super()`'s own
internal `sudo()` escalation for `group_pos_user` callers
(`point_of_sale/models/pos_session.py:427-428`), so that unrelated
internal sudo() writes can never mask the acting user's actual group
membership.

`set_opening_control(cashbox_value, notes, denomination_lines=None)`
follows design.md ADR-1: the public method only stashes `denomination_lines`
into context and delegates to `super()` unmodified — core's own docstring
says "DO NOT INHERIT THIS METHOD. Inherit `_set_opening_control_data`
instead", and `pos_hr` overrides `_set_opening_control_data` with a fixed
`(self, cashbox_value: int, notes: str)` signature
(`pos_hr/models/pos_session.py:23`), so adding a positional/keyword
argument anywhere in that override chain risks a `TypeError` depending on
MRO order. Threading the value through `self.env.context` sidesteps that
entirely: every override in the chain keeps calling `super()` with the
original two-argument signature.
"""

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

from ..domain.breakdown import validate_breakdown
from ..domain.cash_moves import CountToggles, count_required, validate_move_type
from ..domain.cash_position import compute_expected_cash, is_withdrawal_required
from ..domain.closing import ClosingDecision, evaluate_closing
from ..domain.errors import BreakdownError, MoveTypeError, ReasonError
from ..domain.money import compare_amounts
from ..domain.reasons import validate_reason
from ..domain.text import compose_payment_text
from .domain_errors import raise_domain_error


def _pcdc_freeze_lines(raw):
    """Turn a list of `{"bill_id", "quantity"}` dicts into a tuple of
    `(bill_id, quantity)` pairs, so the value is safe to carry on
    `self.env.context` (design.md ADR-1 / Server Flows "Opening")."""
    if raw is None:
        return None
    return tuple((entry.get("bill_id"), entry.get("quantity")) for entry in raw)


def _pcdc_thaw_lines(frozen):
    """Inverse of `_pcdc_freeze_lines`."""
    if frozen is None:
        return None
    return [{"bill_id": bill_id, "quantity": quantity} for bill_id, quantity in frozen]


class PosSession(models.Model):
    _inherit = "pos.session"

    closed_without_denomination_count = fields.Boolean(
        readonly=True,
        copy=False,
        index=True,
        help="Set when a POS manager closed this session without a "
        "recorded closing denomination count (spec "
        "`closing-manager-override`).",
    )
    closed_without_denomination_count_user_id = fields.Many2one(
        "res.users",
        readonly=True,
        help="The manager who closed this session without a recorded "
        "closing denomination count.",
    )
    closed_without_denomination_count_date = fields.Datetime(readonly=True)
    cash_count_ids = fields.One2many("pos.cash.denomination.count", "session_id")

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
        "Cash IN/OUT" sequence: permission, move type, reason, breakdown,
        then `super()` persists the statement line.

        Step 1 duplicates `super()`'s own `_has_cash_move_permission()`
        check (same message) so a caller without permission never reaches
        our reason lookup or validation; `super()` still re-checks it.

        Step 4 creates the count header (when a breakdown is required or
        supplied) *before* calling `super()`, so its id can travel through
        `self.env.context['pcdc_count_by_session']` into
        `_prepare_account_bank_statement_line_vals`, which sets
        `pos_cash_count_id` on the just-created statement line.
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
        count_by_session = {}
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
            # 4. breakdown
            _bd, _bills, header = session._pcdc_validate_and_maybe_persist(
                _type,
                extras.get("denomination_lines"),
                amount,
                reason=reason_record or None,
                note=extras.get("note"),
                extras=extras,
            )
            if header:
                count_by_session[session.id] = header.id
        self = self.with_context(pcdc_count_by_session=count_by_session)
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
        count_id = self.env.context.get("pcdc_count_by_session", {}).get(session.id)
        if count_id:
            vals["pos_cash_count_id"] = count_id
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

    def _pcdc_resolve_employee(self, move_type, extras=None):
        """`(employee_id, employee_name)` for a count header, per
        design.md ADR-8. Cash moves (`in`/`out`) read
        `extras['employee_id']`; opening/closing read `session.employee_id`
        only when that field exists on this session (`pos_hr` installed).
        The name is resolved only when `hr.employee` is a registered
        model."""
        self.ensure_one()
        if move_type in ("in", "out"):
            employee_id = (extras or {}).get("employee_id") or None
        elif "employee_id" in self._fields and self.employee_id:
            employee_id = self.employee_id.id
        else:
            employee_id = None

        employee_name = False
        if employee_id and "hr.employee" in self.env:
            employee = self.env["hr.employee"].sudo().browse(employee_id).exists()
            employee_name = employee.name if employee else False

        return employee_id, employee_name

    def _pcdc_create_count(
        self,
        move_type,
        breakdown,
        bills,
        reason=None,
        note=None,
        statement_line=None,
        extras=None,
    ):
        """Create one `pos.cash.denomination.count` header plus its lines
        for `breakdown` (a `domain.breakdown.Breakdown`), the single header
        + lines creation path shared by every enforcement site: Phase 9's
        `_set_opening_control_data`/`try_cash_in_out`/
        `post_closing_cash_details`, and Phase 10's closing override.

        `bills` is the `pos.bill` recordset `breakdown`'s lines were
        validated against (`domain.breakdown.validate_breakdown`'s
        `allowed_bills`), used only to snapshot each line's `bill_name`.

        Runs in `sudo()`: the header and line models grant no create
        access to any group (design.md Data Model: "All writes go through
        adapter code in sudo()")."""
        self.ensure_one()
        employee_id, employee_name = self._pcdc_resolve_employee(move_type, extras)
        header = self.env["pos.cash.denomination.count"].sudo().create(
            {
                "session_id": self.id,
                "move_type": move_type,
                "total": breakdown.total,
                "user_id": self.env.user.id,
                "employee_ref": employee_id or False,
                "employee_name": employee_name,
                "reason_id": reason.id if reason else False,
                "note": note,
                "statement_line_ids": (
                    [(6, 0, statement_line.ids)] if statement_line else False
                ),
            }
        )
        bills_by_id = {bill.id: bill for bill in bills}
        self.env["pos.cash.denomination.count.line"].sudo().create(
            [
                {
                    "count_id": header.id,
                    "bill_id": line.bill_id,
                    "bill_name": bills_by_id[line.bill_id].name
                    if line.bill_id in bills_by_id
                    else False,
                    "bill_value": line.bill_value,
                    "quantity": line.quantity,
                }
                for line in breakdown.lines
            ]
        )
        return header

    def _pcdc_count_toggles(self, config):
        """Snapshot the four `cash_count_*_required` toggles plus
        `allow_cash_in` into a `domain.cash_moves.CountToggles`."""
        return CountToggles(
            cash_in_enabled=config.allow_cash_in,
            opening_required=config.cash_count_opening_required,
            out_required=config.cash_count_out_required,
            in_required=config.cash_count_in_required,
            closing_required=config.cash_count_closing_required,
        )

    def _pcdc_allowed_bills(self, config):
        """The `pos.bill` recordset allowed for `config`, using the exact
        same domain the POS frontend loads (`pos.bill._load_pos_data_domain`)
        — reused so server-side validation always matches what the POS
        offered the cashier, including any third-party override of that
        domain."""
        Bill = self.env["pos.bill"]
        return Bill.search(Bill._load_pos_data_domain({}, config))

    def _pcdc_validate_and_maybe_persist(
        self, move_type, raw_lines, amount, persist=True, **attribution
    ):
        """Validate `raw_lines` for `move_type` against `amount` on `self`
        (one session), and — when `persist` is `True` (the default) and a
        breakdown was supplied — immediately create the count header+lines
        via `_pcdc_create_count(move_type, breakdown, bills, **attribution)`.

        Toggles, allowed bills, and currency rounding are resolved fresh
        from `self.config_id` on *every* call (spec
        `cash-denomination-enforcement`, Requirement: Offline Replay
        Safety) — nothing here is cached across requests, so a
        replayed/queued RPC is always validated against the server's
        current configuration.

        `try_cash_in_out` uses the `persist=True` default: it needs the
        header immediately, to thread its id through context into
        `_prepare_account_bank_statement_line_vals`.
        `_set_opening_control_data` and `post_closing_cash_details` pass
        `persist=False`: they must call `super()` first and persist the
        count only once `super()` actually succeeds (design.md's Opening
        and Closing Server Flows), so they call `_pcdc_create_count`
        themselves afterward using the returned `(breakdown, bills)`.

        Returns `(breakdown_or_none, allowed_bills_recordset, header_or_none)`.
        """
        self.ensure_one()
        config = self.config_id
        toggles = self._pcdc_count_toggles(config)
        required = count_required(move_type, toggles, config.cash_control)
        bills = self._pcdc_allowed_bills(config)
        allowed_bills = {bill.id: bill.value for bill in bills}
        try:
            bd = validate_breakdown(
                raw_lines, amount, allowed_bills, config.currency_id.rounding, required
            )
        except BreakdownError as exc:
            raise_domain_error(exc)
        header = None
        if bd and persist:
            header = self._pcdc_create_count(move_type, bd, bills, **attribution)
        return bd, bills, header

    def set_opening_control(self, cashbox_value, notes, denomination_lines=None):
        """Additive kwarg (ADR-1): only stashes `denomination_lines` into
        context and delegates to `super()` unmodified. All breakdown
        validation and persistence lives in `_set_opening_control_data`
        instead, which reads the context value back — DO NOT add business
        logic to this method; extend `_set_opening_control_data`.
        """
        self = self.with_context(
            pcdc_opening_lines=_pcdc_freeze_lines(denomination_lines)
        )
        return super().set_opening_control(cashbox_value, notes)

    def _set_opening_control_data(self, cashbox_value, notes):
        self.ensure_one()
        raw_lines = _pcdc_thaw_lines(self.env.context.get("pcdc_opening_lines"))
        bd, bills, _header = self._pcdc_validate_and_maybe_persist(
            "opening", raw_lines, cashbox_value, persist=False
        )
        super()._set_opening_control_data(cashbox_value, notes)
        if bd:
            self._pcdc_create_count("opening", bd, bills, note=notes)

    def post_closing_cash_details(self, counted_cash, denomination_lines=None):
        """Additive kwarg. Unlike `set_opening_control`
        (`_set_opening_control_data` has a fixed-signature override in
        `pos_hr`), no other module in this addon's dependency chain
        overrides `post_closing_cash_details`, so the kwarg is added
        directly here — no context indirection needed.

        Validates before `super()` (a rejected breakdown leaves
        `cash_register_balance_end_real` untouched); persists the closing
        header only when `super()` reports `successful`, so a closing
        blocked by open draft orders (`_cannot_close_session`, which
        returns a dict instead of raising) never leaves a stray header for
        an amount that was never actually recorded. Any previous closing
        header for this session is unlinked first, so retrying an initial
        rejected/blocked closing does not accumulate duplicates."""
        self.ensure_one()
        bd, bills, _header = self._pcdc_validate_and_maybe_persist(
            "closing", denomination_lines, counted_cash, persist=False
        )
        result = super().post_closing_cash_details(counted_cash)
        if bd and result.get("successful"):
            self.env["pos.cash.denomination.count"].sudo().search(
                [("session_id", "=", self.id), ("move_type", "=", "closing")]
            ).unlink()
            self._pcdc_create_count("closing", bd, bills)
        return result

    def _pcdc_has_valid_closing_count(self):
        """`True` when the latest `closing`-type
        `pos.cash.denomination.count` header for this session has a
        `total` matching `cash_register_balance_end_real`, within
        currency rounding (design.md's Back-office close guard: `has_valid`).

        A back-office edit of the counted cash after a POS-recorded count,
        or a rescue session (whose balance is overwritten by
        `action_pos_session_closing_control`), both invalidate a
        previously-recorded count, exactly as design.md documents."""
        self.ensure_one()
        header = (
            self.env["pos.cash.denomination.count"]
            .sudo()
            .search(
                [("session_id", "=", self.id), ("move_type", "=", "closing")],
                order="date desc, id desc",
                limit=1,
            )
        )
        if not header:
            return False
        return (
            compare_amounts(
                header.total,
                self.cash_register_balance_end_real,
                self.currency_id.rounding,
            )
            == 0
        )

    def _validate_session(
        self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None
    ):
        """Closing-manager-override guard (design.md's Back-office close
        guard, spec `closing-manager-override`). See this class's
        docstring for the full rationale; in short: this override runs
        entirely before `super()`, so `self.env.user.has_group(...)` below
        always reads the real acting user's own groups, never an
        escalated `sudo()` context `super()` may switch to internally.
        """
        self.ensure_one()
        config = self.config_id
        required = bool(config.cash_control) and bool(config.cash_count_closing_required)
        has_valid = self._pcdc_has_valid_closing_count()
        is_manager = self.env.user.has_group("point_of_sale.group_pos_manager")
        decision = evaluate_closing(required, has_valid, is_manager)
        if decision == ClosingDecision.REJECTED:
            raise UserError(
                _(
                    "Only a point of sale manager can close this session "
                    "without a recorded closing denomination count."
                )
            )
        result = super()._validate_session(
            balancing_account, amount_to_balance, bank_payment_method_diffs
        )
        # Not flagged when `super()` returned the imbalance/force-close
        # wizard action instead of actually closing the session.
        if decision == ClosingDecision.ALLOWED_FLAGGED and self.state == "closed":
            self.sudo().write(
                {
                    "closed_without_denomination_count": True,
                    "closed_without_denomination_count_user_id": self.env.user.id,
                    "closed_without_denomination_count_date": fields.Datetime.now(),
                }
            )
            self.message_post(
                body=_(
                    "Session closed without a recorded closing "
                    "denomination count by %(user)s (manager override).",
                    user=self.env.user.name,
                )
            )
        return result
