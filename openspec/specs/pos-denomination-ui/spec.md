# POS Denomination UI Specification

## Purpose

The frontend breakdown popup and the changes to the opening, cash move, and
closing popups needed to collect, transport, and display a per-denomination
breakdown, replacing the existing float-keyed `MoneyDetailsPopup` state for
this purpose without changing its behavior when toggles are off.

## Requirements

### Requirement: Id-Keyed Breakdown Popup Payload

A new breakdown popup component MUST emit a payload of `[{bill_id, quantity}]`
entries (keyed by `pos.bill.id`, never by bill value) together with the
computed total.

#### Scenario: Popup confirm returns an id-keyed array (Hoot)

- GIVEN the user enters quantities for two different bills in the popup
- WHEN the popup is confirmed
- THEN the returned payload is an array of `{bill_id, quantity}` objects, one per non-zero entry

#### Scenario: Popup computes a total matching the domain rule (Hoot)

- GIVEN quantities entered for bills of known values
- WHEN the popup is confirmed
- THEN the returned total equals Σ(quantity × bill value) for the entered lines

### Requirement: Read-Only Amount Input When The Applicable Toggle Is On

When the relevant denomination toggle is on, the corresponding amount input
(opening cash, cash move amount, or closing cash payment count) MUST be
read-only, and its value MUST be settable only through the breakdown popup.
When the toggle is off, the amount input MUST remain freely editable, exactly
as in stock Odoo.

#### Scenario: Opening amount field is read-only when the opening toggle is on (Hoot)

- GIVEN the opening toggle is on
- WHEN the opening popup is rendered
- THEN the cash amount input is read-only and its value only changes via the breakdown popup

#### Scenario: Cash move amount field is read-only when the applicable toggle is on (Hoot)

- GIVEN the cash OUT toggle is on and the popup type is "out"
- WHEN the cash move popup is rendered
- THEN the amount input is read-only

#### Scenario: Closing cash amount field is read-only when the closing toggle is on (Hoot)

- GIVEN the closing toggle is on
- WHEN the closing popup is rendered
- THEN the cash payment method's counted amount input is read-only

#### Scenario: Amount field is editable when the toggle is off (Hoot)

- GIVEN the relevant toggle is off
- WHEN the corresponding popup is rendered
- THEN the amount input is freely editable, exactly as in stock Odoo

### Requirement: Breakdown Is Transported To The Server

The UI MUST transport the structured breakdown to the server through the
`denomination_lines` kwarg (opening, closing) or `extras['denomination_lines']`
(cash moves), per the approach's additive transport contract.

#### Scenario: Opening RPC includes the denomination_lines kwarg (Hoot)

- GIVEN the opening toggle is on and a breakdown was entered
- WHEN the opening confirmation RPC is built
- THEN it includes a `denomination_lines` kwarg with the entered `[{bill_id, quantity}]` array

#### Scenario: Cash move RPC includes denomination_lines in extras (Hoot)

- GIVEN the applicable cash move toggle is on and a breakdown was entered
- WHEN `_prepareTryCashInOutPayload` builds the call
- THEN `extras['denomination_lines']` contains the entered array

#### Scenario: Closing RPC includes the denomination_lines kwarg (Hoot)

- GIVEN the closing toggle is on and a breakdown was entered
- WHEN the `post_closing_cash_details` call is built
- THEN it includes a `denomination_lines` kwarg with the entered array

### Requirement: Human-Readable Note Text Is Preserved

The UI MUST continue to append a human-readable breakdown note to the existing
notes text field, exactly as the stock `MoneyDetailsPopup` flow does today.

#### Scenario: Note text is generated from the entered breakdown (Hoot)

- GIVEN a breakdown was entered in the new popup
- WHEN the note text is generated
- THEN it lists each denomination and its quantity in human-readable form

### Requirement: End-To-End Flows Are Verified By Tours

The complete opening, cash-out, and closing flows with a denomination
breakdown MUST be verified end-to-end through browser tours.

#### Scenario: Opening tour with a breakdown succeeds (tour)

- GIVEN the opening toggle is on
- WHEN the opening tour enters a valid breakdown and confirms
- THEN the session opens with the corresponding opening balance and count record

#### Scenario: Cash-out tour with reason and breakdown succeeds (tour)

- GIVEN the cash OUT toggle is on
- WHEN the tour selects a reason, enters a valid breakdown, and confirms a cash-out
- THEN the cash-out succeeds and the resulting statement line carries the reason and amount

#### Scenario: Closing tour with a breakdown succeeds (tour)

- GIVEN the closing toggle is on
- WHEN the tour enters a valid closing breakdown and closes the session
- THEN the session closes with the corresponding counted cash and count record
