"""`pos.config` extension: the cash-in toggle.

Backs spec `cash-in-control`: the field is a stored Boolean defaulting to
`False`, so every existing config gets `allow_cash_in = False` the moment the
column is created by this module's install, with no post-init hook needed.
"""

from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    allow_cash_in = fields.Boolean(
        default=False,
        help="Allow cash-in operations for this point of sale. Off by "
        "default, including for every point of sale that existed before "
        "this module was installed.",
    )
