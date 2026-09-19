"""`pos.config` extension: the cash-in toggle and the default cash-out
reason.

Backs spec `cash-in-control`: `allow_cash_in` is a stored Boolean defaulting
to `False`, so every existing config gets `allow_cash_in = False` the moment
the column is created by this module's install, with no post-init hook
needed.

Backs spec `cash-move-reasons` (Requirement: Default Cash-Out Reason On
`pos.config`): `default_cash_out_reason_id`'s callable default resolves the
seeded "Vault" reason for every *newly created* config. Existing configs
need `hooks.py::post_init_hook` to backfill the column, since the field
default cannot resolve seed data before the column itself is created.
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
    default_cash_out_reason_id = fields.Many2one(
        "pos.cash.move.reason",
        string="Default Cash-Out Reason",
        ondelete="restrict",
        check_company=True,
        domain="[('direction', 'in', ('out', 'both')), "
        "('company_id', 'in', [False, company_id])]",
        default=lambda self: self.env.ref(
            "pos_cash_denomination_control.pos_cash_move_reason_vault",
            raise_if_not_found=False,
        ),
        help="Reason preselected in the cash-out popup. Left empty (or "
        "archived), the cashier must pick a reason explicitly.",
    )
