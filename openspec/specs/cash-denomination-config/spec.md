# Cash Denomination Config Specification

## Purpose

The four independent per-POS denomination toggles (opening, cash OUT, cash IN,
closing) that decide, per operation type, whether a breakdown is required. This
capability covers only the config fields, their defaults, their visibility, and
their delivery to the POS frontend — enforcement itself is
`cash-denomination-enforcement`.

## Requirements

### Requirement: Four Independent Toggles, Default Off

`pos.config` MUST expose four independent stored Boolean fields — opening,
cash OUT, cash IN, and closing cash count — each defaulting to `False`.

#### Scenario: New POS config has all four toggles off (TransactionCase)

- GIVEN a newly created `pos.config` record
- WHEN its denomination toggle fields are read
- THEN all four are `False`

#### Scenario: Existing POS config has all four toggles off after install (TransactionCase)

- GIVEN a `pos.config` record that existed before the module was installed
- WHEN the module is installed
- THEN all four denomination toggle fields on that record are `False`

#### Scenario: Toggles are independent of each other (TransactionCase)

- GIVEN a `pos.config` with the opening toggle set to `True`
- WHEN the cash OUT, cash IN, and closing toggles are read
- THEN they remain `False` unless explicitly set

### Requirement: Toggle Visibility Requires Cash Control

The four denomination toggles MUST be shown in POS settings only when the POS
has cash control (`pos.config.cash_control` is `True`).

#### Scenario: Toggles hidden without cash control (TransactionCase)

- GIVEN a `pos.config` with `cash_control=False`
- WHEN the POS settings form view is evaluated
- THEN the denomination toggle fields are not shown to the user

#### Scenario: Toggles shown with cash control (TransactionCase)

- GIVEN a `pos.config` with `cash_control=True`
- WHEN the POS settings form view is evaluated
- THEN the opening, cash OUT, and closing toggle fields are shown

### Requirement: Cash-IN Toggle Additionally Requires Cash-In Enabled

The cash-IN denomination toggle MUST be shown in settings only when both the POS
has cash control AND cash-in is enabled for that POS (`allow_cash_in=True`).

#### Scenario: Cash-IN toggle hidden when cash-in is disabled (TransactionCase)

- GIVEN a `pos.config` with `cash_control=True` and `allow_cash_in=False`
- WHEN the POS settings form view is evaluated
- THEN the cash-IN denomination toggle is not shown

#### Scenario: Cash-IN toggle shown when cash-in is enabled (TransactionCase)

- GIVEN a `pos.config` with `cash_control=True` and `allow_cash_in=True`
- WHEN the POS settings form view is evaluated
- THEN the cash-IN denomination toggle is shown

### Requirement: Toggles Delivered To POS Frontend

All four denomination toggle values MUST be included in the `pos.config` payload
served to the POS frontend, so JS code can read `this.pos.config.<toggle>`.

#### Scenario: POS load includes current toggle values (Hoot)

- GIVEN a `pos.config` with the cash OUT toggle `True` and the others `False`
- WHEN the POS session loads its config data
- THEN `this.pos.config` exposes the cash OUT toggle as `True` and the other three as `False`

#### Scenario: Toggle change is reflected on next load (Hoot)

- GIVEN a POS config with the closing toggle `False`
- WHEN the toggle is set to `True` in the backend and the POS reloads its config
- THEN `this.pos.config` exposes the closing toggle as `True`
