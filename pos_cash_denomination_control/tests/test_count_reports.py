"""Denomination movement reporting: aggregated header views/action/menu, the
session smart button, and cross-navigation between reports and sessions.

Covers this phase's feature document (`odd/tasks/denomination-count-reports.md`):
one row per `pos.cash.denomination.count` header (a "movement") with its
lines one click away, a session-scoped smart button, and "Open session"
navigation from both the movement form and the existing line report.
"""

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.tests import tagged


@tagged("pcdc", "pcdc_count_reports")
class TestCountReports(CommonPosTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.allow_cash_in = True
        cls.pos_config_usd.open_ui()
        cls.session = cls.pos_config_usd.current_session_id
        cls.session.set_opening_control(0, False)

        cls.pos_config_eur.open_ui()
        cls.other_session = cls.pos_config_eur.current_session_id

        cls.reason = cls.env["pos.cash.move.reason"].create(
            {"name": "Bank Deposit", "direction": "out"}
        )
        cls.bill_1 = cls.env["pos.bill"].create({"name": "1", "value": 1.0})

    def _create_header(self, session, move_type, **extra):
        vals = {
            "session_id": session.id,
            "move_type": move_type,
            "total": 0,
            "user_id": self.env.user.id,
        }
        vals.update(extra)
        return self.env["pos.cash.denomination.count"].sudo().create(vals)

    def _create_line(self, header, bill, quantity):
        return (
            self.env["pos.cash.denomination.count.line"]
            .sudo()
            .create(
                {
                    "count_id": header.id,
                    "bill_id": bill.id,
                    "bill_name": bill.name,
                    "bill_value": bill.value,
                    "quantity": quantity,
                }
            )
        )

    # -- Session smart button: count + scoped action ----------------------

    def test_movement_count_matches_only_this_session_headers(self):
        """Movement count matches only this session's headers."""
        self._create_header(self.session, "opening", total=10)
        self._create_header(
            self.session, "out", total=5, reason_id=self.reason.id
        )
        self._create_header(self.other_session, "opening", total=20)
        self.session.invalidate_recordset(["pcdc_count_movement_count"])
        self.assertEqual(self.session.pcdc_count_movement_count, 2)

    def test_action_view_denomination_movements_domain_scoped_to_session(self):
        """Action domain is scoped to this session only."""
        header_a1 = self._create_header(self.session, "opening", total=10)
        header_a2 = self._create_header(
            self.session, "out", total=5, reason_id=self.reason.id
        )
        self._create_header(self.other_session, "opening", total=20)
        action = self.session.action_view_denomination_movements()
        self.assertEqual(action["res_model"], "pos.cash.denomination.count")
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["domain"], [("session_id", "in", [self.session.id])])
        found = self.env["pos.cash.denomination.count"].sudo().search(
            action["domain"]
        )
        self.assertEqual(found, header_a1 | header_a2)

    # -- Movement action/menu/views exist ----------------------------------

    def test_movement_action_view_and_menu_exist(self):
        """Movement action, views, and menu are registered."""
        self.assertTrue(
            self.env.ref("pos_cash_denomination_control.action_pos_cash_denomination_count")
        )
        self.assertTrue(
            self.env.ref("pos_cash_denomination_control.view_pos_cash_denomination_count_list")
        )
        self.assertTrue(
            self.env.ref("pos_cash_denomination_control.view_pos_cash_denomination_count_form")
        )
        self.assertTrue(
            self.env.ref("pos_cash_denomination_control.view_pos_cash_denomination_count_search")
        )
        self.assertTrue(
            self.env.ref(
                "pos_cash_denomination_control.menu_pos_cash_denomination_count_movement"
            )
        )

    def test_movement_list_view_shows_key_fields(self):
        """Movement list view shows date, session, POS, move type, reason,
        total, and user."""
        view = self.env["pos.cash.denomination.count"]._get_view(
            view_id=self.env.ref(
                "pos_cash_denomination_control.view_pos_cash_denomination_count_list"
            ).id
        )[0]
        for field_name in (
            "date",
            "session_id",
            "config_id",
            "move_type",
            "reason_id",
            "total",
            "user_id",
        ):
            self.assertTrue(
                view.xpath(f"//field[@name='{field_name}']"),
                f"expected field '{field_name}' in the movement list view",
            )

    def test_movement_form_view_has_open_session_button_and_lines(self):
        """Movement form has an 'Open session' button and the denomination
        line breakdown."""
        view = self.env["pos.cash.denomination.count"]._get_view(
            view_id=self.env.ref(
                "pos_cash_denomination_control.view_pos_cash_denomination_count_form"
            ).id
        )[0]
        button = view.xpath("//button[@name='action_open_session']")
        self.assertTrue(button, "expected an 'action_open_session' button")
        self.assertEqual(button[0].get("type"), "object")
        self.assertTrue(
            view.xpath("//field[@name='line_ids']"),
            "expected the denomination line_ids breakdown in the form",
        )
        self.assertTrue(
            view.xpath("//field[@name='session_id']"),
            "expected the session_id field in the form",
        )

    def test_movement_search_view_has_move_type_filters_and_group_by_session(self):
        """Movement search view filters by move type and groups by
        session, POS, move type, reason, and date."""
        view = self.env["pos.cash.denomination.count"]._get_view(
            view_id=self.env.ref(
                "pos_cash_denomination_control.view_pos_cash_denomination_count_search"
            ).id
        )[0]
        for filter_name in (
            "move_type_opening",
            "move_type_in",
            "move_type_out",
            "move_type_closing",
        ):
            self.assertTrue(
                view.xpath(f"//filter[@name='{filter_name}']"),
                f"expected filter '{filter_name}'",
            )
        for group_by_name in (
            "group_by_session",
            "group_by_config",
            "group_by_move_type",
            "group_by_reason",
            "group_by_date",
        ):
            self.assertTrue(
                view.xpath(f"//filter[@name='{group_by_name}']"),
                f"expected group-by filter '{group_by_name}'",
            )

    def test_session_form_has_denomination_movements_smart_button(self):
        """Session form shows the 'Denomination Movements' smart button in
        the button box."""
        view = self.env["pos.session"]._get_view(
            view_id=self.env.ref("point_of_sale.view_pos_session_form").id
        )[0]
        button = view.xpath(
            "//div[@name='button_box']/button[@name='action_view_denomination_movements']"
        )
        self.assertTrue(button, "expected the smart button in the button box")
        self.assertEqual(button[0].get("type"), "object")
        count_field = button[0].xpath(".//field[@name='pcdc_count_movement_count']")
        self.assertTrue(count_field, "expected the count field inside the button")
        self.assertEqual(count_field[0].get("widget"), "statinfo")

    # -- Line report: session column, group-by, open-session control ------

    def test_line_list_view_has_session_column_and_open_session_button(self):
        """Line report list has a session column and an 'Open session'
        row control."""
        view = self.env["pos.cash.denomination.count.line"]._get_view(
            view_id=self.env.ref(
                "pos_cash_denomination_control.view_pos_cash_denomination_count_line_list"
            ).id
        )[0]
        self.assertTrue(
            view.xpath("//field[@name='session_id']"),
            "expected a session_id column",
        )
        button = view.xpath("//button[@name='action_open_session']")
        self.assertTrue(button, "expected an 'action_open_session' row control")
        self.assertEqual(button[0].get("type"), "object")

    def test_line_search_view_has_group_by_session(self):
        """Line report search view can group by session."""
        view = self.env["pos.cash.denomination.count.line"]._get_view(
            view_id=self.env.ref(
                "pos_cash_denomination_control.view_pos_cash_denomination_count_line_search"
            ).id
        )[0]
        self.assertTrue(
            view.xpath("//filter[@name='group_by_session']"),
            "expected a group-by-session filter",
        )

    # -- Open-session navigation methods ------------------------------------

    def test_header_action_open_session_points_to_its_session(self):
        """Header's 'Open session' action points at its own session
        form."""
        header = self._create_header(self.session, "opening", total=10)
        action = header.action_open_session()
        self.assertEqual(action["res_model"], "pos.session")
        self.assertEqual(action["res_id"], self.session.id)
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["view_mode"], "form")

    def test_line_action_open_session_points_to_its_session(self):
        """Line's 'Open session' action points at its header's session
        form."""
        header = self._create_header(self.session, "opening", total=10)
        line = self._create_line(header, self.bill_1, 4)
        action = line.action_open_session()
        self.assertEqual(action["res_model"], "pos.session")
        self.assertEqual(action["res_id"], self.session.id)
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["view_mode"], "form")

    # -- Multi-company: header rule unaffected by new views/action --------

    def test_header_multi_company_rule_hides_other_company_movements(self):
        """The header multi-company record rule still hides another
        company's movements (raw SQL, same technique
        `test_counts.py::test_multi_company_record_rule_hides_other_company_lines`
        uses: `company_id` is a related, stored field, not a plain
        column)."""
        company_b = self.env["res.company"].create({"name": "Company B PCDC"})
        header_a = self._create_header(self.session, "opening", total=1)
        header_b = self._create_header(self.session, "opening", total=1)
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE pos_cash_denomination_count SET company_id = %s WHERE id = %s",
            (company_b.id, header_b.id),
        )
        header_b.invalidate_recordset(["company_id"])
        found = (
            self.env["pos.cash.denomination.count"]
            .with_context(allowed_company_ids=[self.env.company.id])
            .search([("id", "in", (header_a | header_b).ids)])
        )
        self.assertEqual(found, header_a)
