# pos_cash_denomination_control — module rules

This is an independent git repository, one of several under the
`odoo-dev` workspace's `addons/`. Read the workspace root's `CLAUDE.md`
first (loaded automatically alongside this file) for the rules shared by
every module. This file covers only what is specific to this one.

## What this module does

Denomination breakdown, cash-move reasons, a per-POS cash-in toggle, a
vault withdrawal alert with optional register blocking, and a
closing-manager override for Point of Sale cash control. See
`pos_cash_denomination_control/readme/DESCRIPTION.md` for the shipped
feature description and `openspec/specs/*/spec.md` for the detailed
specification of each capability (`cash-denomination-config`,
`cash-denomination-enforcement`, `denomination-breakdown-domain`,
`pos-denomination-ui`, `cash-move-reasons`, `cash-in-control`,
`closing-manager-override`, `vault-withdrawal-alert`, `cash-count-records`).

**Behavior change on install**: cash-in is disabled by default on every
existing and new POS configuration, and every POS's default cash-out reason
is set to the seeded "Vault" reason. See
`pos_cash_denomination_control/readme/CONFIGURE.md` to re-enable cash-in.

## What this module does NOT do

- No cashier-level permission tiers for vault withdrawals — see "Deferred:
  cashier vault-withdrawal permission" below.
- No server-side enforcement of the register-blocking feature — see
  "Register blocking is a workflow control, by design" below.
- No per-branch or per-vault confidentiality scoping (that lives, if at
  all, in `cash_vault`).

## Dependencies

`point_of_sale` only. This module must install and pass its full test suite
**alone** — verified: 61 modules loaded, 0 failed of 171 tests. `cash_vault`
depends on this module; this module must never depend back on `cash_vault`.

## Specs and tasks

- `openspec/specs/` — the specification for each shipped capability.
- `openspec/changes/` — change proposals, including the archived
  `2026-09-19-pos-cash-denomination-control` initial build.
- `odd/tasks/` — task documents for work done under Organic Driven
  Development: `vault-withdrawal-blocking.md`, `cashier-vault-withdrawal.md`
  (deferred, see below), `denomination-count-reports.md`,
  `spanish-translations.md`.

## Testing

```bash
scripts/test.sh                                                          # full suite
scripts/test.sh pos_hr                                                   # coexistence run with pos_hr
scripts/test.sh "" -- --test-tags pcdc_domain/pos_cash_denomination_control   # fast domain-only loop
scripts/test.sh "" -- --test-tags /pos_cash_denomination_control:TestHoot     # frontend/Hoot suite only
scripts/test.sh "" -- --test-tags /pos_cash_denomination_control:TestPcdcHttpCommon  # browser tours only
```

`scripts/test.sh` is a thin wrapper over the workspace's shared
`dev/scripts/test.sh pos_cash_denomination_control`; the test database is
`test_pos_cash_denomination_control`. Run in the **foreground** with an
explicit timeout — see the workspace `CLAUDE.md`. Full detail (Hoot suite,
tag-filter syntax, coexistence run, browser tours) is in `docs/testing.md`.

**Known conflict with core**: while this module is installed, two core
`point_of_sale` tests no longer pass, because they assert stock behavior this
module deliberately changes:

- `TestPointOfSaleFlow.test_close_session_cash_out_without_accounting_rights`
  (`tests/test_point_of_sale_flow.py`) — calls `try_cash_in_out` without a
  `reason_id`, which this module rejects.
- `TestUi.test_cash_in_out` (`tests/test_frontend.py`, runs the
  `test_cash_in_out` tour in `chrome_tour.js`) — performs cash moves without
  choosing a reason, and its cash-in step is also refused because
  `allow_cash_in` defaults to `False`.

This is an accepted cost, not a defect in either suite. Secure-by-default
rules (reason required, cash-in off) were chosen over making them opt-in just
to keep these core tests green. When core tests run with this module
installed, exclude exactly these two:

```
--test-tags '-/point_of_sale:TestPointOfSaleFlow.test_close_session_cash_out_without_accounting_rights,-/point_of_sale:TestUi.test_cash_in_out'
```

Re-check the names on every Odoo upgrade; do not add further exclusions
without confirming they share this cause.

## Module-specific traps

- **Register blocking is a workflow control, by design — not a security
  boundary.** `vault_withdrawal_blocking` stops the POS client from
  validating a sale once expected cash reaches the threshold, but it is
  enforced entirely client-side. Server-side rejection was deliberately
  **not** pursued: POS orders sync after the sale has physically happened,
  so refusing them at sync time would destroy real transactions rather than
  prevent them — worse than the problem. Do not "harden" this into a
  server-side check without re-reading
  `odd/tasks/vault-withdrawal-blocking.md`'s reasoning first, and never
  present it to a user as tamper-proof.

- **Deferred: cashier vault-withdrawal permission.** By default, ordinary
  cashiers (`point_of_sale.group_pos_user`) cannot move any cash at all —
  `_has_cash_move_permission()` requires `group_pos_manager` or
  `account.group_account_invoice`. A design exists to let ordinary cashiers
  send cash to the vault *only* (never other cash-out reasons, never
  cash-in), enforced server-side in `pos.session.try_cash_in_out`, in
  `odd/tasks/cashier-vault-withdrawal.md` — but it is **not implemented**.
  It is deferred into a future permissions feature. Without it, the
  register-blocking feature above has a dead end: a cashier with no
  cash-move permission, on a blocked register, can neither sell nor perform
  the withdrawal that would unblock it. That dead end is handled today with
  its own "ask a supervisor" message (T4 in
  `odd/tasks/vault-withdrawal-blocking.md`), not with a permission grant.

- **`CashMovePopup.confirm()` is a deliberate full duplicate of core's
  method.** Core's `cash_move_popup.js` calls `_t(type)` on the runtime
  variable `"in"`/`"out"`, which Odoo's string extractor can never pick up
  (see `docs/lessons.md`, "`_t(variable)` is never extracted"). There is no
  seam to patch just that one line, so this module's `confirm()` override
  copies core's entire method with only that one line replaced by a
  `translateCashMoveType()` helper mapping to real literals. **Sync risk,
  documented in the code**: any future core change to `confirm()` must be
  manually re-applied here; this override does not compose with core via
  `super()` for that method body. Check this override against core's
  current `confirm()` before upgrading the Odoo version this module targets.

- **Translation gotchas** (see `docs/lessons.md` for the general rules):
  regenerating a `.pot` before the source file that introduces a new string
  exists ships that string untranslated forever, even with a green test
  suite — verify with
  `odoo.tools.translate.code_translations.get_web_translations(module, lang)`,
  not by reading the `.po` file. `msgmerge` has fuzzy-matched several
  entries onto a wrong neighbour's meaning in this module's history (e.g.
  "Amount" onto "Conteo"); always read fuzzy matches by hand.

- **Cashier-facing dialogs must not reveal sensitive figures.** The
  register-blocked dialog originally named the exact expected drawer cash
  and the vault threshold; this was a confidentiality defect, fixed by
  replacing both dialog bodies with fixed, amount-free sentences (see
  `odd/tasks/vault-withdrawal-blocking.md`, task T6). When touching that
  dialog again, assert the **absence** of `formatCurrency(...)` output in
  its body, not only the presence of new text.

- **Test-tag syntax**: Odoo's `--test-tags` grammar is
  `[+-]tag[/module][:class][.method]` — tag first, then `/module`, then
  `:class`. Writing `/module:tag` instead of `tag/module` silently matches
  zero tests and exits 0. Always check the reported test count is greater
  than zero.
