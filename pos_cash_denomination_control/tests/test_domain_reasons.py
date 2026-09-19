"""Domain-unit tests for the pure cash-move reason validation rule.

Covers the pure-rule portion of spec `cash-move-reasons` (Requirement: Pure
Reason Validation Rule, and the `validate_reason_definition` defense-in-depth
note referenced in design.md ADR/Approach 6).
"""

from odoo.tests import BaseCase, tagged

from odoo.addons.pos_cash_denomination_control.domain.errors import ReasonError
from odoo.addons.pos_cash_denomination_control.domain.reasons import (
    ReasonSnapshot,
    is_direction_compatible,
    validate_reason,
    validate_reason_definition,
)


@tagged("at_install", "pcdc", "pcdc_domain")
class TestDomainReasons(BaseCase):
    def _reason(self, **overrides):
        values = dict(id=1, active=True, company_id=None, direction="out", is_vault=False)
        values.update(overrides)
        return ReasonSnapshot(**values)

    def test_missing_reason_is_rejected(self):
        with self.assertRaises(ReasonError) as ctx:
            validate_reason(None, "out", 1)
        self.assertEqual(ctx.exception.code, "MISSING")

    def test_inactive_reason_is_rejected(self):
        reason = self._reason(active=False)
        with self.assertRaises(ReasonError) as ctx:
            validate_reason(reason, "out", 1)
        self.assertEqual(ctx.exception.code, "INACTIVE")

    def test_other_company_reason_is_rejected(self):
        reason = self._reason(company_id=2)
        with self.assertRaises(ReasonError) as ctx:
            validate_reason(reason, "out", 1)
        self.assertEqual(ctx.exception.code, "WRONG_COMPANY")

    def test_shared_reason_is_accepted_across_companies(self):
        reason = self._reason(company_id=None)
        validate_reason(reason, "out", 1)
        validate_reason(reason, "out", 99)

    def test_out_move_accepts_out_or_both_direction_reasons(self):
        for direction in ("out", "both"):
            with self.subTest(direction=direction):
                reason = self._reason(direction=direction)
                validate_reason(reason, "out", 1)

    def test_in_move_accepts_in_or_both_direction_reasons(self):
        for direction in ("in", "both"):
            with self.subTest(direction=direction):
                reason = self._reason(direction=direction)
                validate_reason(reason, "in", 1)

    def test_out_move_rejects_an_in_direction_reason(self):
        reason = self._reason(direction="in")
        with self.assertRaises(ReasonError) as ctx:
            validate_reason(reason, "out", 1)
        self.assertEqual(ctx.exception.code, "DIRECTION_MISMATCH")

    def test_in_move_rejects_an_out_direction_reason(self):
        reason = self._reason(direction="out")
        with self.assertRaises(ReasonError) as ctx:
            validate_reason(reason, "in", 1)
        self.assertEqual(ctx.exception.code, "DIRECTION_MISMATCH")

    def test_vault_reason_is_rejected_for_an_in_move(self):
        reason = self._reason(direction="out", is_vault=True)
        with self.assertRaises(ReasonError) as ctx:
            validate_reason(reason, "in", 1)
        self.assertEqual(ctx.exception.code, "VAULT_NOT_OUT")

    def test_vault_reason_is_accepted_for_an_out_move(self):
        reason = self._reason(direction="out", is_vault=True)
        validate_reason(reason, "out", 1)

    def test_is_direction_compatible_matrix(self):
        self.assertTrue(is_direction_compatible("out", "out"))
        self.assertTrue(is_direction_compatible("both", "out"))
        self.assertTrue(is_direction_compatible("in", "in"))
        self.assertTrue(is_direction_compatible("both", "in"))
        self.assertFalse(is_direction_compatible("in", "out"))
        self.assertFalse(is_direction_compatible("out", "in"))

    def test_validate_reason_definition_rejects_vault_with_non_out_direction(self):
        with self.assertRaises(ReasonError) as ctx:
            validate_reason_definition("in", True)
        self.assertEqual(ctx.exception.code, "VAULT_NOT_OUT")
        with self.assertRaises(ReasonError):
            validate_reason_definition("both", True)

    def test_validate_reason_definition_accepts_vault_with_out_direction(self):
        validate_reason_definition("out", True)

    def test_validate_reason_definition_accepts_non_vault_with_any_direction(self):
        for direction in ("in", "out", "both"):
            with self.subTest(direction=direction):
                validate_reason_definition(direction, False)
