# Deploying to Odoo.sh

This repository ships `pos_cash_denomination_control` at its root, one level
inside the repository (`pos_cash_denomination_control/pos_cash_denomination_control/`)
— OCA-style, no top-level `addons/` folder. On Odoo.sh, this repository is
added as a **git submodule** of the Odoo.sh project's own repository, so
Odoo.sh's own dev/staging/production pipeline builds and tests it like any
other addon. There is no docker-compose runner on Odoo.sh — Odoo.sh has its
own build and test infrastructure, so this addon's own suite
(`scripts/test.sh`) is only used locally and in the pre-install checklist
below, not on Odoo.sh itself.

Source for the submodule mechanics: `odoo/documentation`, 19.0,
`content/administration/odoo_sh/advanced.rst`, "Submodules" section.

## Migration note for implementers

**This module used to be handed over as part of `Dispearson-SC/caja-boveda`**,
on branch `feature/vault-basic`, which carried both `pos_cash_denomination_control`
and `cash_vault` in one repository. That repository has been split: each
module now has its own repository, and `caja-boveda` is retired as the
historical record only.

If your Odoo.sh project already has `caja-boveda` added as a submodule on
`feature/vault-basic`, switch it to this repository instead:

```bash
git submodule deinit -f <old-caja-boveda-path>
git rm -f <old-caja-boveda-path>
git submodule add -b main git@github.com:Dispearson-SC/pos_cash_denomination_control.git <path>
```

`cash_vault` depends on this module and needs its **own** submodule added
the same way — see `cash_vault`'s own `docs/deployment/odoo-sh.md`. Both
submodules are required together if you use `cash_vault`; this module alone
is sufficient if you do not.

## Quick path

