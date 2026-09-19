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


def post_init_hook(env):
    vault_reason = env.ref(
        "pos_cash_denomination_control.pos_cash_move_reason_vault",
        raise_if_not_found=False,
    )
    if not vault_reason:
        return
    env.cr.execute(
        "UPDATE pos_config SET default_cash_out_reason_id = %s "
        "WHERE default_cash_out_reason_id IS NULL",
        (vault_reason.id,),
    )
    env["pos.config"].invalidate_model(["default_cash_out_reason_id"])
