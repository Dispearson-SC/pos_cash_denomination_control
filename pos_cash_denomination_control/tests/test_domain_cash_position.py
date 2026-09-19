"""Domain-unit tests for expected-cash computation and the vault threshold
decision rule.

Covers spec `vault-withdrawal-alert` (Requirement: Expected Cash Computation,
Requirement: Withdrawal-Required Decision Rule).
"""

from odoo.tests import BaseCase, tagged

from odoo.addons.pos_cash_denomination_control.domain.cash_position import (
    compute_expected_cash,
    is_withdrawal_required,
)


@tagged("at_install", "pcdc", "pcdc_domain")
class TestDomainCashPosition(BaseCase):
    def test_expected_cash_computed_with_orders_and_cash_moves(self):
        result = compute_expected_cash(200, [500], [-100])
        self.assertEqual(result, 600)

    def test_expected_cash_with_no_orders_equals_the_opening_balance(self):
        result = compute_expected_cash(200, [], [])
        self.assertEqual(result, 200)

    def test_threshold_zero_never_requires_withdrawal(self):
        self.assertFalse(is_withdrawal_required(1_000_000, 0, 0.01))
        self.assertFalse(is_withdrawal_required(0, 0, 0.01))

    def test_expected_cash_exactly_equal_to_a_positive_threshold_requires_withdrawal(self):
        self.assertTrue(is_withdrawal_required(1000, 1000, 0.01))

    def test_expected_cash_just_below_threshold_within_rounding_tolerance_requires_withdrawal(
        self,
    ):
        self.assertTrue(is_withdrawal_required(999.996, 1000.00, 0.01))

    def test_expected_cash_below_threshold_does_not_require_withdrawal(self):
        self.assertFalse(is_withdrawal_required(900, 1000, 0.01))

    def test_expected_cash_above_threshold_requires_withdrawal(self):
        self.assertTrue(is_withdrawal_required(1500, 1000, 0.01))
