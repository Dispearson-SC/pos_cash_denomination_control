# Let ordinary cashiers perform vault withdrawals

## Objective

Give every ordinary POS cashier the ability to send cash to the vault —
and **only** to the vault — without granting them Odoo's general cash-move
permission.

## Why

Odoo gates all cash movement behind
`point_of_sale/models/res_users.py::_has_cash_move_permission`:

```python
def _has_cash_move_permission(self):
    return self.has_group('point_of_sale.group_pos_manager') \
        or self.has_group('account.group_account_invoice')
```

An ordinary cashier holds `point_of_sale.group_pos_user`, which is in
neither branch, so `pos_store.js`'s
`showCashMoveButton = Boolean(config.cash_control && config._has_cash_move_perm)`
is false for them and the whole Cash In/Out surface is hidden.

Measured on the live Enterprise instance: `group_pos_manager` 3 users,
`account.group_account_invoice` 0, `group_pos_user` 0. So today only
administrators can move cash.

This blocks two things at once: the daily reality that the person holding
the drawer is the one who should hand cash to the vault, and the register
blocking feature (`odd/tasks/vault-withdrawal-blocking.md`), which becomes a
dead end if nobody on the shift can clear the block.

## The second gate, checked and cleared

`navbar.xml` also hides the cash-move entry when
`pos.cashier._role == 'minimal'`. That was verified in `pos_hr`'s
`hr_employee.py`: a role is `minimal` only when the employee is explicitly
listed in `config.minimal_employee_ids`; otherwise the default is
`cashier`. So this gate is opt-in and does **not** block the default case.

## Scope decision, made by the user

Asked whether cashiers should be able to make any cash-out or only vault
withdrawals, the user chose **vault withdrawals only**. Any other cash-out —
expenses, change, supplier payments — still requires a manager.

## This one IS a security boundary — unlike the register block

`odd/tasks/vault-withdrawal-blocking.md` is deliberately client-side only,
because it is a workflow control and blocking a sale server-side would
destroy transactions that already physically happened.

**This feature is the opposite.** It decides whether cash may leave a
drawer and for what reason. A client-side filter on the reason dropdown is a
hint, not a control — exactly the `readonly=True` mistake that produced this
project's 35 security defects.

Therefore every restriction here must be enforced **on the server**, in
`pos.session.try_cash_in_out` or below, and the UI filtering is only a
convenience on top of it. A test must prove that a cashier calling the
method directly with a non-vault reason is refused.

## Design

- **New group** in `pos_cash_denomination_control`, e.g.
  `group_pcdc_vault_withdrawal` ("Vault Withdrawal"), implied by
  `point_of_sale.group_pos_user` so every existing and future cashier gets
  it on install with no manual step.
- **Override `res.users._has_cash_move_permission()`** to also return True
  for that group. This is the minimum needed to make the Cash In/Out surface
  appear; it must call `super()` and never remove anyone's existing access.
- **Server-side restriction** for a user who holds ONLY the new group and
  neither `group_pos_manager` nor `account.group_account_invoice`:
  - cash **in** is refused outright, regardless of the POS's
    `allow_cash_in` setting;
  - cash **out** is refused unless the chosen reason has `is_vault = True`.
- **UI convenience on top**: for such a user the cash-move popup offers only
  vault reasons and only the `out` direction, so they never see an option
  the server will reject.

## Constraints

- Strict TDD: observed RED, GREEN, then mutation evidence naming which test
  died. A non-killed mutation is reported honestly.
- Tests must use real restricted actors via `with_user()`, never the
  ambient privileged actor. This project's tests ran for a long time under
  an over-privileged user and that is how the original defects hid.
- Baseline: tip `d931a44` (or later), `0 failed, 0 error(s) of 288 tests` in
  both configurations.
- Conventional Commits, no AI attribution. New strings translated in
  `es.po`, which is now current.

## Tasks

- [ ] **T1 — The group**, implied by `point_of_sale.group_pos_user`, and the
      `_has_cash_move_permission` override calling `super()`.
- [ ] **T2 — Server-side refusal of cash-in** for a holder of only the new
      group, proven by a `with_user()` test calling the method directly.
- [ ] **T3 — Server-side refusal of a non-vault cash-out reason** for the
      same actor, proven the same way.
- [ ] **T4 — UI narrowing**: only vault reasons, only `out`, for such a
      user. Assert against the real component behaviour, not the source.
- [ ] **T5 — Prove a manager is unaffected**: still both directions, still
      every reason.

## Acceptance criteria

- A plain `group_pos_user` cashier can send cash to the vault from the POS.
- The same cashier is refused, **by the server**, for a cash-in or a
  non-vault cash-out.
- A manager's behaviour is unchanged.
- Both suites green in both configurations.

## Progress

Not started. Runs BEFORE `odd/tasks/vault-withdrawal-blocking.md`, since
that feature is unusable until somebody on the shift can clear the block.
