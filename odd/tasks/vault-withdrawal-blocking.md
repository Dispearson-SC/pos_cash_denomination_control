# Blocking cash register when the vault threshold is reached

## Objective

Add a per-POS option that **stops the register from selling** once the
drawer's expected cash reaches the vault withdrawal threshold, until a
cash-out brings it back down.

## Why

`vault_withdrawal_threshold` today raises a non-blocking alert: a navbar
indicator and a one-off notification. A busy cashier can ignore it
indefinitely, which is exactly the situation the threshold exists to
prevent — too much cash sitting in a drawer across twelve branches.

The user asked for this explicitly, and chose full blocking over the
narrower alternatives when asked: *"bloquear que se siga vendiendo hasta que
se retire dinero de caja"*.

## The decision and its cost, recorded honestly

Three options were put to the user:

| Option | Effect |
| --- | --- |
| Block cash payments only | Card sales continue; only the drawer stops growing |
| **Block validating any sale** | **Chosen.** Nothing can be charged until the withdrawal happens |
| Block opening a new order | Orders in flight still settle; the drawer can still grow |

The user chose the strictest. The cost is real and must not be hidden: at
peak hours a queue waits while someone performs the withdrawal, **including
customers who were going to pay by card and add no cash at all**. That is a
deliberate business choice, not an oversight.

## Scope

`pos_cash_denomination_control` only. No change to `cash_vault`, no change
to security groups or ACLs.

## What this is, and what it is NOT

This is a **workflow control**, not a security boundary.

The threshold state itself is authoritative — it comes from the server via
`pos.session.get_vault_withdrawal_state`, so a cashier cannot fake being
under the limit. But the block itself is enforced in the POS client, and a
client-side block can be bypassed by anyone willing to open developer
tools.

Server-side rejection was considered and is deliberately **not** pursued:
POS orders sync after the sale has physically happened, so refusing them at
sync time would destroy real transactions rather than prevent them. That is
worse than the problem.

This distinction matters in this project specifically: its root defect class
was trusting `readonly=True`, a client-side hint the server does not
enforce. Do not let anyone read this feature as tamper-proof.

## Design

- **New field** `pos.config.vault_withdrawal_blocking`, Boolean, default
  `False`. Off by default, consistent with every other flag this addon adds
  (`allow_cash_in`, the four `cash_count_*_required`).
- **Exposed per POS** in the existing `pcdc_cash_section` block of
  `res_config_settings`, beside `pos_vault_withdrawal_threshold`, through a
  `related` field with `readonly=False` like its siblings.
- **Meaningless without a threshold.** `vault_withdrawal_threshold = 0`
  disables the alert entirely, so blocking can never fire. The setting must
  make that visible rather than letting someone switch on a block that
  silently does nothing.
- **Enforced at payment validation**, refusing with a clear message that
  names the amount and the threshold.
- **The block lifts by itself** once a cash-out brings expected cash below
  the threshold; `PosStore.refreshVaultState` already recomputes this. No
  manual unlock, no new state to reset.
- **Always offer the way out** in the same interaction: open the cash move
  popup in `out` mode with the vault reason preselected, reusing
  `VaultAlertIndicator.preselectedVaultReasonId()` rather than duplicating
  that resolution rule.

## The dead-end case — it is the DEFAULT, not an edge case

`VaultAlertIndicator.onClick` already refuses when `pos.showCashMoveButton`
is false, because the user lacks the stock cash-move permission.

A cashier **without** that permission, on a blocked register, cannot sell
and cannot perform the withdrawal either. They would be stuck with no
action available to them.

The user believed every cashier can move cash. That was checked against
Odoo's own source rather than assumed, and it does not hold.
`point_of_sale/models/res_users.py`:

```python
def _has_cash_move_permission(self):
    return self.has_group('point_of_sale.group_pos_manager') \
        or self.has_group('account.group_account_invoice')
```

