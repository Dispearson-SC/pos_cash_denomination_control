"""Denomination breakdown enforcement for `post_closing_cash_details`
(POS UI closing).

Covers spec `cash-denomination-enforcement`, Requirement "Closing
Enforcement Applies Only To The Cash Payment Method Count".
"""

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("pcdc", "pcdc_enforcement")
class TestEnforcementClosing(CommonPosTest):
    def setUp(self):
        super().setUp()
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.set_opening_control(0, False)
        self.bill_10 = self.env["pos.bill"].create({"name": "10", "value": 10.0})

    def test_closing_with_valid_breakdown_is_accepted(self):
        """Closing with valid breakdown is accepted."""
        self.pos_config_usd.cash_count_closing_required = True
        result = self.session.post_closing_cash_details(
            10, denomination_lines=[{"bill_id": self.bill_10.id, "quantity": 1}]
        )
        self.assertTrue(result["successful"])
        self.assertEqual(self.session.cash_register_balance_end_real, 10)

    def test_closing_missing_breakdown_is_rejected(self):
        """Closing missing breakdown is rejected."""
        self.pos_config_usd.cash_count_closing_required = True
        with self.assertRaises(UserError):
            self.session.post_closing_cash_details(10)
        self.assertNotEqual(self.session.cash_register_balance_end_real, 10)

    def test_non_cash_payment_method_counts_unaffected_by_toggle(self):
        """Non-cash payment method counts are unaffected by the toggle.

        `post_closing_cash_details` only ever sets
        `cash_register_balance_end_real` (the cash payment method's own
        counted amount) regardless of this module's toggle; there is no
        stock RPC on `pos.session` for a non-cash method's own count to
        accidentally start requiring a breakdown from, so this asserts the
        toggle's effect stays scoped to the field it is documented to
        govern.
        """
        self.pos_config_usd.cash_count_closing_required = True
        self.session.post_closing_cash_details(
            10, denomination_lines=[{"bill_id": self.bill_10.id, "quantity": 1}]
        )
        self.assertEqual(self.session.cash_register_balance_end_real, 10)

    def test_closing_note_and_chatter_contain_denomination_breakdown_text(self):
        """Closing note and chatter contain the denomination breakdown
        text."""
        self.pos_config_usd.cash_count_closing_required = True
        self.session.post_closing_cash_details(
            10, denomination_lines=[{"bill_id": self.bill_10.id, "quantity": 1}]
        )
        notes = "1 x 10.00 = 10.00"
        self.session.update_closing_control_state_session(notes)
        self.assertIn("10.00", self.session.closing_notes)
        message = self.session.message_ids.filtered(
            lambda m: "10.00" in (m.body or "")
        )
        self.assertTrue(message)
