"""`pos.cash.denomination.count` (header) and
`pos.cash.denomination.count.line` model layer: core fields, snapshot
independence, denormalization, employee attribution, and reporting
(views/security/access).

Covers spec `cash-count-records`. This phase only proves the models are
constructible directly (no enforcement wiring yet — that is Phase 9's
`cash-denomination-enforcement`, which will call `pos.session`'s shared
`_pcdc_create_count` helper to actually persist these records from
`_set_opening_control_data`/`try_cash_in_out`/`post_closing_cash_details`).
"""

from odoo import Command
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import AccessError
from odoo.tests import tagged

from ..domain.breakdown import Breakdown, compute_total, parse_lines


@tagged("pcdc", "pcdc_counts")
class TestCounts(CommonPosTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.allow_cash_in = True
        cls.pos_config_usd.open_ui()
        cls.session = cls.pos_config_usd.current_session_id
        cls.session.set_opening_control(0, False)
        cls.reason = cls.env["pos.cash.move.reason"].create(
            {"name": "Bank Deposit", "direction": "out"}
        )
        cls.bill_1 = cls.env["pos.bill"].create({"name": "1", "value": 1.0})
        cls.bill_5 = cls.env["pos.bill"].create({"name": "5", "value": 5.0})
        # Restricted actor for the ACL boundary tests below: a bare PoS
        # user, same "cashier" pattern used across this suite's other
        # `with_user()` tests (e.g. `test_cash_in_control.py`'s
        # `no_permission_user`, `test_closing_override.py`'s
        # `non_manager`) -- `point_of_sale.group_pos_user` alone still
        # needs `base.group_user` to reach the model at all.
        cls.cashier = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "PoS user (ACL boundary tests)",
                    "login": "pcdc_acl_boundary_cashier",
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

    def _create_header(self, move_type, **extra):
        vals = {
            "session_id": self.session.id,
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

    # -- Header fields -------------------------------------------------

    def test_header_created_with_core_fields(self):
        """Header created with core fields."""
        header = self._create_header("opening", total=10)
        self.assertEqual(header.session_id, self.session)
        self.assertEqual(header.config_id, self.pos_config_usd)
        self.assertEqual(header.company_id, self.session.company_id)
        self.assertEqual(header.move_type, "opening")
        self.assertEqual(header.total, 10)
        self.assertTrue(header.date)
        self.assertEqual(header.user_id, self.env.user)

    def test_opening_header_has_no_reason(self):
        """Opening header has no reason."""
        header = self._create_header("opening", total=10)
        self.assertFalse(header.reason_id)

    def test_cash_move_header_stores_reason_and_statement_line_link(self):
        """Cash move header stores reason and statement line link."""
        self.session.try_cash_in_out(
            "out",
            5,
            "Bank deposit",
            False,
            {"translatedType": "Cash out", "reason_id": self.reason.id},
        )
        line = self.env["account.bank.statement.line"].search(
            [("pos_session_id", "=", self.session.id)], order="id desc", limit=1
        )
        header = self._create_header(
            "out",
            total=5,
            reason_id=self.reason.id,
            statement_line_ids=[Command.link(line.id)],
        )
        self.assertEqual(header.reason_id, self.reason)
        self.assertEqual(header.statement_line_ids, line)

    # -- Line fields and denormalization --------------------------------

    def test_line_snapshot_independent_of_later_bill_value_change(self):
        """Line snapshot is independent of later bill value changes."""
        header = self._create_header("opening", total=10)
        line = self._create_line(header, self.bill_5, 2)
        self.bill_5.value = 200
        self.assertEqual(line.bill_value, 5.0)

    def test_line_subtotal_equals_quantity_times_snapshot_value(self):
        """Line subtotal equals quantity times snapshot value."""
        header = self._create_header("opening", total=150)
        line = self.env["pos.cash.denomination.count.line"].sudo().create(
            {
                "count_id": header.id,
                "bill_id": self.bill_5.id,
                "bill_name": self.bill_5.name,
                "bill_value": 50,
                "quantity": 3,
            }
        )
        self.assertEqual(line.subtotal, 150)

    def test_line_carries_denormalized_header_fields(self):
        """Line carries denormalized header fields."""
        header = self._create_header("out", total=5, reason_id=self.reason.id)
        line = self._create_line(header, self.bill_1, 5)
        self.assertEqual(line.move_type, "out")
        self.assertEqual(line.reason_id, self.reason)

    # -- Employee attribution --------------------------------------------
    #
    # `test_employee_stored_with_pos_hr_installed` used to live here too,
    # but `_pcdc_resolve_employee` now calls `pos.config._employee_domain`
    # (a `pos_hr`-only addition) whenever `hr.employee` is registered and
    # an `employee_id` is given -- see
    # `TestCountsPosHrEmployeeDomain` below for why that must run
    # `post_install` rather than here.

    def test_employee_absent_without_pos_hr_installed(self):
        """Employee absent without pos_hr installed."""
        if "hr.employee" in self.env:
            self.skipTest("only meaningful when hr.employee is not installed")
        employee_id, employee_name = self.session._pcdc_resolve_employee(
            "out", {}
        )
        self.assertFalse(employee_id)
        self.assertFalse(employee_name)

    # -- One header, N lines ---------------------------------------------

    def test_accepted_operation_creates_header_and_lines(self):
        """Accepted operation creates header and lines: exactly one header
        and one line per denomination entry with a quantity greater than
        zero.

        Exercises `pos.session._pcdc_create_count` (the 8.9 REFACTOR
        extraction), the same shared path Phase 9's enforcement and Phase
        10's closing override will call — instead of the manual
        header-then-line construction the earlier `_create_header`/
        `_create_line` helpers use for the other, lower-level model tests
        in this file.
        """
        before_headers = self.env["pos.cash.denomination.count"].sudo().search_count(
            []
        )
        before_lines = self.env["pos.cash.denomination.count.line"].sudo().search_count(
            []
        )
        allowed_bills = {self.bill_1.id: self.bill_1.value, self.bill_5.id: self.bill_5.value}
        breakdown_lines = parse_lines(
            [
                {"bill_id": self.bill_1.id, "quantity": 3},
                {"bill_id": self.bill_5.id, "quantity": 0},
            ],
            allowed_bills,
        )
        breakdown = Breakdown(
            lines=breakdown_lines, total=compute_total(breakdown_lines)
        )
        header = self.session._pcdc_create_count(
            "opening", breakdown, self.bill_1 | self.bill_5
        )

        self.assertEqual(
            self.env["pos.cash.denomination.count"].sudo().search_count([]),
            before_headers + 1,
        )
        self.assertEqual(
            self.env["pos.cash.denomination.count.line"].sudo().search_count([]),
            before_lines + 1,
        )
        self.assertEqual(header.line_ids.bill_id, self.bill_1)
        self.assertEqual(header.line_ids.quantity, 3)

    # -- Reporting: pivot, security, record rules -------------------------

    def test_pivot_groups_by_pos_date_move_type_denomination_reason(self):
        """Pivot groups by POS, date, move type, denomination, and
        reason."""
        header = self._create_header("out", total=5, reason_id=self.reason.id)
        self._create_line(header, self.bill_5, 1)
        Line = self.env["pos.cash.denomination.count.line"].sudo()
        groups = Line._read_group(
            [("id", "in", header.line_ids.ids)],
            ["config_id", "date:day", "move_type", "bill_id", "reason_id"],
            ["quantity:sum"],
        )
        self.assertTrue(groups)
        config_id, _date, move_type, bill_id, reason_id, quantity_sum = groups[0]
        self.assertEqual(config_id, self.pos_config_usd)
        self.assertEqual(move_type, "out")
        self.assertEqual(bill_id, self.bill_5)
        self.assertEqual(reason_id, self.reason)
        self.assertEqual(quantity_sum, 1)

    def test_multi_company_record_rule_hides_other_company_lines(self):
        """Multi-company record rule hides other company's lines.

        `company_id` is a related, stored field derived from
        `session_id.company_id`, not a plain column — unlike
        `pos.cash.move.reason.company_id` (Phase 4's test), it cannot be
        assigned directly without writing through to the shared
        `self.session`'s own company. A raw SQL update simulates a line
        that belongs to a different company, the same technique already
        used in `tests/test_install.py` to simulate pre-existing state,
        without provisioning a full second-company POS session.
        """
        company_b = self.env["res.company"].create({"name": "Company B"})
        header_a = self._create_header("opening", total=1)
        line_a = self._create_line(header_a, self.bill_1, 1)
        header_b = self._create_header("opening", total=1)
        line_b = self._create_line(header_b, self.bill_1, 1)
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE pos_cash_denomination_count_line SET company_id = %s "
            "WHERE id = %s",
            (company_b.id, line_b.id),
        )
        line_b.invalidate_recordset(["company_id"])
        found = (
            self.env["pos.cash.denomination.count.line"]
            .with_context(allowed_company_ids=[self.env.company.id])
            .search([("id", "in", (line_a | line_b).ids)])
        )
        self.assertEqual(found, line_a)

    def test_user_without_pos_reporting_access_is_denied(self):
        """User without POS reporting access is denied."""
        header = self._create_header("opening", total=1)
        self._create_line(header, self.bill_1, 1)
        no_access_user = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "User without POS reporting access",
                    "login": "pcdc_no_reporting_user",
                    "group_ids": [Command.set([self.env.ref("base.group_user").id])],
                }
            )
        )
        with self.assertRaises(AccessError):
            self.env["pos.cash.denomination.count.line"].with_user(
                no_access_user
            ).search([])

    # -- ACL boundary: create/write/unlink are 0 for every group ---------
    #
    # `ir.model.access.csv` grants `perm_create=perm_write=perm_unlink=0`
    # for both `point_of_sale.group_pos_user` and
    # `point_of_sale.group_pos_manager` on both models below, by design:
    # only `_pcdc_create_count`'s `.sudo()` may write them. No existing
    # test asserted this boundary directly before now -- every other
    # fixture in this file creates these records through `.sudo()`.

    def test_non_privileged_user_cannot_create_write_or_unlink_count_header(
        self,
    ):
        """A restricted PoS user can neither `create()`, `write()`, nor
        `unlink()` a `pos.cash.denomination.count` directly."""
        header = self._create_header("opening", total=1)
        with self.assertRaises(AccessError):
            self.env["pos.cash.denomination.count"].with_user(self.cashier).create(
                {
                    "session_id": self.session.id,
                    "move_type": "opening",
                    "total": 1,
                    "user_id": self.env.user.id,
                }
            )
        with self.assertRaises(AccessError):
            header.with_user(self.cashier).write({"total": 2})
        with self.assertRaises(AccessError):
            header.with_user(self.cashier).unlink()

    def test_non_privileged_user_cannot_create_write_or_unlink_count_line(
        self,
    ):
        """Same ACL boundary as above, for
        `pos.cash.denomination.count.line`."""
        header = self._create_header("opening", total=1)
        line = self._create_line(header, self.bill_1, 1)
        with self.assertRaises(AccessError):
            self.env["pos.cash.denomination.count.line"].with_user(
                self.cashier
            ).create(
                {
                    "count_id": header.id,
                    "bill_id": self.bill_1.id,
                    "bill_name": self.bill_1.name,
                    "bill_value": self.bill_1.value,
                    "quantity": 1,
                }
            )
        with self.assertRaises(AccessError):
            line.with_user(self.cashier).write({"quantity": 2})
        with self.assertRaises(AccessError):
            line.with_user(self.cashier).unlink()

    def test_filter_statement_lines_by_reason(self):
        """Filter statement lines by reason."""
        other_reason = self.env["pos.cash.move.reason"].create(
            {"name": "Till Top-Up", "direction": "out"}
        )
        self.session.try_cash_in_out(
            "out",
            5,
            "Test",
            False,
            {"translatedType": "Cash out", "reason_id": self.reason.id},
        )
        self.session.try_cash_in_out(
            "out",
            7,
            "Test",
            False,
            {"translatedType": "Cash out", "reason_id": other_reason.id},
        )
        found = self.env["account.bank.statement.line"].search(
            [
                ("pos_session_id", "=", self.session.id),
                ("cash_move_reason_id", "=", self.reason.id),
            ]
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(found.cash_move_reason_id, self.reason)


@tagged("post_install", "-at_install", "pcdc", "pcdc_counts")
class TestCountsPosHrEmployeeDomain(CommonPosTest):
    """`_pcdc_resolve_employee`'s `pos.config._employee_domain` guard
    (the fix for the forgeable-attribution finding), which only exists
    once `pos_hr` is actually loaded.

    `post_install`/`-at_install` (same reasoning as `test_hoot.py`'s own
    docstring): `pos_cash_denomination_control`'s `at_install` tests run
    immediately once *this* module finishes loading, which in the
    `pos_hr` coexistence run (`scripts/test.sh pos_hr`) can happen before
    `pos_hr` itself has loaded, even though `hr.employee` (added by the
    separate `hr` module) is already registered -- confirmed empirically:
    an `at_install` version of these tests hit
    `AttributeError: 'pos.config' object has no attribute
    '_employee_domain'` because `pos_hr`'s own `pos.config` extension
    had not loaded yet. `post_install` runs only after every requested
    module has finished loading, so `pos_hr` (when present) is always
    fully installed by the time these run.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.open_ui()
        cls.session = cls.pos_config_usd.current_session_id
        cls.session.set_opening_control(0, False)
        cls.reason = cls.env["pos.cash.move.reason"].create(
            {"name": "Bank Deposit", "direction": "out"}
        )
        cls.bill_1 = cls.env["pos.bill"].create({"name": "1", "value": 1.0})

    def test_employee_stored_with_pos_hr_installed(self):
        """Employee stored with pos_hr installed.

        Moved here (from `TestCounts`, an `at_install` class) once
        `_pcdc_resolve_employee` started calling
        `pos.config._employee_domain`: that `pos_hr`-only method is not
        yet present during `TestCounts`'s own `at_install` phase in the
        `pos_hr` coexistence run (confirmed empirically -- see this
        class's own docstring), even though `hr.employee` (from the
        separate `hr` module) already is.
        """
        if "hr.employee" not in self.env:
            self.skipTest("requires pos_hr (hr.employee not installed)")
        # Fixture setup only: the POS test user has no rights on hr models.
        employee = self.env["hr.employee"].sudo().create({"name": "Test Employee"})
        employee_id, employee_name = self.session._pcdc_resolve_employee(
            "out", {"employee_id": employee.id}
        )
        self.assertEqual(employee_id, employee.id)
        self.assertEqual(employee_name, employee.name)

    def test_cash_move_with_employee_from_another_company_is_rejected(self):
        """Cash move with an `employee_id` from another company is
        rejected, and no count header is created.

        `extras['employee_id']` is caller-supplied (the key `pos_hr`'s own
        `CashMovePopup` patch injects into `try_cash_in_out`'s payload,
        never a server-side guarantee), so `_pcdc_resolve_employee` must
        constrain it to `pos.config._employee_domain` before trusting it
        for the count's audit trail -- otherwise any cash move could name
        an employee from an unrelated company. This only exercises the
        `hr.employee` branch, so it only runs under the `pos_hr`
        coexistence suite (`scripts/test.sh pos_hr`); see
        `TestCounts.test_employee_absent_without_pos_hr_installed` for the
        mirror skip. Uses a manual try/except rather than `assertRaises`
        (`BaseCase.assertRaises` rolls back its own savepoint) so the
        header count can still be checked afterward.
        """
        if "hr.employee" not in self.env:
            self.skipTest("requires pos_hr (hr.employee not installed)")
        other_company = self.env["res.company"].create({"name": "Other Co (PCDC test)"})
        foreign_employee = self.env["hr.employee"].sudo().create(
            {"name": "Foreign Employee", "company_id": other_company.id}
        )
        self.pos_config_usd.cash_count_out_required = True
        before_count = self.env["pos.cash.denomination.count"].sudo().search_count([])
        raised = False
        try:
            self.session.try_cash_in_out(
                "out",
                1,
                "Test",
                False,
                {
                    "translatedType": "Cash out",
                    "reason_id": self.reason.id,
                    "denomination_lines": [
                        {"bill_id": self.bill_1.id, "quantity": 1}
                    ],
                    "employee_id": foreign_employee.id,
                },
            )
        except AccessError:
            raised = True
        self.assertTrue(raised)
        self.assertEqual(
            self.env["pos.cash.denomination.count"].sudo().search_count([]),
            before_count,
        )

    def test_cash_move_with_employee_from_same_company_is_accepted_and_stamped(
        self,
    ):
        """A legitimate `employee_id` (same company, no allow-list
        configured on the config) is still accepted and still stamps
        `employee_ref`/`employee_name` on the header -- the happy path
        this fix must not break."""
        if "hr.employee" not in self.env:
            self.skipTest("requires pos_hr (hr.employee not installed)")
        employee = self.env["hr.employee"].sudo().create({"name": "Local Employee"})
        self.pos_config_usd.cash_count_out_required = True
        self.session.try_cash_in_out(
            "out",
            1,
            "Test",
            False,
            {
                "translatedType": "Cash out",
                "reason_id": self.reason.id,
                "denomination_lines": [{"bill_id": self.bill_1.id, "quantity": 1}],
                "employee_id": employee.id,
            },
        )
        header = (
            self.env["pos.cash.denomination.count"]
            .sudo()
            .search(
                [("session_id", "=", self.session.id), ("move_type", "=", "out")],
                order="id desc",
                limit=1,
            )
        )
        self.assertEqual(header.employee_ref, employee.id)
        self.assertEqual(header.employee_name, employee.name)
