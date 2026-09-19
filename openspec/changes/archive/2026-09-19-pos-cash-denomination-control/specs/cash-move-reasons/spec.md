# Cash Move Reasons Specification

## Purpose

A configurable, company-scoped catalog of cash-move reasons that every POS
cash move must carry. The catalog seeds a single out-only "Vault" reason and
enforces that vault reasons can never be used for cash IN, laying the
groundwork for a future Vault Status feature without building it here.

## Requirements

### Requirement: Reason Catalog Model

`pos.cash.move.reason` MUST exist with fields: `name` (translatable),
`direction` (`out` / `in` / `both`), `is_vault` (Boolean), `sequence`,
`active`, and `company_id` (optional; empty means shared across companies).

#### Scenario: Create a reason with direction and vault flag (TransactionCase)

- GIVEN a request to create a reason with `name="Bank Deposit"`, `direction="out"`, `is_vault=False`
- WHEN the record is created
- THEN it is stored with those exact field values

### Requirement: Vault Reasons Must Be Out-Only

A model constraint MUST reject any reason with `is_vault=True` whose direction
is not `out`, both on create and on write.

#### Scenario: Creating a vault reason with direction "in" is rejected (TransactionCase)

- GIVEN a create call with `is_vault=True`, `direction="in"`
- WHEN the record is created
- THEN `ValidationError` is raised

#### Scenario: Creating a vault reason with direction "both" is rejected (TransactionCase)

- GIVEN a create call with `is_vault=True`, `direction="both"`
- WHEN the record is created
- THEN `ValidationError` is raised

#### Scenario: Creating a vault reason with direction "out" succeeds (TransactionCase)

- GIVEN a create call with `is_vault=True`, `direction="out"`
- WHEN the record is created
- THEN it is created successfully

#### Scenario: Editing an existing reason to set is_vault=True with a non-out direction is rejected (TransactionCase)

- GIVEN an existing reason with `direction="in"` and `is_vault=False`
- WHEN it is written with `is_vault=True`
- THEN `ValidationError` is raised

### Requirement: Seed Data — Exactly One Vault Reason

The module MUST seed, with `noupdate="1"`, exactly one reason named "Vault"
with `direction="out"` and `is_vault=True`. No "From vault" or any other
inbound vault reason MUST be seeded.

#### Scenario: Exactly one seeded Vault reason exists after install (TransactionCase)

- GIVEN the module has been installed
- WHEN reasons with `is_vault=True` are searched
- THEN exactly one is found, named "Vault", with `direction="out"`

### Requirement: Default Cash-Out Reason On `pos.config`

`pos.config.default_cash_out_reason_id` MUST default to the seeded "Vault"
reason. Every `pos.config` record that existed before install MUST receive
this default via a post-init hook, since the field default cannot resolve the
seed data before the column is created.

#### Scenario: New POS config defaults to the Vault reason (TransactionCase)

- GIVEN a newly created `pos.config` record after the module is installed
- WHEN `default_cash_out_reason_id` is read
- THEN it refers to the seeded "Vault" reason

#### Scenario: Existing POS config gets the Vault default after install (TransactionCase)

- GIVEN a `pos.config` record that existed before the module was installed
- WHEN the module's post-init hook runs
- THEN `default_cash_out_reason_id` on that record refers to the seeded "Vault" reason

#### Scenario: Missing or archived default reason yields no preselection (Hoot)

- GIVEN a POS config whose `default_cash_out_reason_id` is empty or refers to an archived reason
- WHEN the cash-out popup opens
- THEN no reason is preselected, and the user must pick one explicitly

### Requirement: Reasons Loaded To The POS Frontend

Active reasons MUST be loaded to the POS frontend through `pos.load.mixin`,
scoped to the session's company (its own reasons plus shared, company-less
reasons).

#### Scenario: POS receives active reasons matching its company (Hoot)

- GIVEN active reasons belonging to the session's company and shared reasons
- WHEN the POS loads its data
- THEN both sets are present in the loaded reasons, and reasons of other companies are absent

### Requirement: Pure Reason Validation Rule

The domain MUST validate a reason value object against a move type and a
company: a `None` reason MUST be treated as an error (missing reason), an
inactive reason MUST be rejected, a reason belonging to a different company
(and not shared) MUST be rejected, and the reason's direction MUST be
compatible with the move type (`out` accepts `out`/`both`; `in` accepts
`in`/`both`). A vault reason (`is_vault=True`) MUST be compatible only with
`out`.

#### Scenario: Missing reason is rejected (domain unit)

- GIVEN `reason=None`
- WHEN reason validation runs for any move type
- THEN validation fails with "reason is required"

#### Scenario: Inactive reason is rejected (domain unit)

- GIVEN a reason value object with `active=False`
- WHEN reason validation runs
- THEN validation fails with "reason is inactive"

#### Scenario: Other-company reason is rejected (domain unit)

- GIVEN a reason scoped to company B and a move for company A
- WHEN reason validation runs
- THEN validation fails with "reason not allowed for this company"

#### Scenario: Shared (company-less) reason is accepted across companies (domain unit)

- GIVEN a reason with no company set and a move for any company
- WHEN reason validation runs
- THEN the company check passes

#### Scenario: Out move accepts out or both direction reasons (domain unit)

- GIVEN move type `out` and a reason with `direction="out"` or `direction="both"`
- WHEN reason validation runs
- THEN the direction check passes

#### Scenario: In move accepts in or both direction reasons (domain unit)

- GIVEN move type `in` and a reason with `direction="in"` or `direction="both"`
- WHEN reason validation runs
- THEN the direction check passes

#### Scenario: Out move rejects an in-direction reason (domain unit)

- GIVEN move type `out` and a reason with `direction="in"`
- WHEN reason validation runs
- THEN validation fails with "reason direction incompatible with move type"

#### Scenario: In move rejects an out-direction reason (domain unit)

- GIVEN move type `in` and a reason with `direction="out"`
- WHEN reason validation runs
- THEN validation fails with "reason direction incompatible with move type"

#### Scenario: Vault reason is rejected for an in move (domain unit)

- GIVEN move type `in` and a reason with `is_vault=True` (necessarily `direction="out"`)
- WHEN reason validation runs
- THEN validation fails, because a vault reason is only compatible with `out`

#### Scenario: Vault reason is accepted for an out move (domain unit)

- GIVEN move type `out` and a reason with `is_vault=True`, `direction="out"`
- WHEN reason validation runs
- THEN validation passes

### Requirement: Reason Selector And Note In The Cash Move Popup

The cash move popup MUST show a reason selector filtered to reasons whose
direction matches the selected move type (or is `both`). For cash OUT, the
selector MUST be preselected with the POS's default cash-out reason unless an
initial reason prop overrides it; other reasons MUST remain selectable. The
existing free-text reason field becomes an optional note. Confirm MUST be
disabled until a reason is selected.

#### Scenario: OUT popup preselects the POS default reason (Hoot)

- GIVEN the popup opens in "out" mode and the POS has a default cash-out reason
- WHEN the popup renders
- THEN the reason selector is preselected with that default

#### Scenario: IN popup has no preselection (Hoot)

- GIVEN the popup opens in "in" mode
- WHEN the popup renders
- THEN no reason is preselected

#### Scenario: Selector filters reasons by direction (Hoot)

- GIVEN reasons of direction `in`, `out`, and `both` exist
- WHEN the popup is in "out" mode
- THEN only `out` and `both` reasons are offered in the selector

#### Scenario: Confirm is disabled until a reason is selected (Hoot)

- GIVEN the popup is open with no reason selected
- WHEN the user attempts to confirm
- THEN the confirm action is disabled or blocked

### Requirement: Reason Transport And Mandatory Server Validation

`reason_id` MUST travel in `extras['reason_id']` to `try_cash_in_out`. The
server MUST validate it using the pure reason validation rule before any
`account.bank.statement.line` is created, and MUST raise `UserError` for a
missing, inactive, wrong-company, direction-incompatible, or (for cash IN)
vault reason.

