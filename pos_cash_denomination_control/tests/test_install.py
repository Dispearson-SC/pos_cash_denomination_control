"""Install-time defaults for `pos.config`.

Covers spec `cash-in-control`: "Existing POS config has cash-in off after
install". The "New POS config has cash-in off by default" scenario for a
freshly created record lives in `tests/test_cash_in_control.py`.
"""

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.tests import tagged

from ..hooks import post_init_hook


@tagged("pcdc", "pcdc_cash_in")
class TestInstall(CommonPosTest):
    def test_existing_pos_config_cash_in_off_after_install(self):
        """A POS config that existed before this module was installed must
        have `allow_cash_in` set to `False` (column default applies to every
        existing row when the module is installed)."""
        self.assertFalse(self.pos_config_usd.allow_cash_in)

    def test_new_pos_config_defaults_to_vault_reason(self):
        """New POS config defaults to the Vault reason."""
        config = self.env["pos.config"].create({"name": "New PoS"})
        vault_reason = self.env.ref(
            "pos_cash_denomination_control.pos_cash_move_reason_vault"
        )
        self.assertEqual(config.default_cash_out_reason_id, vault_reason)

    def test_existing_pos_config_gets_vault_default_after_install(self):
        """Existing POS config gets the Vault default after install.

        `pos_config_usd` is created by `CommonPosTest.setUpClass`, which
        runs after this module's real install already completed, so it
        cannot exercise the "existing row" backfill path on its own (the
        callable field default already resolves it at creation, same as a
        brand-new config). The field is nulled out with raw SQL to simulate
        a row that existed before the hook ran, then `post_init_hook` is
        invoked directly, matching what `__manifest__.py`'s
        `post_init_hook` entry runs on install.
        """
        self.env.cr.execute(
            "UPDATE pos_config SET default_cash_out_reason_id = NULL WHERE id = %s",
            (self.pos_config_usd.id,),
        )
        self.pos_config_usd.invalidate_recordset(["default_cash_out_reason_id"])
        self.assertFalse(self.pos_config_usd.default_cash_out_reason_id)

        post_init_hook(self.env)
        self.pos_config_usd.invalidate_recordset(["default_cash_out_reason_id"])

        vault_reason = self.env.ref(
            "pos_cash_denomination_control.pos_cash_move_reason_vault"
        )
        self.assertEqual(self.pos_config_usd.default_cash_out_reason_id, vault_reason)
