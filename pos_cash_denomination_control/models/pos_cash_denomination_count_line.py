"""`pos.cash.denomination.count.line`: one denomination entry (bill/coin
value and quantity) of a `pos.cash.denomination.count` header.

Backs spec `cash-count-records`. Snapshots `bill_name`/`bill_value` at count
time so a later change to `pos.bill.value` never rewrites history, and
denormalizes the header's session/config/company/move type/date/reason/user
onto the line so pivot and graph views can group directly on lines without
joining to the header (design.md Data Model).
"""

from odoo import api, fields, models


class PosCashDenominationCountLine(models.Model):
    _name = "pos.cash.denomination.count.line"
    _description = "POS Cash Denomination Count Line"
    _order = "bill_value desc, id"

    count_id = fields.Many2one(
        "pos.cash.denomination.count", required=True, ondelete="cascade", index=True
    )
    bill_id = fields.Many2one(
        "pos.bill",
        ondelete="set null",
        help="Stock bill deletion is not blocked; the snapshot fields "
        "below keep the historical name/value.",
    )
    bill_name = fields.Char()
    bill_value = fields.Float(digits=(16, 4))
    quantity = fields.Integer()
    subtotal = fields.Monetary(
        currency_field="currency_id", compute="_compute_subtotal", store=True
    )

    session_id = fields.Many2one(
        related="count_id.session_id", store=True, index=True
    )
    config_id = fields.Many2one(related="count_id.config_id", store=True, index=True)
    company_id = fields.Many2one(
        related="count_id.company_id", store=True, index=True
    )
    currency_id = fields.Many2one(related="count_id.currency_id", store=True)
    move_type = fields.Selection(
        related="count_id.move_type", store=True, index=True
    )
    date = fields.Datetime(related="count_id.date", store=True, index=True)
    reason_id = fields.Many2one(
        related="count_id.reason_id", store=True, index=True
    )
    user_id = fields.Many2one(related="count_id.user_id", store=True)
    employee_name = fields.Char(related="count_id.employee_name", store=True)

    _quantity_non_negative = models.Constraint(
        "CHECK(quantity >= 0)", "The counted quantity cannot be negative."
    )
    _count_bill_unique = models.Constraint(
        "UNIQUE(count_id, bill_id)",
        "A denomination can only appear once per count.",
    )

    @api.depends("quantity", "bill_value")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = (line.quantity or 0) * (line.bill_value or 0.0)

    def action_open_session(self):
        """Open this line's session form (feature document
        `denomination-count-reports.md`'s line-report "Open session"
        control). `session_id` is a related, stored field, so it is
        available directly on the line without loading `count_id`."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.session_id.display_name,
            "res_model": "pos.session",
            "res_id": self.session_id.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }
