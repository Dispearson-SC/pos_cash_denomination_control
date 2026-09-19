"""Server-side enforcement of the cash-in toggle.

Covers spec `cash-in-control`. `try_cash_in_out` must reject `_type='in'`
whenever the session's `pos.config.allow_cash_in` is `False`, regardless of
caller (direct RPC included), additive to the stock
`_has_cash_move_permission()` check. It must never affect `_type='out'`.
"""

from odoo import Command
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("pcdc", "pcdc_cash_in")
class TestCashInControl(CommonPosTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # setUpClass grants the default env.user the manager group, which
        # satisfies `_has_cash_move_permission()`.
        cls.pos_config_usd.open_ui()
        cls.session = cls.pos_config_usd.current_session_id
        cls.session.set_opening_control(0, False)
        cls.no_permission_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "PoS user without cash permission",
                "login": "pos_user_no_cash_permission",
                "group_ids": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("point_of_sale.group_pos_user").id,
                        ]
                    )
                ],
            }
        )

    def _statement_line_count(self):
        return self.env["account.bank.statement.line"].search_count(
            [("pos_session_id", "=", self.session.id)]
        )

    def test_new_pos_config_cash_in_off_by_default(self):
        """New POS config has cash-in off by default."""
        config = self.env["pos.config"].create({"name": "New PoS"})
        self.assertFalse(config.allow_cash_in)

    def test_direct_rpc_cash_in_rejected_when_disabled(self):
        """Direct RPC cash-in rejected when disabled."""
        self.pos_config_usd.allow_cash_in = False
        before = self._statement_line_count()
        with self.assertRaises(UserError):
            self.session.try_cash_in_out("in", 10, "Test reason", False, {})
        self.assertEqual(self._statement_line_count(), before)

    def test_offline_queued_cash_in_replay_rejected_after_disabling(self):
        """Offline-queued cash-in replay rejected after disabling."""
        self.pos_config_usd.allow_cash_in = True
        self.pos_config_usd.allow_cash_in = False
        before = self._statement_line_count()
        with self.assertRaises(UserError):
            self.session.try_cash_in_out("in", 10, "Queued reason", False, {})
        self.assertEqual(self._statement_line_count(), before)

    def test_cash_out_unaffected_by_cash_in_toggle(self):
        """Cash-out unaffected by cash-in toggle."""
        self.pos_config_usd.allow_cash_in = False
        before = self._statement_line_count()
        self.session.try_cash_in_out(
            "out", 5, "Bank deposit", False, {"translatedType": "Cash out"}
        )
        self.assertEqual(self._statement_line_count(), before + 1)

    def test_permission_present_but_toggle_off_is_still_rejected(self):
        """Permission present but toggle off is still rejected."""
        self.pos_config_usd.allow_cash_in = False
        self.assertTrue(self.env.user._has_cash_move_permission())
        with self.assertRaises(UserError):
            self.session.try_cash_in_out("in", 10, "Test reason", False, {})

    def test_toggle_on_but_permission_absent_is_still_rejected(self):
        """Toggle on but permission absent is still rejected."""
        self.pos_config_usd.allow_cash_in = True
        self.assertFalse(self.no_permission_user._has_cash_move_permission())
        from odoo.exceptions import AccessError

        with self.assertRaises(AccessError):
            self.session.with_user(self.no_permission_user).try_cash_in_out(
                "in", 10, "Test reason", False, {}
            )

    def test_permission_present_and_toggle_on_succeeds(self):
        """Permission present and toggle on succeeds."""
        self.pos_config_usd.allow_cash_in = True
        before = self._statement_line_count()
        self.session.try_cash_in_out(
            "in", 10, "Test reason", False, {"translatedType": "Cash in"}
        )
        self.assertEqual(self._statement_line_count(), before + 1)

    def test_cash_in_accepted_when_enabled_and_permitted(self):
        """Cash-in accepted when enabled and permitted."""
        self.pos_config_usd.allow_cash_in = True
        before = self._statement_line_count()
        self.session.try_cash_in_out(
            "in", 15, "Valid reason", False, {"translatedType": "Cash in"}
        )
        self.assertEqual(self._statement_line_count(), before + 1)

    def test_settings_shows_cash_in_toggle_with_cash_control(self):
        """Shown with cash control: the enclosing block for
        `pos_allow_cash_in` is visible when `pos_cash_control` is truthy."""
        view = self.env["res.config.settings"]._get_view(
            view_id=self.env.ref("point_of_sale.res_config_settings_view_form").id
        )[0]
        block = view.xpath("//field[@name='pos_allow_cash_in']/ancestor::block[1]")
        self.assertTrue(block, "pos_allow_cash_in field must be present in the view")
        self.assertEqual(block[0].get("invisible"), "not pos_cash_control")

    def test_settings_hides_cash_in_toggle_without_cash_control(self):
        """Hidden without cash control: same structural check, read as the
        negative case (the `invisible` expression evaluates truthy when
        `pos_cash_control` is falsy)."""
        view = self.env["res.config.settings"]._get_view(
            view_id=self.env.ref("point_of_sale.res_config_settings_view_form").id
        )[0]
        block = view.xpath("//field[@name='pos_allow_cash_in']/ancestor::block[1]")
        self.assertTrue(block)
        self.assertEqual(block[0].get("invisible"), "not pos_cash_control")
