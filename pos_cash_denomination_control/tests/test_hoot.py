"""Permanent Hoot HttpCase runner for this addon's frontend unit tests.

Backs design.md's Testing Strategy ("Hoot runner: `tests/test_hoot.py` is an
`HttpCase` that runs `browser_js` on
`/web/tests?headless&loglevel=2&preset=desktop&filter=@pos_cash_denomination_control`
with the Hoot success signal") and Phase 1 task 1.7's confirmed URL
parameters and success signal (see `docs/testing.md`).

Pulled forward from Phase 13 so `scripts/test.sh`'s full default run
actually exercises the addon's Hoot suite (currently the 4 cash-in popup
tests in `static/tests/unit/cash_move_popup_cash_in.test.js`), instead of
relying on a throwaway harness recreated ad hoc for verification, as Phase
3's apply-progress documented.

`post_install`/`-at_install` matches the tagging `point_of_sale`'s own
`TestUi` tour tests use (`odoo-src/addons/point_of_sale/tests/test_frontend.py:632`),
since the asset bundles under test must be built after every module in the
test database has finished installing. Per `docs/testing.md`'s confirmed
tag-union behavior, `@tagged()` only adds/removes the listed tags on top of
the `standard` default, so this test still matches the bare
`--test-tags /pos_cash_denomination_control` filter `scripts/test.sh` uses.
"""

from odoo.addons.web.tests.test_js import unit_test_error_checker
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "pcdc", "pcdc_hoot")
class TestHoot(HttpCase):
    def test_hoot_suite(self):
        """The addon's Hoot unit-test suite passes headlessly in Chrome."""
        self.browser_js(
            "/web/tests?headless&loglevel=2&preset=desktop"
            "&filter=@pos_cash_denomination_control",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )
