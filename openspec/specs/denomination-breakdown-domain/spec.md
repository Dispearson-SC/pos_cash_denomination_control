# Denomination Breakdown Domain Specification

## Purpose

Pure-Python (no ORM imports) rules for computing and validating a per-denomination
cash breakdown. These functions are the single source of truth for "is this
breakdown valid" and are called by thin Odoo model adapters at every enforcement
point (opening, cash IN/OUT, closing).

## Requirements

### Requirement: Compute Breakdown Total

The domain MUST compute the total of a breakdown as Σ(quantity × bill_value) over
all supplied lines, where each line carries `bill_id`, `bill_value`, and `quantity`.

#### Scenario: Sum of multiple denominations (domain unit)

- GIVEN lines `[(bill_id=1, bill_value=100, quantity=3), (bill_id=2, bill_value=50, quantity=2)]`
- WHEN the total is computed
- THEN the result is `400` (3×100 + 2×50)

#### Scenario: Empty breakdown yields zero total (domain unit)

- GIVEN an empty list of lines
- WHEN the total is computed
- THEN the result is `0`

### Requirement: Validate Non-Negative Integer Quantities

The domain MUST reject any breakdown line whose quantity is negative or is not an
integer value, and MUST accept quantities that are zero or positive integers.

#### Scenario: Negative quantity is rejected (domain unit)

- GIVEN a line with `quantity=-1`
- WHEN the breakdown is validated
- THEN validation fails with an error identifying the offending line and reason "negative quantity"

#### Scenario: Non-integer quantity is rejected (domain unit)

- GIVEN a line with `quantity=2.5`
- WHEN the breakdown is validated
- THEN validation fails with an error identifying the offending line and reason "non-integer quantity"

#### Scenario: Zero and positive integer quantities are accepted (domain unit)

- GIVEN lines with `quantity=0` and `quantity=5`
- WHEN the breakdown is validated against a matching amount and allowed bills
- THEN both lines pass the quantity check

### Requirement: Validate Bills Are In The Allowed Set

The domain MUST reject any breakdown line whose `bill_id` is not a member of the
`allowed_bill_ids` set passed by the caller (the POS config's allowed bills).

#### Scenario: Disallowed bill is rejected (domain unit)

- GIVEN `allowed_bill_ids={1, 2}` and a line with `bill_id=99`
- WHEN the breakdown is validated
- THEN validation fails with an error identifying `bill_id=99` as "not allowed for this POS"

#### Scenario: Allowed bill is accepted (domain unit)

- GIVEN `allowed_bill_ids={1, 2}` and a line with `bill_id=1`
- WHEN the breakdown is validated
- THEN the bill-membership check for that line passes

### Requirement: Validate Sum Matches Declared Amount Within Rounding

The domain MUST compare the computed breakdown total to the declared amount using
currency rounding (not exact float equality) and MUST reject a breakdown whose
total differs from the declared amount by more than the rounding tolerance.

#### Scenario: Sum matches exactly (domain unit)

- GIVEN lines totaling `500.00` and a declared amount of `500.00` with rounding `0.01`
- WHEN the breakdown is validated
- THEN the sum-match check passes

#### Scenario: Sum within rounding tolerance is accepted (domain unit)

- GIVEN lines totaling `500.004` and a declared amount of `500.00` with rounding `0.01`
- WHEN the breakdown is validated
- THEN the sum-match check passes because the difference is below the rounding tolerance

#### Scenario: Sum mismatch beyond rounding is rejected (domain unit)

- GIVEN lines totaling `450.00` and a declared amount of `500.00` with rounding `0.01`
- WHEN the breakdown is validated
- THEN validation fails with an error stating the computed total does not match the declared amount

### Requirement: Validate Breakdown Presence When Required

The domain MUST reject a missing or empty breakdown when `required=True`. When
`required=False`, the domain MUST accept the absence of a breakdown as valid, and
MUST still apply quantity, bill-membership, and sum-match checks to any breakdown
that is supplied even though it was not required.

#### Scenario: Required breakdown missing is rejected (domain unit)

- GIVEN `required=True` and no breakdown lines (or `None`)
- WHEN the breakdown is validated
- THEN validation fails with an error stating a breakdown is required

#### Scenario: Breakdown not required and absent is accepted (domain unit)

- GIVEN `required=False` and no breakdown lines
- WHEN the breakdown is validated
- THEN validation passes with no errors

#### Scenario: Breakdown not required but supplied is still checked (domain unit)

- GIVEN `required=False` and a supplied breakdown whose sum does not match the amount
- WHEN the breakdown is validated
- THEN validation fails on the sum-match rule, because a supplied breakdown is always checked for correctness
