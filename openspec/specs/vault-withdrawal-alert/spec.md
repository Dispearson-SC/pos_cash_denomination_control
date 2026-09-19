# Vault Withdrawal Alert Specification

## Purpose

A per-POS configurable cash threshold that notifies the cashier, non-blockingly,
that the drawer holds enough cash to warrant a vault withdrawal, backed by a
pure expected-cash formula that stays in parity with the existing closing
computation.

## Requirements

### Requirement: Vault Withdrawal Threshold Field

`pos.config` MUST expose a Monetary field (working name
`vault_withdrawal_threshold`) defaulting to `0` (meaning disabled), visible and
effective only when the POS has cash control, and delivered to the POS
frontend.

#### Scenario: Threshold defaults to zero (TransactionCase)

- GIVEN a newly created `pos.config` record
- WHEN `vault_withdrawal_threshold` is read
- THEN it is `0`

#### Scenario: Threshold field hidden without cash control (TransactionCase)

- GIVEN a `pos.config` with `cash_control=False`
- WHEN the POS settings form view is evaluated
- THEN the threshold field is not shown

#### Scenario: Threshold delivered to POS frontend (Hoot)

- GIVEN a `pos.config` with `vault_withdrawal_threshold=1000`
- WHEN the POS loads its config data
- THEN `this.pos.config.vault_withdrawal_threshold` is `1000`

### Requirement: Expected Cash Computation

The domain MUST compute expected drawer cash as: opening balance + the sum of
default cash payment method amounts of closed orders + the sum of cash
statement line amounts, for a given session.

#### Scenario: Expected cash computed with orders and cash moves (domain unit)

- GIVEN an opening balance of `200`, closed-order cash payments summing to `500`, and statement line amounts summing to `-100`
- WHEN expected cash is computed
- THEN the result is `600` (200 + 500 - 100)

#### Scenario: Expected cash with no orders equals the opening balance (domain unit)

- GIVEN an opening balance of `200`, no closed-order cash payments, and no statement lines
- WHEN expected cash is computed
- THEN the result is `200`

### Requirement: Withdrawal-Required Decision Rule

The domain MUST decide that a withdrawal is required only when the threshold
is strictly greater than zero AND expected cash is greater than or equal to
the threshold, compared using currency rounding. A threshold of `0` MUST never
require a withdrawal.

#### Scenario: Threshold zero never requires withdrawal (domain unit)

- GIVEN `threshold=0` and any expected cash value, including a very large one
- WHEN the decision rule runs
- THEN `required` is `False`

#### Scenario: Expected cash exactly equal to a positive threshold requires withdrawal (domain unit)

- GIVEN `threshold=1000` and `expected=1000`
- WHEN the decision rule runs
- THEN `required` is `True`

#### Scenario: Expected cash just below threshold within rounding tolerance requires withdrawal (domain unit)

- GIVEN `threshold=1000.00`, `expected=999.996`, and rounding `0.01`
- WHEN the decision rule runs
- THEN `required` is `True`, because the difference is within the rounding tolerance and treated as equal

#### Scenario: Expected cash below threshold does not require withdrawal (domain unit)

- GIVEN `threshold=1000` and `expected=900`
- WHEN the decision rule runs
- THEN `required` is `False`

#### Scenario: Expected cash above threshold requires withdrawal (domain unit)

- GIVEN `threshold=1000` and `expected=1500`
- WHEN the decision rule runs
- THEN `required` is `True`

### Requirement: Server Method With Parity To `get_closing_control_data`

A server method (working name `get_vault_withdrawal_state`) MUST return
`{expected_cash, threshold, required}` for a session, using the same
`group_pos_user` access check as `get_closing_control_data`. It MUST return
`required=False` when cash control is off or the threshold is `0`. Its
`expected_cash` MUST equal
`get_closing_control_data()['default_cash_details']['amount']` for the same
session.

#### Scenario: Parity between the alert method and the closing control formula (TransactionCase)

- GIVEN a session with orders and cash moves
- WHEN both `get_vault_withdrawal_state` and `get_closing_control_data` are called
- THEN the alert method's `expected_cash` equals `get_closing_control_data()['default_cash_details']['amount']`

#### Scenario: Required is False when cash control is off (TransactionCase)

- GIVEN a session whose POS has `cash_control=False`
- WHEN `get_vault_withdrawal_state` is called
- THEN `required` is `False`

#### Scenario: Required is False when threshold is zero (TransactionCase)

- GIVEN a session whose POS has `vault_withdrawal_threshold=0`
- WHEN `get_vault_withdrawal_state` is called
- THEN `required` is `False`

