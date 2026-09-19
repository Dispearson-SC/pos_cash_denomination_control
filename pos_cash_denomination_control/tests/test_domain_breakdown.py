"""Domain-unit tests for denomination breakdown validation.

Covers spec `denomination-breakdown-domain`. Pure Python, no ORM: subclasses
`odoo.tests.BaseCase` so `--test-tags` picks it up, but uses no `env`.
"""

from odoo.tests import BaseCase, tagged

from odoo.addons.pos_cash_denomination_control.domain.breakdown import (
    compute_total,
    validate_breakdown,
)
from odoo.addons.pos_cash_denomination_control.domain.errors import BreakdownError


@tagged("at_install", "pcdc", "pcdc_domain")
class TestDomainBreakdown(BaseCase):
    def setUp(self):
        super().setUp()
        self.allowed_bills = {1: 100.0, 2: 50.0}

    def test_sum_of_multiple_denominations(self):
        lines = [{"bill_id": 1, "quantity": 3}, {"bill_id": 2, "quantity": 2}]
        breakdown = validate_breakdown(lines, 400, self.allowed_bills, 0.01, required=True)
        self.assertEqual(breakdown.total, 400)

    def test_empty_breakdown_yields_zero_total(self):
        self.assertEqual(compute_total(()), 0)

    def test_negative_quantity_is_rejected(self):
        lines = [{"bill_id": 1, "quantity": -1}]
        with self.assertRaises(BreakdownError) as ctx:
            validate_breakdown(lines, 0, self.allowed_bills, 0.01, required=True)
        self.assertEqual(ctx.exception.code, "NEGATIVE_QUANTITY")

    def test_non_integer_quantity_is_rejected(self):
        lines = [{"bill_id": 1, "quantity": 2.5}]
        with self.assertRaises(BreakdownError) as ctx:
            validate_breakdown(lines, 250, self.allowed_bills, 0.01, required=True)
        self.assertEqual(ctx.exception.code, "NON_INTEGER_QUANTITY")

    def test_zero_and_positive_integer_quantities_are_accepted(self):
        lines = [{"bill_id": 1, "quantity": 0}, {"bill_id": 2, "quantity": 5}]
        breakdown = validate_breakdown(lines, 250, self.allowed_bills, 0.01, required=True)
        self.assertEqual(breakdown.total, 250)
        # the zero-quantity line is dropped; only the bill_id=2 line remains
        self.assertEqual(len(breakdown.lines), 1)
        self.assertEqual(breakdown.lines[0].bill_id, 2)

    def test_disallowed_bill_is_rejected(self):
        lines = [{"bill_id": 99, "quantity": 1}]
        with self.assertRaises(BreakdownError) as ctx:
            validate_breakdown(lines, 0, self.allowed_bills, 0.01, required=True)
        self.assertEqual(ctx.exception.code, "BILL_NOT_ALLOWED")
        self.assertEqual(ctx.exception.params.get("bill_id"), 99)

    def test_allowed_bill_is_accepted(self):
        lines = [{"bill_id": 1, "quantity": 1}]
        breakdown = validate_breakdown(lines, 100, self.allowed_bills, 0.01, required=True)
        self.assertEqual(len(breakdown.lines), 1)
        self.assertEqual(breakdown.lines[0].bill_id, 1)

    def test_sum_matches_exactly(self):
        lines = [{"bill_id": 1, "quantity": 5}]
        breakdown = validate_breakdown(lines, 500.00, self.allowed_bills, 0.01, required=True)
        self.assertEqual(breakdown.total, 500.00)

    def test_sum_within_rounding_tolerance_is_accepted(self):
        allowed_bills = {1: 500.004}
        lines = [{"bill_id": 1, "quantity": 1}]
        breakdown = validate_breakdown(lines, 500.00, allowed_bills, 0.01, required=True)
        self.assertAlmostEqual(breakdown.total, 500.004)

    def test_sum_mismatch_beyond_rounding_is_rejected(self):
        allowed_bills = {1: 450.0}
        lines = [{"bill_id": 1, "quantity": 1}]
        with self.assertRaises(BreakdownError) as ctx:
            validate_breakdown(lines, 500.00, allowed_bills, 0.01, required=True)
        self.assertEqual(ctx.exception.code, "TOTAL_MISMATCH")

    def test_required_breakdown_missing_is_rejected(self):
        with self.assertRaises(BreakdownError) as ctx:
            validate_breakdown(None, 100, self.allowed_bills, 0.01, required=True)
        self.assertEqual(ctx.exception.code, "MISSING")

    def test_breakdown_not_required_and_absent_is_accepted(self):
        result = validate_breakdown(None, 100, self.allowed_bills, 0.01, required=False)
        self.assertIsNone(result)

    def test_breakdown_not_required_but_supplied_is_still_checked(self):
        allowed_bills = {1: 450.0}
        lines = [{"bill_id": 1, "quantity": 1}]
        with self.assertRaises(BreakdownError) as ctx:
            validate_breakdown(lines, 500.00, allowed_bills, 0.01, required=False)
        self.assertEqual(ctx.exception.code, "TOTAL_MISMATCH")