An ordinary cashier holds `point_of_sale.group_pos_user`, which appears in
neither branch. Group membership on the live Enterprise instance at the
time of writing:

| Group | Users |
| --- | --- |
| `point_of_sale.group_pos_manager` | 3 |
| `account.group_account_invoice` | 0 |
| `point_of_sale.group_pos_user` | 0 |

There is a second gate too: `navbar.xml` hides the cash-move entry when
`pos.cashier._role == 'minimal'`, which is a per-employee role, not a group.

So the moment a real cashier is created the ordinary way, the dead end is
what happens. T4 stays.

**This links directly to the next feature.** If cashiers are to perform
vault withdrawals themselves, "may perform a vault withdrawal" has to be one
of the levels in the per-vault permission work — the blocking feature is
only usable if somebody present on the shift can clear the block.

## Constraints

- Strict TDD: observed RED, GREEN, then mutation evidence naming which test
  died. A non-killed mutation is reported honestly.
- Both suites green in both configurations.
- Conventional Commits, no AI attribution. Artifacts in English; new
  user-facing strings must be translatable and added to `es.po`.
- **Enterprise compatibility**: `l10n_mx_edi_pos` patches `PaymentScreen`,
  and this client is Mexican, so that addon may well be installed in their
  production. Any `PaymentScreen` patch must call `super` and must not
  assume it is the only patch present.

## Tasks

- [x] **T1 — The field and its setting.** `vault_withdrawal_blocking` on
      `pos.config`, the `related` field on `res.config.settings`, and the
      `<setting>` in the existing Cash Control block. Assert it is reachable
      in the RENDERED settings arch, not merely present in the source — this
      project shipped two unreachable features already.

      `<setting id="pcdc_vault_withdrawal_blocking">` carries
      `invisible="not pos_vault_withdrawal_threshold"`, so a threshold of
      zero (which already disables the alert entirely) hides the toggle
      instead of letting anyone switch on a block that silently does
      nothing.

      Strict TDD, observed:
      - RED: `./scripts/test.sh "" -- --test-tags
        /pos_cash_denomination_control:TestVaultBlockingConfig` ->
        `4 failed, 2 error(s) of 6 tests`; `AttributeError: 'pos.config'
        object has no attribute 'vault_withdrawal_blocking'`.
      - GREEN: field + related field + setting added -> same command ->
        `0 failed, 0 error(s) of 6 tests`.
      - Mutation: `invisible="not pos_vault_withdrawal_threshold"` changed
        to `invisible="False"` -> same command -> `2 failed, 0 error(s) of
        6 tests`; killed exactly
        `test_blocking_setting_hidden_when_threshold_is_zero` and
        `test_blocking_setting_shown_with_a_positive_threshold`, nothing
        else. Mutation reverted.
      Commit: `3ea876f`.

- [x] **T2 — Block payment validation** when blocking is enabled and the
      vault alert is active. Message names the expected cash and the
      threshold. **Superseded by T6**: naming the amounts in this dialog
      was a confidentiality defect, fixed below -- the dialog body no
      longer includes them.
- [x] **T3 — Offer the withdrawal from the block**, reusing the existing
      vault-reason preselection.
