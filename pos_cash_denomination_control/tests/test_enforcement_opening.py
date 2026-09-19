"""Denomination breakdown enforcement for `set_opening_control` /
`_set_opening_control_data`.

Covers spec `cash-denomination-enforcement`, Requirement "Opening
Enforcement".
"""

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("pcdc", "pcdc_enforcement")
class TestEnforcementOpening(CommonPosTest):
    def setUp(self):
        super().setUp()
        self.bill_10 = self.env["pos.bill"].create({"name": "10", "value": 10.0})
        self.bill_20 = self.env["pos.bill"].create({"name": "20", "value": 20.0})

    def _open_session(self):
        self.pos_config_usd.open_ui()
        return self.pos_config_usd.current_session_id

    def test_opening_with_valid_breakdown_is_accepted(self):
        """Opening with valid breakdown is accepted."""
        self.pos_config_usd.cash_count_opening_required = True
        session = self._open_session()
        session.set_opening_control(
            40,
            False,
            denomination_lines=[{"bill_id": self.bill_20.id, "quantity": 2}],
        )
        self.assertEqual(session.cash_register_balance_start, 40)

    def test_opening_missing_breakdown_is_rejected(self):
        """Opening missing breakdown is rejected."""
        self.pos_config_usd.cash_count_opening_required = True
        session = self._open_session()
        with self.assertRaises(UserError):
            session.set_opening_control(40, False)
        self.assertNotEqual(session.cash_register_balance_start, 40)

    def test_opening_breakdown_sum_mismatch_is_rejected(self):
        """Opening breakdown sum mismatch is rejected."""
        self.pos_config_usd.cash_count_opening_required = True
        session = self._open_session()
        with self.assertRaises(UserError):
            session.set_opening_control(
                40,
                False,
                denomination_lines=[{"bill_id": self.bill_10.id, "quantity": 1}],
            )

    def test_opening_breakdown_with_disallowed_bill_is_rejected(self):
        """Opening breakdown with disallowed bill is rejected."""
        self.pos_config_usd.cash_count_opening_required = True
        session = self._open_session()
        with self.assertRaises(UserError):
            session.set_opening_control(
                40,
                False,
                denomination_lines=[
                    {"bill_id": self.bill_20.id + 999999, "quantity": 2}
                ],
            )

    def test_opening_breakdown_with_negative_quantity_is_rejected(self):
        """Opening breakdown with negative quantity is rejected."""
        self.pos_config_usd.cash_count_opening_required = True
        session = self._open_session()
        with self.assertRaises(UserError):
            session.set_opening_control(
                -20,
                False,
                denomination_lines=[{"bill_id": self.bill_20.id, "quantity": -1}],
            )

    def test_opening_breakdown_with_non_integer_quantity_is_rejected(self):
        """Opening breakdown with non-integer quantity is rejected."""
        self.pos_config_usd.cash_count_opening_required = True
        session = self._open_session()
        with self.assertRaises(UserError):
            session.set_opening_control(
                21,
                False,
                denomination_lines=[{"bill_id": self.bill_20.id, "quantity": 1.5}],
            )

    def test_opening_toggle_off_skips_breakdown_validation(self):
        """Opening toggle off skips breakdown validation."""
        self.pos_config_usd.cash_count_opening_required = False
        session = self._open_session()
        session.set_opening_control(0, False)
        self.assertEqual(session.state, "opened")

    def test_opening_note_contains_denomination_breakdown_text(self):
        """Opening note contains the denomination breakdown text."""
        self.pos_config_usd.cash_count_opening_required = True
        session = self._open_session()
        session.set_opening_control(
            40,
            "2 x 20.00 = 40.00",
            denomination_lines=[{"bill_id": self.bill_20.id, "quantity": 2}],
        )
        self.assertIn("20.00", session.opening_notes)
