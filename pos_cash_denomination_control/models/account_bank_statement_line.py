"""`account.bank.statement.line` extension: the cash-move reason link and
the count-header link.

Backs spec `cash-move-reasons` (Requirement: Reason Storage And `payment_ref`
Composition) and spec `cash-count-records` (the header's
`statement_line_ids` inverse).

`pos_cash_count_id` was deferred from Phase 4: declaring a `Many2one` to
`pos.cash.denomination.count` before that model existed broke the WHOLE
database's registry load with `AssertionError: ... unknown comodel_name
'pos.cash.denomination.count'` (`orm/fields_relational.py:93`, confirmed
empirically against the 19.0 image). Phase 8 creates that model, so the
field is added here now.
"""

from odoo import fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    cash_move_reason_id = fields.Many2one(
        "pos.cash.move.reason", ondelete="restrict", index="btree_not_null"
    )
    pos_cash_count_id = fields.Many2one(
        "pos.cash.denomination.count",
        ondelete="set null",
        index="btree_not_null",
    )
