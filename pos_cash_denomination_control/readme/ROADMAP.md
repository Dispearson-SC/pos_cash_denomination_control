## Known Conflicts With Core Test Suites

Once this module requires a reason on every cash move
(`specs/cash-move-reasons/spec.md`), two core `point_of_sale` test scenarios
that call `try_cash_in_out` / open the cash-move popup without picking a
reason no longer pass while this module is installed:

- `odoo/addons/point_of_sale/tests/test_point_of_sale_flow.py:3212` — calls a
  cash-move flow with no reason.
- `odoo/addons/point_of_sale/static/tests/tours/chrome_tour.js:209` — a tour
  step that performs a cash IN with only a free-text reason, no reason
  selection.

Run core/OCA CI suites **without** this module installed, or tag the known
conflict, when validating an Odoo upgrade or a third-party module against
core's own test suite.

## Future Work

- A bridge module (`pos_cash_denomination_control_hr`, auto-install) could
  replace the soft `employee_ref` reference on
  `pos.cash.denomination.count` with a real `hr.employee` Many2one once
  `pos_hr` is installed, without a data migration.