- [x] **T4 — Handle the no-permission dead end** with its own message.
- [x] **T5 — Prove the block lifts** after a cash-out drops expected cash
      below the threshold, with no manual intervention.

      T2-T5 implemented together in `payment_screen_patch.js`, since they
      are one cohesive `validateOrder` override: `pcdcVaultBlockActive()`
      gates on `pos.config.vault_withdrawal_blocking &&
      pos.vaultAlert.required` (read live, no caching); when active,
      `pcdcShowVaultBlockedDialog()` shows a `ConfirmationDialog` offering
      the withdrawal (confirm -> `pos.cashMove({initialType: "out",
      initialReasonId: VaultAlertIndicator.preselectedVaultReasonId(pos)})`)
      when `pos.showCashMoveButton` is true, or an `AlertDialog` pointing
      at a supervisor otherwise (T4). `VaultAlertIndicator
      .preselectedVaultReasonId` was made a `static` method (the instance
      method now delegates to it) precisely so this new caller reuses the
      existing resolution rule instead of reimplementing it.

      Read core's `point_of_sale/static/src/app/screens/payment_screen/
      payment_screen.js` (Odoo 19) and confirmed `l10n_mx_edi_pos`'s own
      `PaymentScreen` patch (`l10n_mx_edi_pos/static/src/app/screens/
      payment_screen/payment_screen.js`) does not touch `validateOrder`
      before writing the patch; it still calls `super()` and does not
      assume it is the only patch present.

      Strict TDD, observed (`static/tests/unit/
      payment_screen_vault_block.test.js`, 6 tests covering: proceeds when
      blocking is off, proceeds when blocking is on but not required,
      refused when both are true, offers the withdrawal with permission,
      points at a supervisor without permission, and lifts on its own once
      `vaultAlert.required` goes back to false):
      - RED: `./scripts/test.sh "" -- --test-tags
        /pos_cash_denomination_control:TestHoot` (patch not yet written)
        -> Hoot suite `passed: 2 / failed: 4`; the 2 passing were the two
        "proceeds normally" cases, which already held before this patch
        existed (core's own `validateOrder` was untouched).
      - GREEN: `payment_screen_patch.js` added -> same command -> Hoot
        suite `passed: 6`, `0 failed, 0 error(s) of 1 tests`.
      - Mutation: `pcdcVaultBlockActive()` changed to `return false;` ->
        same command -> Hoot suite `passed: 2 / failed: 4`; killed exactly
        the same 4 tests RED had failed ("Validation is refused...",
        "Blocked dialog offers the withdrawal...", "Blocked dialog points
        at a supervisor...", "Block lifts by itself..."), nothing else.
        Mutation reverted.
      Commit: `16ce21e`.

- [x] **T6 — Confidentiality fix: stop revealing the expected drawer cash
      and the vault withdrawal threshold on the blocked-sale dialog.**
      Both figures are sensitive operational data that a register-blocking
      dialog shown to an ordinary cashier must not disclose. Neither
      number belongs on that screen, in either dialog branch.

      **What changed and why**: `pcdcShowVaultBlockedDialog()` (in
      `payment_screen_patch.js`) built both dialog bodies with
      `_t("Expected cash (%(expected)s) has reached the vault withdrawal
      threshold (%(threshold)s). ...", { expected, threshold })`, using
      `this.env.utils.formatCurrency()` on `this.pos.vaultAlert.expected`
      and `.threshold`. Replaced both bodies with fixed, amount-free
      English sentences:
      - `ConfirmationDialog` (has cash-move permission): "A vault
        withdrawal is required before any sale can be validated."
      - `AlertDialog` (no permission): "A vault withdrawal is required
        before any sale can be validated. Ask a supervisor to perform
        it."
      Title (`Register blocked`), `confirmLabel` (`Withdraw cash`), the
      permission-check branching, and the dialog service calls are
      unchanged. The now-dead `expected`/`threshold` destructuring and
      `expectedFormatted`/`thresholdFormatted` locals were removed; no
      other locals or imports became unused.

      Files touched: `static/src/app/screens/payment_screen/
      payment_screen_patch.js`, `static/tests/unit/
      payment_screen_vault_block.test.js`.

      Strict TDD, observed:
      - RED: updated
        `static/tests/unit/payment_screen_vault_block.test.js` first (new
        exact-body assertions plus explicit `not.toInclude` checks against
        `comp.env.utils.formatCurrency(1500)` /
        `comp.env.utils.formatCurrency(1000)`, so a regression that leaks
        the numbers back in is caught even if it keeps the new sentence
        too), then ran `./scripts/test.sh "" --
        --test-tags /pos_cash_denomination_control:TestHoot` against the
        still-unmodified source -> Hoot suite `passed: 59 / failed: 3`,
        `1 failed, 0 error(s) of 1 tests`. The 3 failures were exactly
        "Validation is refused when blocking is on and a withdrawal is
        required" (2 `toInclude` assertions caught `$ 1,500.00` /
        `$ 1,000.00` in the body), "Blocked dialog offers the withdrawal
        when the cashier has permission" (`toBe` exact-body mismatch plus
        both `toInclude` assertions), and "Blocked dialog points at a
        supervisor when the cashier lacks cash-move permission" (same
        pattern for the `AlertDialog` body).
      - GREEN: `payment_screen_patch.js` fixed as above -> same command ->
        Hoot suite `Passed 62 tests (110 assertions)`, `0 failed, 0
        error(s) of 1 tests`.
      - Mutation: temporarily reinstated the expected-cash amount into the
        `ConfirmationDialog` body only (`"... validated. (%(expected)s)"`
        with `this.env.utils.formatCurrency(this.pos.vaultAlert.expected)`)
        -> same command -> Hoot suite `passed: 60 / failed: 2`, `1 failed,
        0 error(s) of 1 tests`; killed exactly "Validation is refused when
        blocking is on and a withdrawal is required" and "Blocked dialog
        offers the withdrawal when the cashier has permission" (both via
        their `not.toInclude("$ 1,500.00")` assertion, plus the offering
        test's exact-body `toBe`), and left "Blocked dialog points at a
        supervisor..." green, as expected since that mutation only
        touched the `ConfirmationDialog` branch. Mutation reverted; source
        confirmed back to the clean fix (`git diff` limited to the
        intended comment/body/dead-code changes).

      **i18n** (done directly in this task, not deferred): the source
      fix was on disk before regenerating the `.pot`, avoiding the
      extraction-gap defect `spanish-translations.md` T5 found and fixed
      once already. Regenerated `pos_cash_denomination_control.pot` via
      `odoo i18n export` against a disposable `i18n_export` database in a
      throwaway `docker compose run --rm` container (installed
      `pos_cash_denomination_control,cash_vault` only,
      `--without-demo`), output through a bind-mounted scratch directory
      since the addons mount is read-only; diffed against the prior
      `.pot` and confirmed only the two old amount-bearing msgids were
      replaced by the two new ones, both carrying the correct
      `code:addons/.../payment_screen_patch.js` reference. Merged into
      `es.po` with `msgmerge`: zero fuzzy matches this time (`grep -c
      "^#, fuzzy"` = 0), so no wrong-neighbour fixups were needed; stripped
      the two obsolete (`#~`) entries `msgmerge` left behind for the old
      amount-bearing strings with `msgattrib --no-obsolete`, matching this
      file's existing convention of zero obsolete entries. Translated the
      two new strings:
      - "A vault withdrawal is required before any sale can be validated."
        -> "Se requiere un retiro a bóveda para poder cobrar."
      - "A vault withdrawal is required before any sale can be validated.
        Ask a supervisor to perform it." -> "Se requiere un retiro a
        bóveda para poder cobrar. Solicítalo a un supervisor."
      Verified "Register blocked" -> "Caja bloqueada" and "Withdraw cash"
      -> "Retirar efectivo" were untouched by the merge (still present,
      unchanged, not fuzzed).

      Verification: `msgattrib --untranslated pos_cash_denomination_control/i18n/es.po`
      -> no output (0 untranslated entries), exit 0.
      `msgfmt --check pos_cash_denomination_control/i18n/es.po -o /dev/null`
      -> no output, exit 0.
      End-to-end, in the same `i18n_export` disposable database, via
      `odoo shell`: `code_translations.get_web_translations(
      "pos_cash_denomination_control", "es_MX")` resolved both new
      strings to the Spanish text above, and "Register blocked" /
      "Withdraw cash" still resolved correctly. The disposable
      `i18n_export` database was dropped afterward; `odoo_dev` and
      `staging` were never touched.

      Commits:
      - `7209c9b` fix(pos_cash_denomination_control): stop revealing amounts on the blocked-sale dialog
      - `4dad039` chore(i18n): regenerate pos_cash_denomination_control.pot
      - `3629fca` i18n(pos_cash_denomination_control): translate the confidentiality-fix dialog strings

