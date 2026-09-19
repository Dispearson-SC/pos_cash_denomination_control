# Cash Count Records Specification

## Purpose

The persisted structured record of every denomination count: a header per
counted operation and one line per denomination entered, plus the backend
reporting surface (views, menu, access rights, record rules) built on them.

## Requirements

### Requirement: Header Record Fields

`pos.cash.denomination.count` MUST store: `session_id`, `config_id` (related to
the session's config, stored), `company_id` (from the session), `move_type`
(one of `opening`, `in`, `out`, `closing`), `total`, a date/time, the acting
`user_id`, an optional employee reference (filled only when `pos_hr` data is
available), a `reason_id` (populated only for `in`/`out` move types), and a link
to the related `account.bank.statement.line` (populated only for `in`/`out`
move types).

#### Scenario: Header created with core fields (TransactionCase)

- GIVEN an accepted, counted opening operation
- WHEN the header record is inspected
- THEN it has the session, config, company, `move_type='opening'`, total, date, and user set correctly

#### Scenario: Opening header has no reason (TransactionCase)

- GIVEN an accepted, counted opening operation
- WHEN the header record is inspected
- THEN `reason_id` is empty, because opening does not carry a reason

#### Scenario: Cash move header stores reason and statement line link (TransactionCase)

- GIVEN an accepted, counted cash OUT operation with a valid reason
- WHEN the header record is inspected
- THEN `reason_id` matches the reason used and the header is linked to the created `account.bank.statement.line`

### Requirement: Line Record Fields And Denormalization

`pos.cash.denomination.count.line` MUST store `bill_id`, a snapshot of the
bill's value at count time (`bill_value`), `quantity`, a stored `subtotal`
(quantity × snapshot bill value), and denormalized copies of the header's
session, config, company, move type, date, and reason, so pivot and graph views
can group directly on lines without joining to the header.

#### Scenario: Line snapshot is independent of later bill value changes (TransactionCase)

- GIVEN a count line created when `pos.bill.value` was `100`
- WHEN `pos.bill.value` is later changed to `200`
- THEN the line's stored `bill_value` snapshot remains `100`

#### Scenario: Line subtotal equals quantity times snapshot value (TransactionCase)

- GIVEN a line with `quantity=3` and snapshot `bill_value=50`
- WHEN the line is read
- THEN `subtotal` is `150`

#### Scenario: Line carries denormalized header fields (TransactionCase)

- GIVEN a count line belonging to a header with `move_type='out'` and a given reason
- WHEN the line is read
- THEN its own `move_type` and `reason_id` fields match the header's values

### Requirement: Employee Attribution Without Hard `pos_hr` Dependency

The header MUST record the acting employee when employee data is available
(`extras['employee_id']` for cash moves, `session.employee_id` for opening and
closing) and MUST leave the employee field empty when no employee data is
available, without requiring `pos_hr` as a dependency.

#### Scenario: Employee stored with pos_hr installed (TransactionCase)

- GIVEN `pos_hr` is installed and the session has an employee, or `extras['employee_id']` is provided for a cash move
- WHEN the header is created
- THEN the employee field is populated with that employee

#### Scenario: Employee absent without pos_hr installed (TransactionCase)

- GIVEN `pos_hr` is not installed and no employee data is available
- WHEN the header is created
- THEN the employee field is empty and no error is raised

### Requirement: One Header And N Lines Per Accepted Operation

Each accepted, counted operation MUST create exactly one header record and one
line per denomination entry with a quantity greater than zero.

#### Scenario: Accepted operation creates header and lines (TransactionCase)

- GIVEN an accepted breakdown of `[{bill_id: 1, quantity: 3}, {bill_id: 2, quantity: 0}, {bill_id: 3, quantity: 5}]`
- WHEN the operation is persisted
- THEN exactly one header is created and exactly two lines are created (for `bill_id: 1` and `bill_id: 3`)

### Requirement: Reporting Views, Menu, Access, And Record Rules

The backend MUST expose list, pivot, and graph views on count lines — including
a reason dimension — under a menu inside POS Reporting, with access rights and
multi-company record rules.

#### Scenario: Pivot groups by POS, date, move type, denomination, and reason (TransactionCase)

- GIVEN count lines across multiple POS configs, dates, move types, denominations, and reasons
- WHEN the pivot view's read_group is executed grouping by those dimensions
- THEN the results are correctly grouped and summed by each dimension

#### Scenario: Multi-company record rule hides other company's lines (TransactionCase)

- GIVEN count lines belonging to company A and company B
- WHEN a user scoped to company A searches count lines
- THEN only company A's lines are returned

#### Scenario: User without POS reporting access is denied (TransactionCase)

- GIVEN a user without the count-line read access right
- WHEN that user attempts to read count lines
- THEN an `AccessError` is raised

### Requirement: Statement Lines Filterable And Groupable By Reason

Cash-move `account.bank.statement.line` records MUST be filterable and
groupable by `reason_id` in the backend.

#### Scenario: Filter statement lines by reason (TransactionCase)

- GIVEN statement lines with different reasons
- WHEN a search is performed filtering on a specific `reason_id`
- THEN only statement lines with that reason are returned
