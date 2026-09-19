"""Install-time defaults for `pos.config`.

Covers spec `cash-in-control`: "Existing POS config has cash-in off after
install". The "New POS config has cash-in off by default" scenario for a
freshly created record lives in `tests/test_cash_in_control.py`.
"""

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.tests import tagged


@tagged("pcdc", "pcdc_cash_in")
class TestInstall(CommonPosTest):
    def test_existing_pos_config_cash_in_off_after_install(self):
        """A POS config that existed before this module was installed must
        have `allow_cash_in` set to `False` (column default applies to every
        existing row when the module is installed)."""
        self.assertFalse(self.pos_config_usd.allow_cash_in)