#### Scenario: Access denied for a user without group_pos_user (TransactionCase)

- GIVEN a user without `group_pos_user`
- WHEN that user calls `get_vault_withdrawal_state`
- THEN an `AccessError` is raised, matching `get_closing_control_data`'s own access check

### Requirement: POS Refresh Triggers

The POS frontend MUST refresh the vault withdrawal state on POS load, after
each successful order sync, and after each successful cash move.

#### Scenario: State refreshes on load (Hoot)

- GIVEN a POS session with a threshold configured
- WHEN the POS loads
- THEN the vault withdrawal state is fetched and applied

#### Scenario: State refreshes after order sync (tour)

- GIVEN a POS session with a threshold configured
- WHEN an order is successfully synced
- THEN the vault withdrawal state is refreshed afterward

#### Scenario: State refreshes after cash move (tour)

- GIVEN a POS session with a threshold configured
- WHEN a cash move is successfully completed
- THEN the vault withdrawal state is refreshed afterward

### Requirement: Non-Blocking Notification And Persistent Navbar Indicator

On a transition from "not required" to "required" (and on load when already
required), the POS MUST show exactly one non-blocking "Vault withdrawal
required" notification. While required, a persistent navbar indicator MUST be
shown. The indicator MUST disappear only after a refresh reports expected cash
below the threshold.

#### Scenario: Notification shown once on transition to required (Hoot)

- GIVEN the state was "not required"
- WHEN a refresh reports "required"
- THEN exactly one notification is shown

#### Scenario: Notification shown on load when already required (Hoot)

- GIVEN the session is already over threshold when the POS loads
- WHEN the initial refresh reports "required"
- THEN a notification is shown

#### Scenario: Indicator persists across multiple refreshes without repeated notification (Hoot)

- GIVEN the state is already "required" and a notification was already shown
- WHEN a subsequent refresh again reports "required"
- THEN the navbar indicator remains visible but no additional notification is shown

#### Scenario: Indicator is cleared after cash-out brings expected cash below threshold (tour)

- GIVEN the navbar indicator is showing "required"
- WHEN a cash-out is completed that brings expected cash below the threshold and the state is refreshed
- THEN the navbar indicator is removed

#### Scenario: Indicator is not shown when required is False (Hoot)

- GIVEN the refreshed state reports `required=False`
- WHEN the navbar is rendered
- THEN no vault withdrawal indicator is shown

### Requirement: Offline Behavior Keeps Last Known State

While offline, the indicator MUST keep showing the last known state from the
most recent successful refresh, without inventing a new state.

#### Scenario: Indicator retains last known state while offline (Hoot)

- GIVEN the last successful refresh reported `required=True`
- WHEN the POS goes offline and no further refresh succeeds
- THEN the navbar indicator continues showing "required" unchanged

### Requirement: One-Click Vault Cash-Out

Clicking the indicator MUST open the cash move popup in "out" mode with a
vault reason preselected using this priority: the POS default cash-out reason
if it is a vault reason; otherwise the first active vault reason by sequence;
otherwise no preselection. This MUST respect the stock cash-move permission:
without it, clicking MUST show a notification instead of opening the popup.

#### Scenario: Click preselects the POS default vault reason (Hoot)

- GIVEN the POS default cash-out reason is a vault reason
- WHEN the indicator is clicked
- THEN the popup opens in "out" mode with that reason preselected

#### Scenario: Click preselects the first active vault reason when the default is not a vault reason (Hoot)

- GIVEN the POS default cash-out reason is not a vault reason, and one or more active vault reasons exist
- WHEN the indicator is clicked
- THEN the popup opens in "out" mode with the first active vault reason (by sequence) preselected

#### Scenario: Click shows no preselection when no vault reason exists (Hoot)

- GIVEN no active vault reason exists
- WHEN the indicator is clicked
- THEN the popup opens in "out" mode with no reason preselected

#### Scenario: Click without stock cash-move permission shows a notification instead of the popup (Hoot)

- GIVEN the acting user lacks the stock cash-move permission
- WHEN the indicator is clicked
- THEN a notification is shown and the cash move popup does not open

### Requirement: The Alert Never Blocks POS Functions

The vault withdrawal alert MUST NOT add any check that blocks sales, payments,
cash moves, or closing.

#### Scenario: Sale completes normally while the alert is active (tour)

- GIVEN the navbar indicator shows "required"
- WHEN a sale is completed
- THEN the sale succeeds without any alert-related interruption

#### Scenario: Closing succeeds normally while the alert is active (TransactionCase)

- GIVEN the session is over the vault threshold
- WHEN the session is closed
- THEN closing succeeds without any alert-related check blocking it
