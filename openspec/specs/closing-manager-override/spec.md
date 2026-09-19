# Closing Manager Override Specification

## Purpose

With the closing denomination toggle on, the rule that lets a session close
from the back office without a recorded closing breakdown only for POS
managers, independent of the entry point that reaches the closing guard. This
guarantees the POS UI closing path (which always records a breakdown under
enforcement) is never itself blocked.

## Requirements

### Requirement: Closing Without A Recorded Breakdown Requires Manager

With the closing toggle on, when no closing count exists for the session, only
a user in `point_of_sale.group_pos_manager` MUST be allowed to close the
session; any other user MUST receive a `UserError`.

#### Scenario: Non-manager closing without a breakdown is rejected (TransactionCase)

- GIVEN the closing toggle is on, no closing count exists for the session, and the acting user is not a POS manager
- WHEN the session close is attempted
- THEN `UserError` is raised and the session is not closed

#### Scenario: Manager closing without a breakdown succeeds and flags the session (TransactionCase)

- GIVEN the closing toggle is on, no closing count exists for the session, and the acting user is a POS manager
- WHEN the session close is attempted
- THEN the session closes successfully and is flagged as closed without a denomination count

#### Scenario: Non-manager closing with a recorded breakdown succeeds (tour)

- GIVEN the closing toggle is on and the POS UI recorded a closing breakdown via `post_closing_cash_details`
- WHEN a non-manager cashier closes the session from the POS UI
- THEN the session closes successfully and is not flagged

### Requirement: Guard Applies At A Common Choke Point Regardless Of Entry Point

The guard MUST be enforced at a point every public close path reaches, so that
the back-office "Close Session & Post Entries" button, the imbalance wizard,
and direct RPC calls to `action_pos_session_validate` or
`action_pos_session_close` all produce the same outcome for the same
(has-count, is-manager) combination.

#### Scenario: Non-manager direct RPC to action_pos_session_validate is rejected without a breakdown (TransactionCase)

- GIVEN the closing toggle is on, no closing count exists, and the caller is not a manager
- WHEN `action_pos_session_validate` is called directly
- THEN `UserError` is raised

#### Scenario: Non-manager via the imbalance wizard is rejected without a breakdown (TransactionCase)

- GIVEN the closing toggle is on, no closing count exists, and the caller is not a manager
- WHEN the session close is attempted through `wizard/pos_close_session_wizard.py`
- THEN `UserError` is raised

#### Scenario: Manager via any public close path succeeds and is flagged (TransactionCase)

- GIVEN the closing toggle is on, no closing count exists, and the caller is a manager
- WHEN the session is closed via the back-office button, the imbalance wizard, or a direct call to `action_pos_session_validate` or `action_pos_session_close`
- THEN each path succeeds and flags the session identically

### Requirement: No Accounting Entry On Rejection

When the guard rejects a closing attempt, no accounting entry MUST be created,
and any session state changes made earlier in the same call chain (for example
by `action_pos_session_closing_control`) MUST be rolled back with the
transaction.

#### Scenario: Rejected closing leaves no journal entries and no state change (TransactionCase)

- GIVEN the closing toggle is on, no closing count exists, and the caller is not a manager
- WHEN the session close is attempted and rejected
- THEN no `account.move` is created for the session and the session's state is unchanged from before the attempt

### Requirement: Manager-Closing Flag And Audit Trail

When a manager closes a session without a recorded breakdown, the system MUST
store a Boolean flag (working name `closed_without_denomination_count`) plus
the acting user and the date/time, and MUST post a chatter message. The flag
MUST be visible on session views and MUST be usable as a search filter and
group-by.

#### Scenario: Flag, user, date/time, and chatter are recorded (TransactionCase)

- GIVEN a manager closes a session without a recorded breakdown
- WHEN the session record is inspected
- THEN `closed_without_denomination_count` is `True`, the closing user and date/time are stored, and a chatter message documenting the manager override exists

#### Scenario: Sessions are filterable and groupable by the flag (TransactionCase)

- GIVEN sessions with and without the flag set
- WHEN a search or group-by is performed on `closed_without_denomination_count`
- THEN only flagged sessions are returned by the filter, and the group-by correctly buckets flagged vs. unflagged sessions

### Requirement: Toggle Off Restores Stock Behavior

With the closing toggle off, the guard MUST NOT apply: any user MUST be able
to close a session without a recorded breakdown, exactly as in stock Odoo.

#### Scenario: Non-manager closes without a breakdown when toggle is off (TransactionCase)

- GIVEN the closing toggle is off
- WHEN a non-manager closes a session with no closing count recorded
- THEN the session closes successfully and is not flagged

### Requirement: Rescue Sessions Follow The Same Rule

Rescue sessions, which stock Odoo only closes from the back office, MUST
follow the same manager-only rule and flagging behavior as any other session.

#### Scenario: Manager closes a rescue session without a breakdown and it is flagged (TransactionCase)

- GIVEN a rescue session with the closing toggle on and no closing count
- WHEN a manager closes it
- THEN it closes successfully and is flagged

#### Scenario: Non-manager closing a rescue session without a breakdown is rejected (TransactionCase)

- GIVEN a rescue session with the closing toggle on and no closing count
- WHEN a non-manager attempts to close it
- THEN `UserError` is raised

### Requirement: Manager Check Uses The Real Acting User Before Any Sudo Escalation

The manager-group check MUST evaluate `self.env.user` (the real acting user),
performed before any `sudo()` context switch inside the closing validation
chain, so that internal sudo calls cannot mask the acting user's actual group
membership.

#### Scenario: Check uses the acting user's own groups, not an escalated context (TransactionCase)

- GIVEN a non-manager user triggers a close path that internally uses `sudo()` for unrelated writes
- WHEN the manager-group check runs
- THEN it evaluates the original non-manager user's group membership and rejects the closing
