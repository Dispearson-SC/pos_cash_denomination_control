"""Closing manager override guard at `_validate_session`.

Covers spec `closing-manager-override`. See design.md's "Back-office close
guard" pseudocode: `_validate_session` is the single writer of
`state='closed'` (`point_of_sale/models/pos_session.py:482`), so every
public close path (the back-office button, the imbalance/force-close
wizard, and direct RPC calls to `action_pos_session_validate` or
`action_pos_session_close`) reaches the same guard. With the closing
toggle on, closing without a valid closing count is manager-only; any
other user gets `UserError`, and a manager instead gets flagged
(`closed_without_denomination_count` + user/date + chatter).
"""

from odoo import Command
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("pcdc", "pcdc_closing_override")
class TestClosingOverride(CommonPosTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # `CommonPosTest.setUpClass` grants the default `env.user` (used as
        # "the manager" throughout this file) `point_of_sale.group_pos_manager`.
        cls.non_manager = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "PoS user without manager group",
                    "login": "pos_user_non_manager_closing",
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
        )

    def _open_session(self, closing_required=True, rescue=False):
        self.pos_config_usd.cash_count_closing_required = closing_required
        self.pos_config_usd.open_ui()
        session = self.pos_config_usd.current_session_id
        session.set_opening_control(0, False)
        if rescue:
            session.rescue = True
        return session

    def test_non_manager_closing_without_breakdown_is_rejected(self):
        """Non-manager closing without a breakdown is rejected."""
        session = self._open_session()
        with self.assertRaises(UserError):
            session.with_user(self.non_manager).action_pos_session_close()
        self.assertNotEqual(session.state, "closed")

    def test_manager_closing_without_breakdown_succeeds_and_flags_session(self):
        """Manager closing without a breakdown succeeds and flags the
        session."""
        session = self._open_session()
        session.action_pos_session_close()
        self.assertEqual(session.state, "closed")
        self.assertTrue(session.closed_without_denomination_count)
        self.assertEqual(
            session.closed_without_denomination_count_user_id, self.env.user
        )
        self.assertTrue(session.closed_without_denomination_count_date)

    def test_non_manager_direct_rpc_action_pos_session_validate_is_rejected(
        self,
    ):
        """Non-manager direct RPC to action_pos_session_validate is
        rejected without a breakdown."""
        session = self._open_session()
        with self.assertRaises(UserError):
            session.with_user(self.non_manager).action_pos_session_validate()

    def test_non_manager_via_imbalance_wizard_is_rejected(self):
        """Non-manager via the imbalance wizard is rejected without a
        breakdown."""
        session = self._open_session()
        wizard = (
            self.env["pos.close.session.wizard"]
            .with_user(self.non_manager)
            .with_context(active_ids=session.ids)
            .create({"amount_to_balance": 0.0})
        )
        with self.assertRaises(UserError):
            wizard.close_session()

    def test_manager_via_any_public_close_path_succeeds_and_is_flagged(self):
        """Manager via any public close path succeeds and is flagged
        identically (back-office button, wizard,
        action_pos_session_validate, action_pos_session_close)."""

        def _via_closing_control(session):
            session.action_pos_session_closing_control()

        def _via_wizard(session):
            wizard = self.env["pos.close.session.wizard"].with_context(
                active_ids=session.ids
            ).create({"amount_to_balance": 0.0})
            wizard.close_session()

        def _via_validate(session):
            session.action_pos_session_validate()

        def _via_close(session):
            session.action_pos_session_close()

        paths = {
            "back-office button (action_pos_session_closing_control)": _via_closing_control,
            "imbalance/force-close wizard": _via_wizard,
            "action_pos_session_validate": _via_validate,
            "action_pos_session_close": _via_close,
        }
        for label, close_path in paths.items():
            with self.subTest(path=label):
                session = self._open_session()
                close_path(session)
                self.assertEqual(session.state, "closed")
                self.assertTrue(session.closed_without_denomination_count)
                self.assertEqual(
                    session.closed_without_denomination_count_user_id,
                    self.env.user,
                )

    def test_rejected_closing_leaves_no_journal_entries_and_no_state_change(
        self,
    ):
        """Rejected closing leaves no journal entries and no state
        change."""
        session = self._open_session()
        reason = self.env["pos.cash.move.reason"].create(
            {"name": "Test Reason", "direction": "both"}
        )
        # A statement line exists so `_validate_session`'s account-move
        # branch would have something to post if the guard did not stop it
        # first (`get_session_orders() or statement_line_ids` gate at
        # `point_of_sale/models/pos_session.py:430`).
        session.try_cash_in_out(
            "out", 5, "Test reason", False,
            {"translatedType": "Cash out", "reason_id": reason.id},
        )
        state_before = session.state
        with self.assertRaises(UserError):
            session.with_user(self.non_manager).action_pos_session_close()
        self.assertEqual(session.state, state_before)
        self.assertFalse(session.move_id)

    def test_flag_user_date_and_chatter_are_recorded(self):
        """Flag, user, date/time, and chatter are recorded."""
        session = self._open_session()
        session.action_pos_session_close()
        self.assertTrue(session.closed_without_denomination_count)
        self.assertEqual(
            session.closed_without_denomination_count_user_id, self.env.user
        )
        self.assertTrue(session.closed_without_denomination_count_date)
        message = session.message_ids.filtered(
            lambda m: "denomination count" in (m.body or "")
        )
        self.assertTrue(message)

    def test_sessions_are_filterable_and_groupable_by_flag(self):
        """Sessions are filterable and groupable by the flag."""
        flagged = self._open_session()
        flagged.action_pos_session_close()

        unflagged = self._open_session()
        unflagged.post_closing_cash_details(0, denomination_lines=[])
        unflagged.action_pos_session_close()

        filtered = self.env["pos.session"].search(
            [
                ("id", "in", (flagged | unflagged).ids),
                ("closed_without_denomination_count", "=", True),
            ]
        )
        self.assertEqual(filtered, flagged)

        groups = self.env["pos.session"]._read_group(
            [("id", "in", (flagged | unflagged).ids)],
            ["closed_without_denomination_count"],
            ["__count"],
        )
        buckets = {flag: count for flag, count in groups}
        self.assertEqual(buckets.get(True), 1)
        self.assertEqual(buckets.get(False), 1)

    def test_non_manager_closes_without_breakdown_when_toggle_off(self):
        """Non-manager closes without a breakdown when toggle is off."""
        session = self._open_session(closing_required=False)
        session.with_user(self.non_manager).action_pos_session_close()
        self.assertEqual(session.state, "closed")
        self.assertFalse(session.closed_without_denomination_count)

    def test_manager_closes_rescue_session_without_breakdown_and_it_is_flagged(
        self,
    ):
        """Manager closes a rescue session without a breakdown and it is
        flagged."""
        session = self._open_session(rescue=True)
        session.action_pos_session_closing_control()
        self.assertEqual(session.state, "closed")
        self.assertTrue(session.closed_without_denomination_count)

    def test_non_manager_closing_rescue_session_without_breakdown_is_rejected(
        self,
    ):
        """Non-manager closing a rescue session without a breakdown is
        rejected."""
        session = self._open_session(rescue=True)
        with self.assertRaises(UserError):
            session.with_user(self.non_manager).action_pos_session_closing_control()
        self.assertNotEqual(session.state, "closed")

    def test_close_session_from_ui_non_manager_without_breakdown_is_rejected(
        self,
    ):
        """`close_session_from_ui` (the POS UI closing entry point,
        design.md's Closing Server Flow: `close_session_from_ui ->
        action_pos_session_closing_control -> ... -> _validate_session
        [guard]`) rejects a non-manager without a recorded breakdown, same
        as every other public close path. Task 10.6's runtime harness
        names this method explicitly."""
        session = self._open_session()
        with self.assertRaises(UserError):
            session.with_user(self.non_manager).close_session_from_ui()
        self.assertNotEqual(session.state, "closed")

    def test_close_session_from_ui_manager_without_breakdown_is_flagged(self):
        """`close_session_from_ui` succeeds and flags the session for a
        manager closing without a recorded breakdown."""
        session = self._open_session()
        session.close_session_from_ui()
        self.assertEqual(session.state, "closed")
        self.assertTrue(session.closed_without_denomination_count)

    def test_check_uses_acting_user_own_groups_not_escalated_context(self):
        """Check uses the acting user's own groups, not an escalated
        context.

        Stock `_validate_session` internally elevates `record` to
        `record.sudo()` for any caller in `point_of_sale.group_pos_user`
        (`point_of_sale/models/pos_session.py:427-428`) to perform its own
        unrelated writes. `self.non_manager` deliberately holds
        `group_pos_user` (so that internal escalation fires), and the
        guard must still reject the closing: it evaluates
        `self.env.user.has_group(...)` in its own override, which runs
        entirely before `super()` performs that escalation.
        """
        self.assertTrue(
            self.non_manager.has_group("point_of_sale.group_pos_user")
        )
        self.assertFalse(
            self.non_manager.has_group("point_of_sale.group_pos_manager")
        )
        session = self._open_session()
        with self.assertRaises(UserError):
            session.with_user(self.non_manager).action_pos_session_close()
        self.assertNotEqual(session.state, "closed")
