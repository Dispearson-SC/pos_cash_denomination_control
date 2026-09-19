# Cash Denomination Enforcement Specification

## Purpose

Server-side acceptance and rejection of opening, cash IN/OUT, and POS UI
closing operations, keyed on each operation's denomination toggle. Enforcement
calls the pure domain validators (`denomination-breakdown-domain`) and must be
safe for offline-queued replay, since these RPCs travel through the
offline-tolerant queue.

## Requirements

### Requirement: Opening Enforcement

When the opening denomination toggle is on, `set_opening_control` (via
`_set_opening_control_data`) MUST require a breakdown whose computed total
matches the declared `cashbox_value` within currency rounding, using only
allowed bills and non-negative integer quantities. When the toggle is off,
behavior MUST be unchanged from stock (no breakdown required).

#### Scenario: Opening with valid breakdown is accepted (TransactionCase)

- GIVEN the opening toggle is on and a breakdown summing to the declared cashbox value using allowed bills
- WHEN `set_opening_control` is called with that breakdown
- THEN the call succeeds and the cashbox value is set

#### Scenario: Opening missing breakdown is rejected (TransactionCase)

- GIVEN the opening toggle is on
- WHEN `set_opening_control` is called without a breakdown
- THEN `UserError` is raised and the opening balance is not set

#### Scenario: Opening breakdown sum mismatch is rejected (TransactionCase)

- GIVEN the opening toggle is on and a breakdown that sums to less than the declared cashbox value
- WHEN `set_opening_control` is called
- THEN `UserError` is raised

#### Scenario: Opening breakdown with disallowed bill is rejected (TransactionCase)

- GIVEN the opening toggle is on and a breakdown containing a bill not in the POS's allowed bills
- WHEN `set_opening_control` is called
- THEN `UserError` is raised

#### Scenario: Opening breakdown with negative quantity is rejected (TransactionCase)

- GIVEN the opening toggle is on and a breakdown line with a negative quantity
- WHEN `set_opening_control` is called
- THEN `UserError` is raised

#### Scenario: Opening breakdown with non-integer quantity is rejected (TransactionCase)

- GIVEN the opening toggle is on and a breakdown line with a non-integer quantity
- WHEN `set_opening_control` is called
- THEN `UserError` is raised

#### Scenario: Opening toggle off skips breakdown validation (TransactionCase)

- GIVEN the opening toggle is off
- WHEN `set_opening_control` is called with no breakdown, as stock Odoo does today
- THEN the call succeeds exactly as in stock Odoo

### Requirement: Cash Move Enforcement (IN/OUT), Independent Per Direction

When the cash OUT toggle is on, `try_cash_in_out` MUST require a valid,
amount-matching breakdown for `_type='out'`. When the cash IN toggle is on (and
cash-in is enabled), it MUST require a valid, amount-matching breakdown for
`_type='in'`. Each toggle MUST apply only to its own direction.

#### Scenario: Cash out with valid breakdown is accepted (TransactionCase)

- GIVEN the cash OUT toggle is on and a breakdown matching the requested amount using allowed bills
- WHEN `try_cash_in_out` is called with `_type='out'` and that breakdown
- THEN the call succeeds and a statement line is created

#### Scenario: Cash out missing breakdown is rejected when toggle is on (TransactionCase)

- GIVEN the cash OUT toggle is on
- WHEN `try_cash_in_out` is called with `_type='out'` and no breakdown
- THEN `UserError` is raised and no statement line is created

#### Scenario: Cash in with valid breakdown is accepted (TransactionCase)

- GIVEN cash-in is enabled, the cash IN toggle is on, and a matching breakdown is supplied
- WHEN `try_cash_in_out` is called with `_type='in'`
- THEN the call succeeds and a statement line is created

#### Scenario: Cash-IN toggle does not affect cash OUT enforcement (TransactionCase)

- GIVEN the cash IN toggle is on and the cash OUT toggle is off
- WHEN `try_cash_in_out` is called with `_type='out'` and no breakdown
- THEN the call succeeds, because the OUT toggle (not the IN toggle) governs OUT enforcement

#### Scenario: Cash move breakdown sum mismatch is rejected (TransactionCase)

- GIVEN the applicable toggle is on and a breakdown that does not sum to the requested amount within rounding
- WHEN `try_cash_in_out` is called
- THEN `UserError` is raised

#### Scenario: Cash move breakdown with disallowed bill is rejected (TransactionCase)

- GIVEN the applicable toggle is on and a breakdown containing a disallowed bill
- WHEN `try_cash_in_out` is called
- THEN `UserError` is raised

#### Scenario: Cash move breakdown with negative or non-integer quantity is rejected (TransactionCase)

- GIVEN the applicable toggle is on and a breakdown line with a negative or non-integer quantity
- WHEN `try_cash_in_out` is called
- THEN `UserError` is raised

### Requirement: Closing Enforcement Applies Only To The Cash Payment Method Count

When the closing toggle is on, `post_closing_cash_details` MUST require a
breakdown whose total matches `counted_cash` within currency rounding, using
allowed bills and non-negative integer quantities. This enforcement MUST apply
only to the cash payment method's counted amount; non-cash payment method
counts MUST be unaffected.

#### Scenario: Closing with valid breakdown is accepted (TransactionCase)

- GIVEN the closing toggle is on and a breakdown matching `counted_cash`
- WHEN `post_closing_cash_details` is called with that breakdown
- THEN the call succeeds and `cash_register_balance_end_real` is set

#### Scenario: Closing missing breakdown is rejected (TransactionCase)

- GIVEN the closing toggle is on
- WHEN `post_closing_cash_details` is called without a breakdown
- THEN `UserError` is raised and `cash_register_balance_end_real` is not set

#### Scenario: Non-cash payment method counts are unaffected by the toggle (TransactionCase)

- GIVEN the closing toggle is on
- WHEN a non-cash payment method's counted amount is submitted through its own closing flow
- THEN it is accepted or rejected exactly as in stock Odoo, unaffected by this toggle

### Requirement: Offline Replay Safety

Because opening and cash move RPCs travel through the offline-tolerant queue,
each payload MUST be self-contained (bill ids, quantities, declared amount) so
that server-side validation at replay time does not depend on any client-side
context beyond that single payload, and MUST validate against the POS
configuration as it exists at replay time.

#### Scenario: Queued opening replay is validated independently after reconnect (TransactionCase)

- GIVEN an opening call was queued while offline with a valid, self-contained breakdown payload
- WHEN the queued call reaches the server later
- THEN it is validated using only the payload's own data and the server's current config, and succeeds if still valid

#### Scenario: Offline replay against changed allowed-bills configuration is rejected at replay time (TransactionCase)

- GIVEN an opening or cash move call was queued while a bill was allowed for the POS
- WHEN that bill is removed from the POS's allowed bills before the queued call replays
- THEN the replay is rejected with `UserError`, because validation uses the allowed bills at replay time, not at queue time

### Requirement: Backward-Compatible Notes Preserved

Regardless of toggle state, the human-readable breakdown text MUST still be
appended to opening and closing notes and posted to chatter, exactly as stock
Odoo does today for the existing `MoneyDetailsPopup` flow.

#### Scenario: Opening note contains the denomination breakdown text (TransactionCase)

- GIVEN an opening with a submitted breakdown
- WHEN the session's opening notes are read
- THEN they contain the human-readable per-denomination breakdown text

#### Scenario: Closing note and chatter contain the denomination breakdown text (TransactionCase)

- GIVEN a closing with a submitted breakdown
- WHEN the session's closing notes and chatter messages are read
- THEN they contain the human-readable per-denomination breakdown text
