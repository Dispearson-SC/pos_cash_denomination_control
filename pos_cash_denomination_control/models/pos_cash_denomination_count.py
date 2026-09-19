"""`pos.cash.denomination.count`: the header record for one accepted,
counted operation (opening, cash IN, cash OUT, or closing).

Backs spec `cash-count-records`. See design.md's Data Model section for the
field table. Per design.md, the header grants no create/write/unlink access
to any group — every write goes through adapter code in `sudo()`
(`pos.session._pcdc_create_count`, added in this same phase as a
forward-looking helper for Phase 9's enforcement wiring). This phase only
proves the model is constructible directly; nothing calls it yet.
"""

from odoo import fields, models


class PosCashDenominationCount(models.Model):
    _name = "pos.cash.denomination.count"
    _description = "POS Cash Denomination Count"
    _order = "date desc, id desc"

    session_id = fields.Many2one(
        "pos.session", required=True, ondelete="cascade", index=True
    )
    config_id = fields.Many2one(
        related="session_id.config_id", store=True, index=True
    )
    company_id = fields.Many2one(
        related="session_id.company_id", store=True, index=True
    )
    currency_id = fields.Many2one(related="session_id.currency_id")
    move_type = fields.Selection(
        [
            ("opening", "Opening"),
            ("in", "Cash In"),
            ("out", "Cash Out"),
            ("closing", "Closing"),
        ],
        required=True,
        index=True,
    )
    total = fields.Monetary(currency_field="currency_id")
    date = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    user_id = fields.Many2one("res.users", required=True)
    employee_ref = fields.Integer(
        help="Soft reference to hr.employee.id (design.md ADR-8) — no hard "
        "dependency on hr/pos_hr."
    )
    employee_name = fields.Char(help="Snapshot of the employee's name.")
    reason_id = fields.Many2one(
        "pos.cash.move.reason",
        ondelete="restrict",
        index=True,
        help="Populated only for cash IN/OUT move types.",
    )
    note = fields.Text()
    statement_line_ids = fields.One2many(
        "account.bank.statement.line", "pos_cash_count_id"
    )
    line_ids = fields.One2many("pos.cash.denomination.count.line", "count_id")

    _total_non_negative = models.Constraint(
        "CHECK(total >= 0)", "The counted total cannot be negative."
    )
