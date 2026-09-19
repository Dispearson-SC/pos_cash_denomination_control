"""End-to-end browser tours (Phase 13, spec `pos-denomination-ui`
Requirement "End-To-End Flows Are Verified By Tours", plus tour-level
scenarios from `cash-in-control`, `closing-manager-override`, and
`vault-withdrawal-alert`).

Mirrors how `pos_hr` hosts its own tours: a `TestPointOfSaleHttpCommon`
subclass adds this addon's own fixtures (bills, reasons, a product), and
each test method configures only the toggle(s) its own tour exercises
before calling `start_pos_tour`.
"""

from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged("post_install", "-at_install", "pcdc_tours")
class TestPcdcHttpCommon(TestPointOfSaleHttpCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Deliberately NOT restricted via `default_bill_ids`: `pos.bill`'s
        # own `_load_pos_data_domain` allows a bill when it is in the
        # config's `default_bill_ids` OR it carries no `pos_config_ids` at
        # all (empirically confirmed) — a bill created with no
        # `pos_config_ids` (the default here) is therefore always globally
        # allowed for every config regardless of `default_bill_ids`, same
        # as the core seed bills. Every tour instead targets this specific
        # bill's row via its `name` ("20", `data-bill-name` in
        # `denomination_breakdown_popup.xml`), which also works regardless
        # of how many other (seed) bills the popup also lists.
        cls.pcdc_bill_20 = cls.env["pos.bill"].create({"name": "20", "value": 20.0})
        cls.pcdc_reason_bank_deposit = cls.env["pos.cash.move.reason"].create(
            {"name": "Bank Deposit", "direction": "out"}
        )
        cls.pcdc_reason_in = cls.env["pos.cash.move.reason"].create(
            {"name": "Petty cash top-up", "direction": "in"}
        )
        cls.pcdc_vault_product = cls.env["product.template"].create(
            {
                "name": "PCDC Vault Product",
                "available_in_pos": True,
                "list_price": 80.0,
                "taxes_id": False,
            }
        )

    def _last_session(self, state=None):
        """The most recent session for `main_pos_config`, optionally
        filtered by `state`. A closing tour's own post-close page reload
        makes the POS controller auto-open a fresh (`opening_control`)
        session for the next visit, so a closing test must filter by
        `state="closed"` rather than trusting "most recent" alone."""
        domain = [("config_id", "=", self.main_pos_config.id)]
        if state:
            domain.append(("state", "=", state))
        return self.env["pos.session"].search(domain, order="id desc", limit=1)

    def test_opening_breakdown_tour(self):
        """`pos-denomination-ui` spec: "Opening tour with a breakdown
        succeeds"."""
        self.main_pos_config.write({"cash_count_opening_required": True})
        self.start_pos_tour("pcdc_opening_breakdown_tour")
        session = self._last_session()
        self.assertEqual(session.state, "opened")
        self.assertEqual(session.cash_register_balance_start, 40.0)
        count = self.env["pos.cash.denomination.count"].sudo().search(
            [("session_id", "=", session.id), ("move_type", "=", "opening")]
        )
        self.assertEqual(len(count), 1)
        self.assertEqual(count.total, 40.0)
        self.assertEqual(count.line_ids.quantity, 2)

    def test_cash_out_reason_breakdown_tour(self):
        """`pos-denomination-ui` spec: "Cash-out tour with reason and
        breakdown succeeds". Logs in as `pos_admin`: the "Cash In/Out" menu
        option requires `_has_cash_move_permission()`
        (`group_pos_manager` or `account.group_account_invoice`), which
        the plain `pos_user` fixture does not have."""
        self.main_pos_config.write({"cash_count_out_required": True})
        self.start_pos_tour("pcdc_cash_out_reason_tour", login="pos_admin")
        session = self._last_session()
        line = session.statement_line_ids.filtered(lambda l: l.amount < 0)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.amount, -20.0)
        self.assertEqual(line.cash_move_reason_id, self.pcdc_reason_bank_deposit)
        count = self.env["pos.cash.denomination.count"].sudo().search(
            [("session_id", "=", session.id), ("move_type", "=", "out")]
        )
        self.assertEqual(len(count), 1)
        self.assertEqual(count.total, 20.0)

    def test_closing_breakdown_tour(self):
        """`pos-denomination-ui` spec: "Closing tour with a breakdown
        succeeds" + `closing-manager-override` spec: "Non-manager closing
        with a recorded breakdown succeeds (tour)"."""
        self.main_pos_config.write({"cash_count_closing_required": True})
        self.start_pos_tour("pcdc_closing_breakdown_tour")
        session = self._last_session(state="closed")
        self.assertEqual(session.state, "closed")
        self.assertFalse(session.closed_without_denomination_count)
        count = self.env["pos.cash.denomination.count"].sudo().search(
            [("session_id", "=", session.id), ("move_type", "=", "closing")]
        )
        self.assertEqual(len(count), 1)
        self.assertEqual(count.total, 20.0)

    def test_cash_in_disabled_tour(self):
        """`cash-in-control` spec, tour-level proof (design.md Testing
        Strategy Tours row "cash-in disabled"). See
        `test_cash_out_reason_breakdown_tour` for why `pos_admin`."""
        self.assertFalse(self.main_pos_config.allow_cash_in)
        self.start_pos_tour("pcdc_cash_in_disabled_tour", login="pos_admin")
        session = self._last_session()
        self.assertFalse(session.statement_line_ids)

    def test_rejection_tour(self):
        """Tour-level rejection UX (design.md Testing Strategy Tours row
        "reason and denomination rejection"). The tour deliberately
        triggers a server-side `UserError` (the whole point of the
        scenario); Odoo's default `browser_js` behavior fails a test on
        ANY browser `console.error`, including the expected `RPC_ERROR`
        the framework itself logs when relaying that error to the dialog
        service, so an `error_checker` is required to not fail on it while
        still failing on any other, unexpected console error."""
        self.main_pos_config.write(
            {"allow_cash_in": True, "cash_count_out_required": True}
        )
        self.start_pos_tour(
            "pcdc_rejection_tour",
            login="pos_admin",
            error_checker=lambda message: "RPC_ERROR" not in message,
        )
        session = self._last_session()
        # Neither the discarded cash-in nor the server-rejected cash-out
        # ever created a statement line.
        self.assertFalse(session.statement_line_ids)

    def test_vault_alert_tour(self):
        """`vault-withdrawal-alert` spec, tour-level scenarios. Logs in as
        `pos_admin`: the one-click cash-out also requires
        `showCashMoveButton` (see `test_cash_out_reason_breakdown_tour`)."""
        self.main_pos_config.write({"vault_withdrawal_threshold": 150.0})
        self.start_pos_tour("pcdc_vault_alert_tour", login="pos_admin")
        session = self._last_session()
        state = session.get_vault_withdrawal_state()
        self.assertFalse(state["required"])
        self.assertEqual(state["expected_cash"], 140.0)

    def test_offline_queue_is_memory_only(self):
        """Not a spec scenario: confirms/refutes design.md's Discovery
        table claim that the offline replay queue is memory-only. See
        `offline_queue_tour.js` for the full rationale. Logs in as
        `pos_admin`: the "Cash In/Out" menu option requires
        `showCashMoveButton` (see `test_cash_out_reason_breakdown_tour`)."""
        self.start_pos_tour("pcdc_offline_queue_tour", login="pos_admin")
        session = self._last_session()
        self.assertFalse(
            session.statement_line_ids,
            "The queued cash-out was lost on reload and never replayed, "
            "confirming the offline queue is memory-only.",
        )
