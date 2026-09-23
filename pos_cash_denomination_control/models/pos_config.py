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

Backs spec `vault-withdrawal-alert` (Requirement: Vault Withdrawal Threshold
Field): `vault_withdrawal_threshold` is a Monetary field defaulting to `0`
(disabled), with a SQL `CHECK` (same `models.Constraint` style already used
by `pos.cash.move.reason`) as a defense-in-depth layer against a negative
value from any caller that bypasses the ORM.

Backs spec `cash-denomination-config`: the four `cash_count_*_required`
toggles are independent stored Booleans defaulting to `False`, so every
existing config also gets them off the moment the columns are created by
this module's install (same "no post-init hook needed" reasoning as
`allow_cash_in`). Enforcement itself (`cash-denomination-enforcement`) is
Phase 9; this field only decides, per operation type, whether a breakdown
will be required once that enforcement lands.

Backs spec `vault-withdrawal-blocking`: `vault_withdrawal_blocking` is a
stored Boolean defaulting to `False` (same "no post-init hook needed"
reasoning as every other flag above). It is enforced entirely in the POS
client (`static/src/app/screens/payment_screen/payment_screen_patch.js`),
never on the server: this is a WORKFLOW CONTROL, not a security boundary.
POS orders sync after the sale has physically happened, so refusing them at
sync time would destroy real transactions instead of preventing them.
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
    vault_withdrawal_threshold = fields.Monetary(
        currency_field="currency_id",
        default=0,
        help="Expected drawer cash at or above this amount triggers a "
        "non-blocking vault withdrawal alert. Zero disables the alert.",
    )
    cash_count_opening_required = fields.Boolean(
        default=False,
        help="Require a denomination breakdown when opening the session.",
    )
    cash_count_out_required = fields.Boolean(
        default=False,
        help="Require a denomination breakdown for cash-out operations.",
    )
    cash_count_in_required = fields.Boolean(
        default=False,
        help="Require a denomination breakdown for cash-in operations. "
        "Has no effect while cash-in is disabled for this point of sale.",
    )
    cash_count_closing_required = fields.Boolean(
        default=False,
        help="Require a denomination breakdown when closing the session.",
    )
    vault_withdrawal_blocking = fields.Boolean(
        default=False,
        help="Stop validating sales for this point of sale once the "
        "expected drawer cash reaches the vault withdrawal threshold, "
        "until a cash-out brings it back down. Has no effect while the "
        "threshold is zero, since the alert itself is disabled.",
    )

    _vault_withdrawal_threshold_non_negative = models.Constraint(
        "CHECK(vault_withdrawal_threshold >= 0)",
        "The vault withdrawal threshold cannot be negative.",
    )
