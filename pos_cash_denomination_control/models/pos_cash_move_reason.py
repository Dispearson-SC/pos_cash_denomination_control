"""`pos.cash.move.reason`: the cash-move reason catalog.

Backs spec `cash-move-reasons`. See design.md's Data Model section for the
field table and `specs/cash-move-reasons/spec.md`'s "Vault Reasons Must Be
Out-Only" requirement, enforced three ways: an early `create`/`write` guard
(so an ordinary ORM call gets the translated `ValidationError` the spec
requires), an `@api.constrains` safety net, and a SQL `CHECK` (same style as
`pos_note.py`'s `models.Constraint`) as the final defense-in-depth layer for
anything that bypasses the ORM.

Empirically confirmed (Odoo 19.0 image) that the SQL `CHECK` alone is not
enough to satisfy the spec: Postgres evaluates `CHECK` constraints
synchronously on `INSERT`/`UPDATE`, which happens before `_validate_fields`
runs `@api.constrains` in `create()`/`write()`. An ordinary ORM `create()`
call (outside the XML/CSV data-import loader, the only caller of
`_sql_error_to_message`) therefore raises a raw, untranslated
`psycopg2.errors.CheckViolation` before the Python constrain ever executes.
The early guard below validates the incoming values before delegating to
`super()`, so the SQL layer is never reached for an ordinary invalid call.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..domain.errors import ReasonError
from ..domain.reasons import validate_reason_definition
from .domain_errors import raise_domain_error


class PosCashMoveReason(models.Model):
    _name = "pos.cash.move.reason"
    _description = "POS Cash Move Reason"
    _inherit = ["pos.load.mixin"]
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    direction = fields.Selection(
        [("out", "Out"), ("in", "In"), ("both", "Both")],
        required=True,
        default="out",
    )
    is_vault = fields.Boolean(
        string="Vault",
        help="A vault reason can only be used for cash-out operations.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        index=True,
        help="Leave empty to share this reason across every company.",
    )

    _is_vault_out_only = models.Constraint(
        "CHECK(NOT is_vault OR direction = 'out')",
        "A vault reason must have direction 'Out'.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_vault_direction_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        if "is_vault" in vals or "direction" in vals:
            for reason in self:
                merged = {"is_vault": reason.is_vault, "direction": reason.direction}
                merged.update(vals)
                self._check_vault_direction_vals(merged)
        return super().write(vals)

    @api.model
    def _check_vault_direction_vals(self, vals):
        try:
            validate_reason_definition(
                vals.get("direction", "out"), vals.get("is_vault", False)
            )
        except ReasonError as exc:
            raise_domain_error(exc, exc_class=ValidationError)

    @api.constrains("is_vault", "direction")
    def _check_vault_direction(self):
        for reason in self:
            try:
                validate_reason_definition(reason.direction, reason.is_vault)
            except ReasonError as exc:
                raise_domain_error(exc, exc_class=ValidationError)

    def _to_domain_snapshot(self):
        """Build a `domain.reasons.ReasonSnapshot` from this record."""
        self.ensure_one()
        from ..domain.reasons import ReasonSnapshot

        return ReasonSnapshot(
            id=self.id,
            active=self.active,
            company_id=self.company_id.id or None,
            direction=self.direction,
            is_vault=self.is_vault,
        )

    @api.model
    def _load_pos_data_domain(self, data, config):
        return [("company_id", "in", [False, config.company_id.id])]

    @api.model
    def _load_pos_data_fields(self, config):
        return ["id", "name", "direction", "is_vault", "sequence", "company_id"]
