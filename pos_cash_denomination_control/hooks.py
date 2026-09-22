"""Install-time hooks for pos_cash_denomination_control.

Backs spec `cash-move-reasons` (Requirement: Default Cash-Out Reason On
`pos.config`) and design.md's Hooks section: every `pos.config` record that
existed before install must get `default_cash_out_reason_id` pointing to the
seeded "Vault" reason, since the field's callable default only resolves for
records created after the module (and its seed data) are already installed.

Raw SQL is deliberate here, not `pos.config.write()`: `pos_config.py`'s
`write()` runs `_check_modules_to_install`/`_check_groups_implied`, which can
trigger unrelated side effects on every existing config during install.
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    vault_reason = env.ref(
        "pos_cash_denomination_control.pos_cash_move_reason_vault",
        raise_if_not_found=False,
    )
    if not vault_reason:
        _logger.info(
            "pos_cash_denomination_control: no seeded Vault reason found "
            "(pos_cash_denomination_control.pos_cash_move_reason_vault); "
            "skipping the default_cash_out_reason_id backfill."
        )
        return
    env.cr.execute(
        "UPDATE pos_config SET default_cash_out_reason_id = %s "
        "WHERE default_cash_out_reason_id IS NULL",
        (vault_reason.id,),
    )
    _logger.info(
        "pos_cash_denomination_control: backfilled default_cash_out_reason_id "
        "to the Vault reason on %d existing pos.config row(s).",
        env.cr.rowcount,
    )
    env["pos.config"].invalidate_model(["default_cash_out_reason_id"])