## Acceptance criteria

- [x] A POS with blocking off behaves exactly as today (proven by
      "Validation proceeds normally when blocking is off").
- [x] A POS with blocking on and threshold 0 also behaves exactly as today:
      `pos.vaultAlert.required` can only be true when
      `config.cash_control` is on AND the threshold is positive
      (`pos.session.get_vault_withdrawal_state`, `models/pos_session.py`),
      so a zero threshold means `required` is always false and
      `pcdcVaultBlockActive()` never fires — proven by "Validation proceeds
      normally when blocking is on but no withdrawal is required" plus the
      pre-existing `test_required_is_false_when_threshold_is_zero`.
- [x] Every new string translated in `es.po`. The original T1-T5 pass
      translated "Vault Withdrawal Blocking" + its help text, "Register
      blocked" and "Withdraw cash" (see `odd/tasks/spanish-translations.md`
      T5). T6 replaced the two amount-bearing block-message literals with
      new confidentiality-safe ones and translated those directly in this
      task (see T6 above); `msgattrib --untranslated` / `msgfmt --check`:
      0 in both.
- [x] Both suites green in both configurations (see Progress).
- [x] **Confidentiality**: the blocked-sale dialog (either branch) no
      longer reveals the expected drawer cash or the vault withdrawal
      threshold to the cashier (T6).

