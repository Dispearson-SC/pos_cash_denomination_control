"""`pos.cash.move.reason` model: creation, the vault-out-only constraint,
seed data, defaults, security, views, frontend loading, and the enforcement
of a reason on every cash move.

Covers spec `cash-move-reasons`.
"""

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged("pcdc", "pcdc_reasons")
class TestReasons(CommonPosTest):
    def test_create_reason_with_direction_and_vault_flag(self):
        """Create a reason with direction and vault flag."""
        reason = self.env["pos.cash.move.reason"].create(
            {"name": "Bank Deposit", "direction": "out", "is_vault": False}
        )
        self.assertEqual(reason.name, "Bank Deposit")
        self.assertEqual(reason.direction, "out")
        self.assertFalse(reason.is_vault)

    def test_creating_vault_reason_with_direction_in_is_rejected(self):
        """Creating a vault reason with direction 'in' is rejected."""
        with self.assertRaises(ValidationError):
            self.env["pos.cash.move.reason"].create(
                {"name": "Bad Vault", "direction": "in", "is_vault": True}
            )

    def test_creating_vault_reason_with_direction_both_is_rejected(self):
        """Creating a vault reason with direction 'both' is rejected."""
        with self.assertRaises(ValidationError):
            self.env["pos.cash.move.reason"].create(
                {"name": "Bad Vault", "direction": "both", "is_vault": True}
            )

    def test_creating_vault_reason_with_direction_out_succeeds(self):
        """Creating a vault reason with direction 'out' succeeds."""
        reason = self.env["pos.cash.move.reason"].create(
            {"name": "Good Vault", "direction": "out", "is_vault": True}
        )
        self.assertTrue(reason.is_vault)

    def test_editing_reason_to_vault_with_non_out_direction_is_rejected(self):
        """Editing an existing reason to set is_vault=True with a
        non-out direction is rejected."""
        reason = self.env["pos.cash.move.reason"].create(
            {"name": "Refund", "direction": "in", "is_vault": False}
        )
        with self.assertRaises(ValidationError):
            reason.write({"is_vault": True})

    def test_seed_data(self):
        """Exactly one seeded Vault reason exists after install."""
        vault_reasons = self.env["pos.cash.move.reason"].search(
            [("is_vault", "=", True)]
        )
        self.assertEqual(len(vault_reasons), 1)
        self.assertEqual(vault_reasons.name, "Vault")
        self.assertEqual(vault_reasons.direction, "out")

    def test_multi_company_record_rule_hides_other_company_reasons(self):
        """Multi-company record rule hides other company's reasons."""
        company_b = self.env["res.company"].create({"name": "Company B"})
        reason_a = self.env["pos.cash.move.reason"].create(
            {"name": "Reason A", "company_id": self.env.company.id}
        )
        reason_b = self.env["pos.cash.move.reason"].create(
            {"name": "Reason B", "company_id": company_b.id}
        )
        found = self.env["pos.cash.move.reason"].with_context(
            allowed_company_ids=[self.env.company.id]
        ).search([("id", "in", (reason_a | reason_b).ids)])
        self.assertEqual(found, reason_a)

    def test_reasons_menu(self):
        """Reasons menu is accessible under POS Configuration."""
        menu = self.env.ref(
            "pos_cash_denomination_control.menu_pos_cash_move_reason"
        )
        self.assertEqual(
            menu.parent_id, self.env.ref("point_of_sale.menu_point_config_product")
        )
        self.assertEqual(menu.action.res_model, "pos.cash.move.reason")


