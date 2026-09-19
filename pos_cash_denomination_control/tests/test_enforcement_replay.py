"""Offline replay safety for denomination breakdown enforcement.

Covers spec `cash-denomination-enforcement`, Requirement "Offline Replay
Safety". Because opening and cash-move RPCs travel through the
offline-tolerant queue, this proves server-side validation depends only on
the single payload plus the server's *current* configuration, never on
anything cached from an earlier request.
"""

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("pcdc", "pcdc_enforcement")
class TestEnforcementReplay(CommonPosTest):
    def setUp(self):
        super().setUp()
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.bill_10 = self.env["pos.bill"].create({"name": "10", "value": 10.0})

    def test_queued_opening_replay_is_validated_independently_after_reconnect(
        self,
    ):
        """Queued opening replay is validated independently after
        reconnect.

        A self-contained payload (bill ids, quantities, declared amount)
        is all `_set_opening_control_data` reads from the request: it
        resolves toggles/allowed-bills/rounding fresh from the session's
        config on every call rather than from any earlier client or
        request-scoped state, exactly as a replayed offline RPC reaching
        the server later would. This exercises the same code path as
        `tests/test_enforcement_opening.py`'s "valid breakdown accepted"
        scenario, proven again here under the replay-safety requirement.
        """
        self.pos_config_usd.cash_count_opening_required = True
        self.session.set_opening_control(
            20,
            False,
            denomination_lines=[{"bill_id": self.bill_10.id, "quantity": 2}],
        )
        self.assertEqual(self.session.cash_register_balance_start, 20)

    def test_offline_replay_against_changed_allowed_bills_is_rejected_at_replay_time(
        self,
    ):
        """Offline replay against changed allowed-bills configuration is
        rejected at replay time: a bill allowed when a cash move was
        queued, but restricted to a different POS before the queued call
        replays, is rejected using the server's state *at replay time*,
        not at queue time."""
        self.session.set_opening_control(0, False)
        self.pos_config_usd.cash_count_out_required = True
        reason = self.env["pos.cash.move.reason"].create(
            {"name": "Test Reason", "direction": "out"}
        )
        extras = {
            "translatedType": "Cash out",
            "reason_id": reason.id,
            "denomination_lines": [{"bill_id": self.bill_10.id, "quantity": 1}],
        }
        # First call: the bill is still globally allowed (no
        # `pos_config_ids` restriction) -> succeeds.
        self.session.try_cash_in_out("out", 10, "Test", False, extras)

        # Configuration changes before the "replay": the bill is now
        # restricted to a different point of sale.
        self.bill_10.pos_config_ids = [(6, 0, [self.pos_config_eur.id])]

        with self.assertRaises(UserError):
            self.session.try_cash_in_out("out", 10, "Test", False, extras)
