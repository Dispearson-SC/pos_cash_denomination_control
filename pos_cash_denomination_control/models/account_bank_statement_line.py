"""`account.bank.statement.line` extension: the cash-move reason link.

Backs spec `cash-move-reasons` (Requirement: Reason Storage And `payment_ref`
Composition).

Design.md also calls for `pos_cash_count_id` (a link to the count header
added in Phase 8) to be declared here already, "populate it starting Phase
8". That is not possible: Odoo's field setup asserts the comodel is already
a registered model (`orm/fields_relational.py:93`,
`assert self.comodel_name in model.pool`), confirmed empirically against the
19.0 image — declaring a `Many2one` to `pos.cash.denomination.count` before
that model exists breaks the WHOLE database's registry load with
`AssertionError: ... unknown comodel_name 'pos.cash.denomination.count'`,
not just this addon. `pos_cash_count_id` is added in Phase 8, when the
comodel is created.
"""

from odoo import fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    cash_move_reason_id = fields.Many2one(
        "pos.cash.move.reason", ondelete="restrict", index="btree_not_null"
    )
