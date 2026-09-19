from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_allow_cash_in = fields.Boolean(
        related="pos_config_id.allow_cash_in", readonly=False
    )
    pos_vault_withdrawal_threshold = fields.Monetary(
        related="pos_config_id.vault_withdrawal_threshold", readonly=False
    )
    pos_cash_count_opening_required = fields.Boolean(
        related="pos_config_id.cash_count_opening_required", readonly=False
    )
    pos_cash_count_out_required = fields.Boolean(
        related="pos_config_id.cash_count_out_required", readonly=False
    )
    pos_cash_count_in_required = fields.Boolean(
        related="pos_config_id.cash_count_in_required", readonly=False
    )
    pos_cash_count_closing_required = fields.Boolean(
        related="pos_config_id.cash_count_closing_required", readonly=False
    )