@tagged("pcdc", "pcdc_reasons")
class TestReasonEnforcement(CommonPosTest):
    """`try_cash_in_out` reason validation and storage.

    Covers spec `cash-move-reasons` (Requirement: Reason Transport And
    Mandatory Server Validation, Requirement: Reason Storage And
    `payment_ref` Composition).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.allow_cash_in = True
        cls.pos_config_usd.open_ui()
        cls.session = cls.pos_config_usd.current_session_id
        cls.session.set_opening_control(0, False)
        cls.out_reason = cls.env["pos.cash.move.reason"].create(
            {"name": "Bank Deposit", "direction": "out"}
        )
        cls.in_reason = cls.env["pos.cash.move.reason"].create(
            {"name": "Till Top-Up", "direction": "in"}
        )
        cls.other_company = cls.env["res.company"].create({"name": "Other Co"})
        cls.other_company_reason = cls.env["pos.cash.move.reason"].create(
            {"name": "Other Co Reason", "direction": "out", "company_id": cls.other_company.id}
        )
        cls.vault_reason = cls.env.ref(
            "pos_cash_denomination_control.pos_cash_move_reason_vault"
        )

    def _statement_line_count(self):
        return self.env["account.bank.statement.line"].search_count(
            [("pos_session_id", "=", self.session.id)]
        )

    def test_missing_reason_id_is_rejected(self):
        """Missing reason_id is rejected before any statement line is
        created."""
        before = self._statement_line_count()
        with self.assertRaises(UserError):
            self.session.try_cash_in_out(
                "out", 5, "Test", False, {"translatedType": "Cash out"}
            )
        self.assertEqual(self._statement_line_count(), before)

    def test_inactive_reason_is_rejected(self):
        """Inactive reason is rejected."""
        inactive_reason = self.env["pos.cash.move.reason"].create(
            {"name": "Retired", "direction": "out", "active": False}
        )
        before = self._statement_line_count()
        with self.assertRaises(UserError):
            self.session.try_cash_in_out(
                "out",
                5,
                "Test",
                False,
                {"translatedType": "Cash out", "reason_id": inactive_reason.id},
            )
        self.assertEqual(self._statement_line_count(), before)

    def test_other_company_reason_is_rejected(self):
        """Other-company reason is rejected."""
        before = self._statement_line_count()
        with self.assertRaises(UserError):
            self.session.try_cash_in_out(
                "out",
                5,
                "Test",
                False,
                {
                    "translatedType": "Cash out",
                    "reason_id": self.other_company_reason.id,
                },
            )
        self.assertEqual(self._statement_line_count(), before)

    def test_direction_incompatible_reason_is_rejected(self):
        """Direction-incompatible reason is rejected."""
        before = self._statement_line_count()
        with self.assertRaises(UserError):
            self.session.try_cash_in_out(
                "out",
                5,
                "Test",
                False,
                {"translatedType": "Cash out", "reason_id": self.in_reason.id},
            )
        self.assertEqual(self._statement_line_count(), before)

    def test_vault_reason_on_cash_in_is_rejected(self):
        """Vault reason on cash-in is rejected."""
        before = self._statement_line_count()
        with self.assertRaises(UserError):
            self.session.try_cash_in_out(
                "in",
                5,
                "Test",
                False,
                {"translatedType": "Cash in", "reason_id": self.vault_reason.id},
            )
        self.assertEqual(self._statement_line_count(), before)

    def test_valid_reason_is_accepted_and_stored(self):
        """Valid reason is accepted and stored."""
        before = self._statement_line_count()
        self.session.try_cash_in_out(
            "out",
            5,
            "Test",
            False,
            {"translatedType": "Cash out", "reason_id": self.out_reason.id},
        )
        self.assertEqual(self._statement_line_count(), before + 1)
        line = self.env["account.bank.statement.line"].search(
            [("pos_session_id", "=", self.session.id)], order="id desc", limit=1
        )
        self.assertEqual(line.cash_move_reason_id, self.out_reason)

    def test_payment_ref_contains_only_reason_name_without_note(self):
        """payment_ref contains only the reason name when no note is
        given."""
        self.session.try_cash_in_out(
            "out",
            5,
            "Test",
            False,
            {"translatedType": "Cash out", "reason_id": self.out_reason.id},
        )
        line = self.env["account.bank.statement.line"].search(
            [("pos_session_id", "=", self.session.id)], order="id desc", limit=1
        )
        self.assertEqual(
            line.payment_ref, f"{self.session.name}-Cash out-Bank Deposit"
        )

    def test_payment_ref_contains_reason_name_and_note(self):
        """payment_ref contains the reason name followed by the note when
        given."""
        self.session.try_cash_in_out(
            "out",
            5,
            "Test",
            False,
            {
                "translatedType": "Cash out",
                "reason_id": self.out_reason.id,
                "note": "till audit",
            },
        )
        line = self.env["account.bank.statement.line"].search(
            [("pos_session_id", "=", self.session.id)], order="id desc", limit=1
        )
        self.assertEqual(
            line.payment_ref,
            f"{self.session.name}-Cash out-Bank Deposit: till audit",
        )