1. Register the deploy key **first**, then add this repository as a submodule
   of the Odoo.sh project repository (see
   [Repository-as-submodule setup](#repository-as-submodule-setup)).
2. Push to a dev branch. Odoo.sh builds it and runs this addon's test suite
   automatically (see [Dev branch build behavior](#dev-branch-build-behavior)).
3. Promote to a staging branch — a neutralized copy of production — and run
   the [pre-install / pre-upgrade checklist](#pre-install--pre-upgrade-checklist)
   against it.
4. Only after staging is green, merge to the production branch.

## Repository-as-submodule setup

The addon lives at `pos_cash_denomination_control/` inside this repository,
one level below the repository root (next to `openspec/`, `odd/`, `docs/`
and `scripts/`). Odoo.sh discovers addons through **submodules** of its own
project repository, so this repository is added as one:

**The deploy key comes first.** The 19.0 documentation is explicit — "Before
adding private GitHub repository as a submodule, it is necessary to add a
deploy key" (`odoo_sh/getting_started/settings.rst`). Adding the submodule
first leaves the build unable to fetch it.

**The Odoo.sh UI cannot do this for a private repository.** Its
`Submodule → Run on Odoo.sh` dialog states: "Currently, it is not possible
to add **private** repositories with Odoo.sh. You can nevertheless do so
with Git" (`odoo_sh/advanced.rst`). The submodule must be added from a
terminal, and the URL must be the **SSH** form — `git@github.com:…` — not
HTTPS.

1. On Odoo.sh: **Settings → Submodules**, paste this repository's SSH URL
   (`git@github.com:Dispearson-SC/pos_cash_denomination_control.git`), click
   Add, and copy the generated **Public Key**.
2. On this repository's git host: **Settings → Deploy keys → Add deploy
   key**, paste that public key, and save it read-only. This step happens on
   *this* repository, so whoever owns it must perform it — an implementer
   with Odoo.sh access cannot do it for them.
3. In a clone of the Odoo.sh project repository, on the target branch:

   ```bash
   git submodule add -b main git@github.com:Dispearson-SC/pos_cash_denomination_control.git <path>
   git commit -a && git push
   ```

   `<path>` is the folder the submodule lands in.
4. Odoo.sh rebuilds and automatically adds every submodule's addons to the
   instance's addons path — "the platform automatically detects submodules
   and adds them to your addons path for database installation, provided you
   configure a deploy key" (`odoo_sh/advanced.rst`). No manual addons-path
   configuration is needed.

Directories in this repository without an `__manifest__.py` (`openspec/`,
`odd/`, `docs/`, `scripts/`) are simply not seen as addons, so the whole
repository can be mounted as one submodule without filtering.

## Dev branch build behavior

Every push to an Odoo.sh **development branch** triggers a build that
installs the branch's addons and **runs their tests**. Pushing a commit
under this submodule (including a version bump or a merge from this
repository) to a dev branch therefore re-installs
`pos_cash_denomination_control` and runs its full suite — the same
`--test-tags /pos_cash_denomination_control` set that `scripts/test.sh` uses
locally — as part of that build. A failing test fails the build.

**Production builds do not run tests.** Only dev branches (and, for install
tests, staging branches when explicitly configured to run them) exercise
this addon's suite automatically; a production merge trusts what staging
already proved.

## Staging rollout

Before promoting to production:

1. Create (or reuse) an Odoo.sh **staging branch**. Odoo.sh staging branches
   are neutralized copies of the production database (outgoing emails and
   similar production-only side effects are disabled), so they are safe to
   test destructive operations against.
2. Merge or push the release commit to that staging branch.
3. Run the [pre-install / pre-upgrade checklist](#pre-install--pre-upgrade-checklist)
   against the staging copy before promoting anything to production.
4. Only promote to production once staging is green end to end.

## Pre-install / pre-upgrade checklist

Run this checklist against the staging copy, in order, before promoting the
release to production:

1. **Close every open POS session**, or at minimum confirm no session is
   stuck in `opening_control` with pending offline openings.
2. **Sync every POS device**: bring each one online until its offline-queue
   counter shows nothing pending. The offline queue is **memory-only**
   (confirmed empirically by this addon's own `offline_queue_tour`): a cash
   move confirmed while offline and never synced is lost outright on
   reload, and any pre-upgrade queued cash move that does reach the server
   after the upgrade has no `reason_id` and is rejected on replay, since a
   reason becomes required on every cash move immediately on install.
3. **Back up the database.**
4. **Audit custom and third-party modules** installed on the target
   database for overrides of any of the following extension points, since
   this addon's design relies on being additive at each of them:
   - `try_cash_in_out`
   - `set_opening_control`
   - `post_closing_cash_details`
   - `_validate_session`
   - `_set_opening_control_data`
   - the opening, cash-move, and closing popup templates (`OpeningControlPopup`,
     `CashMovePopup`, `ClosePosPopup`) at the xpath anchors this addon
     patches
   Read `reference/odoo-src/addons/point_of_sale` (workspace read-only
   reference) and any installed third-party addon sources available on the
   target to compile this audit, and record the findings in this document
   before proceeding.
5. **Install on the Enterprise staging database** and run this addon's full
   suite and every browser tour. Enterprise ships its own POS asset
   overrides; a template conflict there breaks the whole POS bundle, not
   just this addon, so this step must run on Enterprise, not Community.
6. **Reload every POS client** after install so it picks up the new assets.
7. **Re-enable cash-in** on the POS configurations that need it (see
   [Cash-in disabled on install](#cash-in-disabled-on-install) below —
   install turns it off everywhere).
8. **Review the default cash-out reason and every vault withdrawal
   threshold** on each POS configuration.

## Cash-in disabled on install

Installing this module sets `allow_cash_in = False` on **every** existing
POS configuration, in addition to new ones — this is a column default, so
it applies unconditionally, not only to configurations an administrator
explicitly opts into. Any POS that relied on cash-in loses it silently
until re-enabled.

To restore cash-in for a POS after install, follow
`pos_cash_denomination_control/readme/CONFIGURE.md`'s "Cash In" section:
**Point of Sale > Configuration > Settings**, open the POS configuration,
and turn on **Cash In** under Cash Control.

## Known conflicts with core test runs

While this module is installed, two core `point_of_sale` test scenarios
fail, because they perform a cash move without a reason and this module
requires one on every cash move as soon as it is installed:

- `odoo/addons/point_of_sale/tests/test_point_of_sale_flow.py:3212`
- `odoo/addons/point_of_sale/static/tests/tours/chrome_tour.js:209`

Run core or OCA CI suites **without** this module installed, or tag the
known conflict, exactly as documented in
`pos_cash_denomination_control/readme/ROADMAP.md`. This is an accepted,
documented cost, not a defect in either suite.

## Release gate

Before promoting a release, re-run the full local suite once more, with and
without `pos_hr`, as a release gate independent of Odoo.sh's own dev-branch
test run:

```bash
scripts/test.sh
scripts/test.sh pos_hr
```

**Last verified in this repository**: `dev/scripts/test.sh
pos_cash_denomination_control` — 61 modules loaded, 0 failed of 171 tests,
standalone.

## Rollback

- **Toggles / thresholds**: turn the relevant toggle off or the vault
  threshold to 0 per POS to restore stock behavior immediately, with no
  data loss.
- **Uninstall**: uninstalling `pos_cash_denomination_control` drops its
  tables, columns, and reason catalog; core `pos.session` and
  `account.bank.statement.line` are unaffected, and existing `payment_ref`
  text and chatter messages remain readable. Export count lines,
  statement-line reasons, and session flags first if that history or a
  future feature needs them. If `cash_vault` is also installed, it must be
  uninstalled first (it depends on this module).

## Handover to implementers

Split of responsibilities:

| Who | Step |
| --- | --- |
| Repository owner | Invite the implementers as collaborators (read is enough). |
| Implementers | On Odoo.sh: Settings → Submodules → paste this repository's SSH URL → copy the generated Public Key. |
| Repository owner | GitHub → Settings → **Deploy keys** → paste that key, read-only. One time. |
| Implementers | `git submodule add -b main …`, push, and let Odoo.sh rebuild. |

The deploy key step cannot be delegated: the key is installed on *this*
repository, which only its owner administers.

An archive (`git archive` of the addon folder) remains possible when the
implementers cannot reach the repository at all, at the cost of losing
history and requiring a fresh archive for every correction.
