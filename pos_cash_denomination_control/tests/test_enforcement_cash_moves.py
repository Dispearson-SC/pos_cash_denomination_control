"""Denomination breakdown enforcement for `try_cash_in_out` (cash IN/OUT),
independent per direction.

Covers spec `cash-denomination-enforcement`, Requirement "Cash Move
Enforcement (IN/OUT), Independent Per Direction".
"""

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("pcdc", "pcdc_enforcement")
class TestEnforcementCashMoves(CommonPosTest):
    def setUp(self):
        super().setUp()
        self.pos_config_usd.allow_cash_in = True
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.set_opening_control(0, False)
        self.reason = self.env["pos.cash.move.reason"].create(
            {"name": "Test Reason", "direction": "both"}
        )
        self.bill_10 = self.env["pos.bill"].create({"name": "10", "value": 10.0})

    def _statement_line_count(self):
        return self.env["account.bank.statement.line"].search_count(
            [("pos_session_id", "=", self.session.id)]
        )

    def _extras(self, **extra):
        extras = {"translatedType": "Cash", "reason_id": self.reason.id}
        extras.update(extra)
        return extras

    def test_cash_out_with_valid_breakdown_is_accepted(self):
        """Cash out with valid breakdown is accepted."""
        self.pos_config_usd.cash_count_out_required = True
        before = self._statement_line_count()
        self.session.try_cash_in_out(
            "out",
            10,
            "Test",
            False,
            self._extras(
                denomination_lines=[{"bill_id": self.bill_10.id, "quantity": 1}]
            ),
        )
        self.assertEqual(self._statement_line_count(), before + 1)

    def test_cash_out_missing_breakdown_is_rejected_when_toggle_is_on(self):
        """Cash out missing breakdown is rejected when toggle is on."""
        self.pos_config_usd.cash_count_out_required = True
        before = self._statement_line_count()
        with self.assertRaises(UserError):
            self.session.try_cash_in_out("out", 10, "Test", False, self._extras())
        self.assertEqual(self._statement_line_count(), before)

    def test_cash_in_with_valid_breakdown_is_accepted(self):
        """Cash in with valid breakdown is accepted."""
        self.pos_config_usd.cash_count_in_required = True
        before = self._statement_line_count()
        self.session.try_cash_in_out(
            "in",
            10,
            "Test",
            False,
            self._extras(
                denomination_lines=[{"bill_id": self.bill_10.id, "quantity": 1}]
            ),
        )
        self.assertEqual(self._statement_line_count(), before + 1)

    def test_cash_in_toggle_does_not_affect_cash_out_enforcement(self):
        """Cash-IN toggle does not affect cash OUT enforcement: the OUT
        toggle (off here) governs OUT enforcement, not the IN toggle."""
        self.pos_config_usd.cash_count_in_required = True
        self.pos_config_usd.cash_count_out_required = False
        before = self._statement_line_count()
        self.session.try_cash_in_out("out", 10, "Test", False, self._extras())
        self.assertEqual(self._statement_line_count(), before + 1)

    def test_cash_move_breakdown_sum_mismatch_is_rejected(self):
        """Cash move breakdown sum mismatch is rejected."""
        self.pos_config_usd.cash_count_out_required = True
        with self.assertRaises(UserError):
            self.session.try_cash_in_out(
                "out",
                10,
                "Test",
                False,
                self._extras(
                    denomination_lines=[{"bill_id": self.bill_10.id, "quantity": 2}]
                ),
            )

    def test_cash_move_breakdown_with_disallowed_bill_is_rejected(self):
        """Cash move breakdown with disallowed bill is rejected."""
        self.pos_config_usd.cash_count_out_required = True
        with self.assertRaises(UserError):
            self.session.try_cash_in_out(
                "out",
                10,
                "Test",
                False,
                self._extras(
                    denomination_lines=[
                        {"bill_id": self.bill_10.id + 999999, "quantity": 1}
                    ]
                ),
            )

    def test_cash_move_breakdown_with_negative_or_non_integer_quantity_is_rejected(
        self,
    ):
        """Cash move breakdown with negative or non-integer quantity is
        rejected."""
        self.pos_config_usd.cash_count_out_required = True
        with self.assertRaises(UserError):
            self.session.try_cash_in_out(
                "out",
                10,
                "Test",
                False,
                self._extras(
                    denomination_lines=[{"bill_id": self.bill_10.id, "quantity": -1}]
                ),
            )
        with self.assertRaises(UserError):
            self.session.try_cash_in_out(
                "out",
                10,
                "Test",
                False,
                self._extras(
                    denomination_lines=[{"bill_id": self.bill_10.id, "quantity": 1.5}]
                ),
            )
