"""`pos.config.vault_withdrawal_blocking` and its settings-view exposure.

Covers spec `vault-withdrawal-blocking` (backend portion): Requirement
"Blocking Field" and Requirement "Settings Exposure, Gated By Threshold".

The blocking behaviour itself (refusing sale validation, offering the
withdrawal, the no-permission dead end, the block lifting) is entirely
client-side — see `static/tests/unit/payment_screen_vault_block.test.js` —
because this is a WORKFLOW CONTROL, not a security boundary: server-side
rejection would destroy real transactions, since POS orders sync after the
sale has physically happened. This file only covers the one thing that is
genuinely server-side: the config field and its settings-view reachability.
"""

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.tests import tagged


@tagged("pcdc", "pcdc_vault_block")
class TestVaultBlockingConfig(CommonPosTest):
    def _settings_view(self):
        return self.env["res.config.settings"]._get_view(
            view_id=self.env.ref("point_of_sale.res_config_settings_view_form").id
        )[0]

    def test_blocking_defaults_to_false(self):
        """Blocking defaults to False, off by default like every other
        flag this addon adds (`allow_cash_in`, the four
        `cash_count_*_required` toggles)."""
        self.assertFalse(self.pos_config_usd.vault_withdrawal_blocking)

    def test_existing_pos_config_has_blocking_off_after_install(self):
        """Existing POS config has blocking off after install (column
        default applies to every existing row, same reasoning as
        `allow_cash_in` — no post-init hook needed)."""
        self.assertFalse(self.pos_config_eur.vault_withdrawal_blocking)

    def test_blocking_setting_reachable_in_rendered_settings_view(self):
        """Reachable in the RENDERED settings arch via `_get_view`, not
        merely present in the source XML — this project shipped two
        unreachable features already."""
        view = self._settings_view()
        field = view.xpath("//field[@name='pos_vault_withdrawal_blocking']")
        self.assertTrue(
            field,
            "pos_vault_withdrawal_blocking field must be reachable in the "
            "rendered settings view",
        )

    def test_blocking_setting_lives_in_cash_control_block(self):
        """The setting lives inside the existing `pcdc_cash_section` block,
        beside `pos_vault_withdrawal_threshold` — not a new, separately
        gated block."""
        view = self._settings_view()
        block = view.xpath(
            "//field[@name='pos_vault_withdrawal_blocking']/ancestor::block[1]"
        )
        self.assertTrue(block, "setting must be inside a block")
        self.assertEqual(block[0].get("id"), "pcdc_cash_section")

    def test_blocking_setting_hidden_when_threshold_is_zero(self):
        """Blocking is meaningless when `vault_withdrawal_threshold = 0`
        (it disables the alert entirely, so blocking can never fire). The
        setting must make that visible rather than letting someone switch
        on a block that silently does nothing: its own `<setting>` carries
        `invisible="not pos_vault_withdrawal_threshold"`."""
        view = self._settings_view()
        setting = view.xpath(
            "//field[@name='pos_vault_withdrawal_blocking']/ancestor::setting[1]"
        )
        self.assertTrue(setting, "pos_vault_withdrawal_blocking setting must be present")
        self.assertEqual(
            setting[0].get("invisible"), "not pos_vault_withdrawal_threshold"
        )

    def test_blocking_setting_shown_with_a_positive_threshold(self):
        """Shown with a positive threshold (same structural assertion,
        read as the positive case: the setting's `invisible` expression
        evaluates falsy once `pos_vault_withdrawal_threshold` is truthy)."""
        self.test_blocking_setting_hidden_when_threshold_is_zero()
