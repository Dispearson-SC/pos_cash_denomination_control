# Cash-In Control Specification

## Purpose

A per-POS toggle that disables the "Cash In" operation outright, independent of
denomination breakdowns. Off by default, including for every POS config that
exists when the module is installed. This is additive to the stock user-level
`_has_cash_move_permission()` check: both the permission and the toggle must
allow cash IN for it to succeed.

## Requirements

### Requirement: Cash-In Toggle Default Off, Applied At Install

`pos.config` MUST expose a stored Boolean field (working name `allow_cash_in`)
defaulting to `False`. Installing the module MUST set this field to `False` on
every existing `pos.config` record.

#### Scenario: New POS config has cash-in off by default (TransactionCase)

- GIVEN a newly created `pos.config` record
- WHEN `allow_cash_in` is read
- THEN it is `False`

#### Scenario: Existing POS config has cash-in off after install (TransactionCase)

- GIVEN a `pos.config` record that existed and had cash-in usable before the module was installed
- WHEN the module is installed
- THEN `allow_cash_in` on that record is `False`

### Requirement: Cash-In Toggle Settings Visibility

The cash-in toggle MUST be shown in POS settings only when the POS has cash
control.

#### Scenario: Shown with cash control (TransactionCase)

- GIVEN a `pos.config` with `cash_control=True`
- WHEN the POS settings form view is evaluated
- THEN the cash-in toggle is shown

#### Scenario: Hidden without cash control (TransactionCase)

- GIVEN a `pos.config` with `cash_control=False`
- WHEN the POS settings form view is evaluated
- THEN the cash-in toggle is not shown

### Requirement: Frontend Delivery Of Cash-In State

`allow_cash_in` MUST be included in the `pos.config` payload delivered to the POS
frontend.

#### Scenario: POS receives cash-in flag (Hoot)

- GIVEN a `pos.config` with `allow_cash_in=True`
- WHEN the POS session loads its config data
- THEN `this.pos.config.allow_cash_in` is `True`

### Requirement: Cash Move Popup Reflects Cash-In State

When `allow_cash_in` is `False`, the cash move popup MUST NOT show a "Cash In"
option, MUST open in "out" mode, and MUST NOT allow switching its type to "in".
When `allow_cash_in` is `True`, both "Cash In" and "Cash Out" MUST be available
(subject to the stock cash-move permission).

#### Scenario: Popup hides Cash In when disabled (Hoot)

- GIVEN `this.pos.config.allow_cash_in` is `False`
- WHEN the cash move popup is opened
- THEN no "Cash In" button or option is rendered and the popup state type is `"out"`

#### Scenario: Popup type cannot be switched to in when disabled (Hoot)

- GIVEN the cash move popup is open with `allow_cash_in=False`
- WHEN the user attempts to select "in" as the move type
- THEN the type remains `"out"`

#### Scenario: Popup shows both options when enabled (Hoot)

- GIVEN `this.pos.config.allow_cash_in` is `True`
- WHEN the cash move popup is opened
- THEN both "Cash In" and "Cash Out" options are available

### Requirement: Server Rejects Cash-In When Disabled, Regardless Of Caller

`try_cash_in_out` MUST raise `UserError` for `_type == 'in'` when the session's
POS config has `allow_cash_in=False`, before any statement line or count record
is created. This check MUST apply regardless of the caller (POS UI, direct RPC,
script) and MUST also reject offline-queued cash-in replays performed after the
toggle was turned off.

#### Scenario: Direct RPC cash-in rejected when disabled (TransactionCase)

- GIVEN a session whose config has `allow_cash_in=False`
- WHEN `try_cash_in_out` is called directly with `_type='in'`
- THEN a `UserError` is raised and no `account.bank.statement.line` is created

#### Scenario: Offline-queued cash-in replay rejected after disabling (TransactionCase)

- GIVEN a cash-in call was queued while `allow_cash_in` was `True`
- WHEN `allow_cash_in` is set to `False` before the queued call is replayed against the server
- THEN the replay raises `UserError` and no statement line is created

#### Scenario: Cash-out unaffected by cash-in toggle (TransactionCase)

- GIVEN a session whose config has `allow_cash_in=False`
- WHEN `try_cash_in_out` is called with `_type='out'`
- THEN the call proceeds normally (subject to other rules) and is not rejected by this toggle

#### Scenario: Cash-in accepted when enabled and permitted (TransactionCase)

- GIVEN a session whose config has `allow_cash_in=True` and a user with the stock cash-move permission
- WHEN `try_cash_in_out` is called with `_type='in'` and a valid reason
- THEN the call succeeds and a statement line is created

### Requirement: Cash-In Requires Both Permission And Toggle

The cash-in toggle MUST be additive to the stock `_has_cash_move_permission()`
check. Neither one alone is sufficient for cash IN to succeed.

#### Scenario: Permission present but toggle off is still rejected (TransactionCase)

- GIVEN a user with the stock cash-move permission and `allow_cash_in=False`
- WHEN `try_cash_in_out` is called with `_type='in'`
- THEN `UserError` is raised

#### Scenario: Toggle on but permission absent is still rejected (TransactionCase)

- GIVEN a user without the stock cash-move permission and `allow_cash_in=True`
- WHEN `try_cash_in_out` is called with `_type='in'`
- THEN the stock permission check rejects the call as it does today, unaffected by this toggle

#### Scenario: Permission present and toggle on succeeds (TransactionCase)

- GIVEN a user with the stock cash-move permission and `allow_cash_in=True`
- WHEN `try_cash_in_out` is called with `_type='in'` and a valid reason
- THEN the call succeeds

### Requirement: Documented Behavior Change

The addon README MUST document that installing the module disables cash-in on
every existing POS config, and MUST document how to re-enable cash-in per POS.

#### Scenario: README documents the cash-in default-off change (documentation review)

- GIVEN the addon's `readme/` fragments
- WHEN they are reviewed
- THEN they state that install disables cash-in on all existing configs and describe the settings toggle used to re-enable it per POS