#### Scenario: Missing reason_id is rejected before any statement line is created (TransactionCase)

- GIVEN a call to `try_cash_in_out` with no `extras['reason_id']`
- WHEN the call is made
- THEN `UserError` is raised and no `account.bank.statement.line` is created

#### Scenario: Inactive reason is rejected (TransactionCase)

- GIVEN `extras['reason_id']` refers to an inactive reason
- WHEN `try_cash_in_out` is called
- THEN `UserError` is raised and no statement line is created

#### Scenario: Other-company reason is rejected (TransactionCase)

- GIVEN `extras['reason_id']` refers to a reason of another company
- WHEN `try_cash_in_out` is called
- THEN `UserError` is raised and no statement line is created

#### Scenario: Direction-incompatible reason is rejected (TransactionCase)

- GIVEN `_type='out'` and `extras['reason_id']` refers to an `in`-only reason
- WHEN `try_cash_in_out` is called
- THEN `UserError` is raised and no statement line is created

#### Scenario: Vault reason on cash-in is rejected (TransactionCase)

- GIVEN `_type='in'` and `extras['reason_id']` refers to the seeded Vault reason
- WHEN `try_cash_in_out` is called
- THEN `UserError` is raised and no statement line is created

#### Scenario: Valid reason is accepted and stored (TransactionCase)

- GIVEN a valid, direction-compatible, active, same-company reason
- WHEN `try_cash_in_out` is called
- THEN the call succeeds and the statement line stores that `reason_id`

### Requirement: Reason Storage And `payment_ref` Composition

`reason_id` MUST be stored on `account.bank.statement.line` and, for cash
moves, on the count header. `payment_ref` MUST keep the stock shape
(`session - type - text`), where `text` is the reason's name, followed by the
note when a note is given.

#### Scenario: payment_ref contains only the reason name when no note is given (TransactionCase)

- GIVEN a cash move with a reason and no note
- WHEN `payment_ref` is composed
- THEN its text segment equals the reason's name

#### Scenario: payment_ref contains the reason name followed by the note when given (TransactionCase)

- GIVEN a cash move with a reason and a note "till audit"
- WHEN `payment_ref` is composed
- THEN its text segment is the reason name followed by "till audit"

#### Scenario: reason_id is stored on the statement line (TransactionCase)

- GIVEN an accepted cash move
- WHEN the resulting `account.bank.statement.line` is inspected
- THEN its `reason_id` matches the reason used

#### Scenario: reason_id is stored on the count header for cash moves (TransactionCase)

- GIVEN an accepted, counted cash move
- WHEN the count header is inspected
- THEN its `reason_id` matches the reason used

### Requirement: Backend Views And Security

Reasons MUST have backend list and form views under a configuration menu
inside POS Configuration, with access rights and multi-company record rules.

#### Scenario: Reasons menu is accessible under POS Configuration (TransactionCase)

- GIVEN a user with POS configuration access
- WHEN the POS Configuration menu is opened
- THEN a menu item for cash move reasons is present and opens the reason list view

#### Scenario: Multi-company record rule hides other company's reasons (TransactionCase)

- GIVEN reasons scoped to company A and company B
- WHEN a user scoped to company A searches reasons
- THEN only company A's reasons and shared reasons are returned

### Requirement: Vault Status Readiness Invariant

Every accepted POS cash move MUST have exactly one reason, and no statement
line with an `is_vault=True` reason MUST ever represent a cash IN, so a future
Vault Status feature can safely sum vault-reason outflows without additional
filtering logic.

#### Scenario: Every created cash-move statement line has a non-null reason (TransactionCase)

- GIVEN any accepted cash move created after this module is installed
- WHEN its statement line is inspected
- THEN `reason_id` is set

#### Scenario: No statement line pairs a vault reason with an inflow (TransactionCase)

- GIVEN the full set of statement lines whose reason has `is_vault=True`
- WHEN their amounts are inspected
- THEN none represents a cash IN (all are outflows), because vault reasons are enforced out-only end to end
