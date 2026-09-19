"""`pos.session.get_vault_withdrawal_state()` and the
`pos.config.vault_withdrawal_threshold` field.

Covers spec `vault-withdrawal-alert` (server-side portion): Requirement
"Vault Withdrawal Threshold Field" and Requirement "Server Method With
Parity To `get_closing_control_data`".
"""

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import AccessError
from odoo.tests import tagged


@tagged("pcdc", "pcdc_vault_backend")
class TestVaultAlert(CommonPosTest):
    def test_threshold_defaults_to_zero(self):
        """Threshold defaults to zero."""
        self.assertEqual(self.pos_config_usd.vault_withdrawal_threshold, 0)

    def test_threshold_field_hidden_without_cash_control(self):
        """Threshold field hidden without cash control: the enclosing
        block for `pos_vault_withdrawal_threshold` is invisible when
        `pos_cash_control` is falsy (`pos_config_eur` has no cash payment
        method, so `cash_control` is False)."""
        self.assertFalse(self.pos_config_eur.cash_control)
        view = self.env["res.config.settings"]._get_view(
            view_id=self.env.ref("point_of_sale.res_config_settings_view_form").id
        )[0]
        block = view.xpath(
            "//field[@name='pos_vault_withdrawal_threshold']/ancestor::block[1]"
        )
        self.assertTrue(
            block, "pos_vault_withdrawal_threshold field must be present in the view"
        )
        self.assertEqual(block[0].get("invisible"), "not pos_cash_control")

    def test_parity_between_alert_method_and_closing_control_formula(self):
        """Parity between the alert method and the closing control
        formula: the alert's `expected_cash` must equal
        `get_closing_control_data()['default_cash_details']['amount']` for a
        session with orders and cash moves."""
        self.pos_config_usd.vault_withdrawal_threshold = 1
        self.pos_config_usd.open_ui()
        session = self.pos_config_usd.current_session_id
        session.set_opening_control(100, False)
        reason = self.env["pos.cash.move.reason"].create(
            {"name": "Test Reason", "direction": "both"}
        )
        session.try_cash_in_out(
            "out",
            25,
            "Bank deposit",
            False,
            {"translatedType": "Cash out", "reason_id": reason.id},
        )
        closing_data = session.get_closing_control_data()
        state = session.get_vault_withdrawal_state()
        self.assertEqual(
            state["expected_cash"],
            closing_data["default_cash_details"]["amount"],
        )

    def test_required_is_false_when_cash_control_is_off(self):
        """Required is False when cash control is off."""
        self.pos_config_eur.open_ui()
        session = self.pos_config_eur.current_session_id
        session.set_opening_control(0, False)
        state = session.get_vault_withdrawal_state()
        self.assertFalse(state["required"])

    def test_required_is_false_when_threshold_is_zero(self):
        """Required is False when threshold is zero."""
        self.pos_config_usd.vault_withdrawal_threshold = 0
        self.pos_config_usd.open_ui()
        session = self.pos_config_usd.current_session_id
        session.set_opening_control(1_000_000, False)
        state = session.get_vault_withdrawal_state()
        self.assertFalse(state["required"])

    def test_access_denied_for_user_without_group_pos_user(self):
        """Access denied for a user without group_pos_user."""
        self.pos_config_usd.open_ui()
        session = self.pos_config_usd.current_session_id
        session.set_opening_control(0, False)
        no_access_user = self.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "User without POS access",
                "login": "pcdc_no_pos_access_user",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            session.with_user(no_access_user).get_vault_withdrawal_state()
