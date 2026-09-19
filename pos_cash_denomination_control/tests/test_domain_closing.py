"""Domain-unit tests for the closing decision table.

Covers design.md's Testing Strategy row "closing decision table", the pure
core of spec `closing-manager-override`.
"""

from odoo.tests import BaseCase, tagged

from odoo.addons.pos_cash_denomination_control.domain.closing import (
    ClosingDecision,
    evaluate_closing,
)


@tagged("at_install", "pcdc", "pcdc_domain")
class TestDomainClosing(BaseCase):
    def _expected(self, required, has_valid, is_manager):
        if not required or has_valid:
            return ClosingDecision.ALLOWED
        if is_manager:
            return ClosingDecision.ALLOWED_FLAGGED
        return ClosingDecision.REJECTED

    def test_closing_decision_table_every_combination(self):
        for required in (False, True):
            for has_valid in (False, True):
                for is_manager in (False, True):
                    with self.subTest(
                        required=required, has_valid=has_valid, is_manager=is_manager
                    ):
                        expected = self._expected(required, has_valid, is_manager)
                        result = evaluate_closing(required, has_valid, is_manager)
                        self.assertEqual(result, expected)

    def test_not_required_is_always_allowed(self):
        self.assertEqual(
            evaluate_closing(False, has_valid_count=False, is_manager=False),
            ClosingDecision.ALLOWED,
        )

    def test_required_with_valid_count_is_allowed(self):
        self.assertEqual(
            evaluate_closing(True, has_valid_count=True, is_manager=False),
            ClosingDecision.ALLOWED,
        )

    def test_required_without_valid_count_manager_is_flagged(self):
        self.assertEqual(
            evaluate_closing(True, has_valid_count=False, is_manager=True),
            ClosingDecision.ALLOWED_FLAGGED,
        )

    def test_required_without_valid_count_non_manager_is_rejected(self):
        self.assertEqual(
            evaluate_closing(True, has_valid_count=False, is_manager=False),
            ClosingDecision.REJECTED,
        )
