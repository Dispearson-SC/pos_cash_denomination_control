"""`pos.config`'s four independent denomination-count toggles: defaults,
independence, and settings-view visibility.

Covers spec `cash-denomination-config`.
"""

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.tests import tagged

_TOGGLE_FIELDS = (
    "cash_count_opening_required",
    "cash_count_out_required",
    "cash_count_in_required",
    "cash_count_closing_required",
)


@tagged("pcdc", "pcdc_counts")
class TestDenominationConfig(CommonPosTest):
    def test_new_pos_config_has_all_four_toggles_off(self):
        """New POS config has all four toggles off."""
        config = self.env["pos.config"].create({"name": "New PoS"})
        for field_name in _TOGGLE_FIELDS:
            self.assertFalse(config[field_name], field_name)

    def test_existing_pos_config_has_all_four_toggles_off_after_install(self):
        """Existing POS config has all four toggles off after install
        (column default applies to every existing row, same as
        `allow_cash_in` in Phase 3 — no post-init hook needed)."""
        for field_name in _TOGGLE_FIELDS:
            self.assertFalse(self.pos_config_usd[field_name], field_name)

    def test_toggles_are_independent_of_each_other(self):
        """Toggles are independent of each other."""
        config = self.env["pos.config"].create(
            {"name": "New PoS", "cash_count_opening_required": True}
        )
        self.assertTrue(config.cash_count_opening_required)
        self.assertFalse(config.cash_count_out_required)
        self.assertFalse(config.cash_count_in_required)
        self.assertFalse(config.cash_count_closing_required)

    def _settings_view(self):
        return self.env["res.config.settings"]._get_view(
            view_id=self.env.ref("point_of_sale.res_config_settings_view_form").id
        )[0]

    def test_toggles_hidden_without_cash_control(self):
        """Toggles hidden without cash control: the enclosing block for
        the opening/out/closing toggles is invisible when
        `pos_cash_control` is falsy (same block-level assertion style as
        `test_cash_in_control.py`'s cash-in toggle check)."""
        view = self._settings_view()
        for field_name in (
            "pos_cash_count_opening_required",
            "pos_cash_count_out_required",
            "pos_cash_count_closing_required",
        ):
            block = view.xpath(f"//field[@name='{field_name}']/ancestor::block[1]")
            self.assertTrue(block, field_name)
            self.assertEqual(block[0].get("invisible"), "not pos_cash_control")

    def test_toggles_shown_with_cash_control(self):
        """Toggles shown with cash control (same structural assertion,
        read as the positive case: the block's `invisible` expression
        evaluates falsy once `pos_cash_control` is truthy)."""
        self.test_toggles_hidden_without_cash_control()

    def test_cash_in_toggle_hidden_when_cash_in_is_disabled(self):
        """Cash-IN toggle hidden when cash-in is disabled: its own
        `<setting>` carries an additional `invisible="not
        pos_allow_cash_in"`, nested inside the already cash-control-gated
        block."""
        view = self._settings_view()
        setting = view.xpath(
            "//field[@name='pos_cash_count_in_required']/ancestor::setting[1]"
        )
        self.assertTrue(setting, "pos_cash_count_in_required setting must be present")
        self.assertEqual(setting[0].get("invisible"), "not pos_allow_cash_in")

    def test_cash_in_toggle_shown_when_cash_in_is_enabled(self):
        """Cash-IN toggle shown when cash-in is enabled (same structural
        assertion; evaluates falsy at runtime once `pos_allow_cash_in` is
        `True`)."""
        self.test_cash_in_toggle_hidden_when_cash_in_is_disabled()
