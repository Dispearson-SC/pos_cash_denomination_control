"""Domain-unit tests for the move-type rule and `count_required`.

Covers design.md's Testing Strategy row "move type" and the pure-rule portion
of spec `cash-in-control` (move-type validation feeding `try_cash_in_out`).
"""

from odoo.tests import BaseCase, tagged

from odoo.addons.pos_cash_denomination_control.domain.cash_moves import (
    CountToggles,
    count_required,
    validate_move_type,
)
from odoo.addons.pos_cash_denomination_control.domain.errors import MoveTypeError


@tagged("at_install", "pcdc", "pcdc_domain")
class TestDomainCashMoves(BaseCase):
    def test_unknown_type_is_rejected(self):
        with self.assertRaises(MoveTypeError) as ctx:
            validate_move_type("sideways", cash_in_enabled=True)
        self.assertEqual(ctx.exception.code, "UNKNOWN_TYPE")

    def test_cash_in_disabled_is_rejected(self):
        with self.assertRaises(MoveTypeError) as ctx:
            validate_move_type("in", cash_in_enabled=False)
        self.assertEqual(ctx.exception.code, "CASH_IN_DISABLED")

    def test_cash_in_allowed_when_enabled(self):
        validate_move_type("in", cash_in_enabled=True)  # no exception

    def test_cash_out_never_blocked_by_cash_in_toggle(self):
        validate_move_type("out", cash_in_enabled=False)  # no exception

    def test_count_required_false_when_cash_control_off(self):
        toggles = CountToggles(
            cash_in_enabled=True,
            opening_required=True,
            out_required=True,
            in_required=True,
            closing_required=True,
        )
        for move_type in ("opening", "out", "in", "closing"):
            with self.subTest(move_type=move_type):
                self.assertFalse(count_required(move_type, toggles, cash_control=False))

    def test_count_required_true_only_for_the_matching_toggle(self):
        toggles = CountToggles(
            cash_in_enabled=True,
            opening_required=True,
            out_required=False,
            in_required=True,
            closing_required=False,
        )
        self.assertTrue(count_required("opening", toggles, cash_control=True))
        self.assertFalse(count_required("out", toggles, cash_control=True))
        self.assertTrue(count_required("in", toggles, cash_control=True))
        self.assertFalse(count_required("closing", toggles, cash_control=True))

    def test_count_required_for_cash_in_also_gated_by_cash_in_enabled(self):
        toggles = CountToggles(cash_in_enabled=False, in_required=True)
        self.assertFalse(count_required("in", toggles, cash_control=True))

        toggles = CountToggles(cash_in_enabled=True, in_required=True)
        self.assertTrue(count_required("in", toggles, cash_control=True))
