from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_allow_cash_in = fields.Boolean(
        related="pos_config_id.allow_cash_in", readonly=False
    )
    pos_vault_withdrawal_threshold = fields.Monetary(
        related="pos_config_id.vault_withdrawal_threshold", readonly=False
    )
