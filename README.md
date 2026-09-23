# pos_cash_denomination_control

Odoo 19 addon: denomination breakdown, cash-move reasons, a per-POS cash-in
toggle, a vault withdrawal alert with optional register blocking, and a
closing-manager override for Point of Sale cash control. See
`pos_cash_denomination_control/readme/DESCRIPTION.md` for the full feature
description.

This repository is one module inside the `odoo-dev` multi-agent workspace.
If you were handed only this repository (e.g. as an Odoo.sh submodule), see
"Standalone use" below.

## Layout

This repository follows an OCA-style layout, with the addon **one level
inside** the repository root (required for Odoo.sh submodule discovery):

| Path | Role |
|------|------|
| `pos_cash_denomination_control/` | The addon Odoo loads. |
| `openspec/` | Specs (`specs/`) and change proposals (`changes/`) for this module. |
| `odd/tasks/` | Task documents for work done under Organic Driven Development. |
| `docs/testing.md` | Full local testing reference. |
| `docs/deployment/odoo-sh.md` | Odoo.sh deployment guide. |
| `docs/history/commit-map.txt` | Maps this module's old commit hashes (from the retired shared repository) to its new, per-module history. |
| `scripts/test.sh` | Test entry point — see below. |

## Running the tests

```bash
scripts/test.sh                    # install + full addon test suite
scripts/test.sh pos_hr             # coexistence run, also installs pos_hr
```

See `docs/testing.md` for the fast domain-only loop, tag-filter syntax, the
Hoot/frontend suite, browser tours, and known gotchas.

## Dependencies

`point_of_sale` only. This module installs and passes its full suite alone.

## Deploying

See `docs/deployment/odoo-sh.md` for the Odoo.sh submodule setup and the
pre-install/pre-upgrade checklist. Inside the `odoo-dev` workspace, deploying
to the two live instances goes through `deploy/deploy.sh` at the workspace
root — see the workspace's `deploy/RUNBOOK.md`, never this repository
directly.

## Standalone use

`scripts/test.sh` only works inside the `odoo-dev` workspace (it delegates
to `../../dev/scripts/test.sh`, the workspace's shared Odoo 19 + Postgres
runner). If you have only this repository — for example as an Odoo.sh
submodule — there is no local docker-compose runner here; Odoo.sh runs this
addon's tests as part of its own dev-branch build. See
`docs/deployment/odoo-sh.md`.