## Progress

All six tasks complete. Baseline `db7a67b` for T1-T5, tree clean apart
from untracked `odd/tasks/*.md` docs. T6 landed later on the same branch,
baseline `45a4130`, tree clean apart from the untracked, unrelated
`odd/tasks/cashier-vault-withdrawal.md` (someone else's in-progress work,
not touched).

Commits (feature/vault-basic, no AI attribution per repo policy):
- `3ea876f` feat(pos_cash_denomination_control): add vault withdrawal blocking config field
- `16ce21e` feat(pos_cash_denomination_control): block sale validation on vault withdrawal alert
- `7209c9b` fix(pos_cash_denomination_control): stop revealing amounts on the blocked-sale dialog
- `4dad039` chore(i18n): regenerate pos_cash_denomination_control.pot
- `3629fca` i18n(pos_cash_denomination_control): translate the confidentiality-fix dialog strings

Final verification, T6 (foreground, observed, not inferred):
- `./scripts/test.sh` -> `0 failed, 0 error(s) of 294 tests when loading
  database 'pcdc_test'` (cash_vault 157, pos_cash_denomination_control 219,
  Hoot suite `Passed 62 tests (110 assertions)`).
- `./scripts/test.sh pos_hr` -> `Loading module pos_hr (67/70)` ...
  `70 modules loaded in 250.44s` ... `0 failed, 0 error(s) of 294 tests
  when loading database 'pcdc_test'`, Hoot suite `Passed 62 tests
  (110 assertions)`.

Final verification (foreground, observed, not inferred):
- `./scripts/test.sh` -> `0 failed, 0 error(s) of 294 tests when loading
  database 'pcdc_test'` (cash_vault 157, pos_cash_denomination_control 219;
  Hoot suite 62/62 passed, was 56 — +6 new frontend tests).
- `./scripts/test.sh pos_hr` -> `70 modules loaded in 248.93s` ... `0
  failed, 0 error(s) of 294 tests when loading database 'pcdc_test'`.

Not yet done: the `.pot`/`es.po` follow-up (see acceptance criteria above)
and live-instance deployment, both explicitly out of this agent's scope —
the orchestrator handles deployment.
