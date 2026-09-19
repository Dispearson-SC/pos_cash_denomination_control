# Proposal: POS Cash Denomination Control

## Intent

Odoo 19 POS lets a cashier type any cash amount at session opening, cash in/out, and closing. The existing `MoneyDetailsPopup` breakdown is optional. Only its total and a free-text note reach the server, so the structured per-denomination count is discarded. Cash moves also carry only a free-text reason. This causes five problems:

1. **Control**: operators cannot require a physical count. A cashier can declare a cash-out of 1,000 without saying which bills left the drawer.
2. **Reporting**: denominations cannot be analyzed. Questions like "which denominations were withdrawn per POS per day" have no data source.
3. **Classification**: cash moves cannot be classified reliably. The vault ("bóveda") is the normal destination of cash withdrawals, but a withdrawal to the vault cannot be told apart from any other withdrawal, because the reason is free text.
4. **Unused cash-in**: the business does not put cash into registers through the POS, and money never returns from the vault to a register. Stock Odoo still offers "Cash In" to every user who has the cash-move permission, and it has no per-POS switch for it.
5. **Cash accumulation**: nothing tells the cashier that the drawer holds too much cash and should be emptied into the vault. Stock POS has no client-side live cash balance; expected cash is only computed on the server at closing.

This change adds:
- an opt-in, per-POS requirement for these cash operations. When a requirement is on, the cashier must enter a denomination breakdown. The breakdown is validated on the server and saved as structured, reportable lines. When the closing requirement is on, only POS managers may close a session from the back office without a breakdown, and such closings are flagged;
- a configurable **cash-move reason catalog**. Every POS cash move must carry a reason from the catalog; the server rejects cash moves without one. The seeded "Vault" reason is the default for cash OUT. The vault is **out-only**: vault reasons can only be used for cash OUT. This data is the foundation for a future "Vault Status" feature that does not mix in other withdrawal types;
- a per-POS **cash-in control** toggle, off by default. When it is off, the POS does not offer "Cash In" and the server rejects cash-in requests for that POS;
- a per-POS **vault withdrawal alert**: a configurable cash threshold. When the expected cash in the drawer reaches it, the POS shows a non-blocking notification and a persistent navbar indicator that opens a pre-filled vault cash-out.

Success is defined by the Success Criteria section below.

**Stock behavior guarantee (with deliberate deviations).** With every denomination toggle off and the alert threshold at 0, opening, closing, and selling MUST behave exactly like stock Odoo. Cash moves deviate from stock in three deliberate ways:
- the required reason selector is always active once the module is installed (see Approach 6);
- the server rejects any cash move without a reason, including callers other than the POS UI (see Approach 6);
- **cash IN is disabled by default on every POS**, including POS configs that exist when the module is installed (see Approach 7). An operator must enable it per POS to restore the stock cash-in behavior.

**Edition impact**: This targets **both Community and Enterprise**. The module depends only on `point_of_sale` and ships no Enterprise-only code. POS UI patches (including the navbar indicator) must survive Enterprise's POS asset overrides; this is verified at deploy time.

## Scope

### In Scope
- New addon `pos_cash_denomination_control` (OCA-style layout). It depends only on `point_of_sale` and must coexist with `pos_hr`, where the cashier may be an `hr.employee`.
- **Test runner provisioning (first task)**: docker-compose with Odoo 19 and Postgres, plus the documented test command, so strict TDD can be enabled for all later tasks.
- **Pure-Python domain layer** (no ORM imports) that:
  - computes the breakdown total as Σ(quantity × bill value);
  - validates a breakdown: quantities are non-negative integers, bills are in the allowed set, the sum matches the amount within currency rounding, and the breakdown is present when required;
  - validates a cash-move reason: it is present (a missing reason is an error), active, allowed for the company, and its direction is compatible with the move type (`out` accepts `out`/`both`; `in` accepts `in`/`both`). A vault reason is only compatible with `out`;
  - decides whether a cash move type is allowed for a POS (cash IN only when cash-in is enabled);
  - decides whether a closing without a breakdown is allowed (toggle off, or breakdown present, or caller is a manager) and whether it must be flagged;
  - computes expected drawer cash (opening balance + default cash method payments of closed orders + sum of cash statement line amounts) and decides whether a vault withdrawal is required (`threshold > 0` and `expected >= threshold`, compared with currency rounding).
- **Cash-in control**:
  - new stored Boolean on `pos.config` (working name `allow_cash_in`; the final name is the design's choice), **default `False`**, shown in POS settings when the POS has cash control, and delivered to the POS frontend;
  - when off, the `CashMovePopup` hides the "Cash In" button and opens in "out" mode (stock Odoo already initializes the popup type to `"out"`, `cash_move_popup.js:31`; the patch keeps it there);
  - when off, `try_cash_in_out` raises `UserError` for `_type == 'in'` on that session's config, regardless of the UI. This also rejects offline-queued cash-in replays;
  - it is additive to the stock user-level permission. Odoo 19 has no per-POS cash-in switch; the only gate is `res.users._has_cash_move_permission()` (`res_users.py:24`), checked in `try_cash_in_out` (`pos_session.py:1880`) and exposed to the frontend as `_has_cash_move_perm` (`pos_config.py:290`). That permission gates both IN and OUT and stays unchanged. Cash IN requires both the permission and the toggle;
  - the README documents that installing the module disables cash-in on all existing POS configs, and how to re-enable it.
- **`pos.config` denomination toggles**: four independent stored Booleans, all default off:
  - opening cash;
  - cash OUT;
  - cash IN (visible and relevant only when cash-in is enabled for the POS);
  - closing cash count.

  They appear in POS settings only when the POS has cash control, and they are delivered to the POS frontend.
- **Cash-move reason catalog**:
  - new model `pos.cash.move.reason`: `name` (translatable), `direction` (`out` / `in` / `both`), `is_vault` (Boolean), `sequence`, `active`, `company_id` (optional; empty means shared across companies);
  - a model constraint: a reason with `is_vault=True` must have direction `out`. The `direction` field stays available with all three values for non-vault reasons;
  - seed data with `noupdate="1"`: one record, "Vault" (direction `out`, `is_vault=True`). There is no "From vault" reason;
  - `pos.config.default_cash_out_reason_id`, which defaults to the seeded "Vault" reason. Existing POS configs get this value at install time;
  - backend list and form views and a configuration menu under POS Configuration, with access rights and multi-company record rules;
  - reasons are loaded to the POS through `pos.load.mixin`.
- **Reason on cash moves (always active, required on the server)**:
  - the cash move popup shows a reason selector filtered by direction. For cash OUT, it is preselected with the POS default. Other reasons can still be selected;
  - Odoo's current free-text reason becomes an optional **note**;
  - `reason_id` travels in `extras['reason_id']` in `try_cash_in_out` and is validated on the server. **A missing `reason_id` raises `UserError`** before any statement line is created (settled);
  - `reason_id` is stored on `account.bank.statement.line` (new field) and on the count header when a count exists;
  - `payment_ref` keeps the stock shape (`session - type - text`), where the text is the reason name followed by the note when a note is given. This keeps existing reports and searches working.
- **Structured count persistence**: a new header + lines model pair (see Approach), linked to the session, company, move type, cashier (user, and employee when `pos_hr` is installed), reason (cash moves), and, for cash moves, `account.bank.statement.line`. Each line stores the `pos.bill` reference, a snapshot of the bill value, the quantity, and a stored subtotal.
- **Server-side enforcement** for each denomination toggle that is on, at these entry points:
  - opening: `set_opening_control` → `_set_opening_control_data`;
  - cash IN and OUT: `try_cash_in_out` through `extras['denomination_lines']`;
  - closing (POS UI): `post_closing_cash_details`.

  Each RPC payload is self-contained, so offline replay is safe.
- **Back-office closing control (closing toggle on, settled)**: closing without a recorded closing breakdown is allowed only for `point_of_sale.group_pos_manager`; others get a `UserError`. A manager closing without a breakdown flags the session (stored Boolean, working name `closed_without_denomination_count`, plus user and date/time) and posts a chatter message; the flag is shown on session views and usable as a filter and group-by. The POS UI path stays enforced and is not blocked (see Approach 9).
- **Vault withdrawal alert (settled)**: a `pos.config` Monetary threshold (working name `vault_withdrawal_threshold`, default `0` = disabled, visible and effective only with cash control, delivered to the frontend); a server method returning expected drawer cash and the alert state, reusing the `get_closing_control_data` formula (`pos_session.py:778`); refresh on load, order sync, and cash move; a non-blocking "Vault withdrawal required" notification and a persistent navbar indicator that opens a vault cash-out. It never blocks any POS function (see Approach 10).
- **POS UI**:
  - a new id-keyed denomination breakdown popup (payload `[{bill_id, quantity}]`);
  - patches to `OpeningControlPopup`, `CashMovePopup` (cash-in visibility, IN and OUT breakdown separately, reason selector, optional initial type and reason props), and `ClosePosPopup` (cash payment method only). With a toggle on, the free amount input is read-only and the amount comes only from the popup;
  - a navbar indicator and the alert refresh logic.
- **Backward-compatible notes**: the human-readable breakdown text is still appended to the opening and closing notes and chatter, as Odoo does today.
- **Reporting**: backend list, pivot, and graph views on the count lines, including a reason dimension, plus a menu under POS Reporting, with multi-company record rules and access rights. Cash-move statement lines can be filtered and grouped by reason. Sessions can be filtered by the "closed without denomination count" flag.
- **README** (OCA `readme/` fragments): configuration, the cash-in default-off behavior change and how to re-enable cash-in per POS, the required reason on every cash move (and its effect on other callers), the manager-only back-office closing rule, and the vault withdrawal alert.
- **Tests at every layer**:
  - domain unit tests (move-type rule, vault-direction rule, missing reason, closing-bypass rule, expected cash and threshold rule);
  - `TransactionCase` tests for models, reasons (including the vault `out`-only constraint and missing-reason rejection), cash-in rejection, enforcement, back-office closing (manager allowed and flagged, non-manager rejected, POS path unaffected), and the alert method (including parity with `get_closing_control_data`);
  - Hoot JS unit tests for the popup, the reason selector, the patches, the popup without the "Cash In" button, and the navbar indicator;
  - `HttpCase` tours for the opening, cash-out (with reason), rejection, and vault alert flows.

### Out of Scope
- The "Vault Status" report or balance, and any vault ledger. The reason model must not prevent it, but it is not built here.
- Any flow that moves money from the vault back to a register. It does not exist in the business, and no reason supports it.
- Accounting transfers between the POS cash journal and a vault journal or safe. Cash moves stay the stock statement lines.
- A separate on/off toggle for the reason catalog (see Approach 6).
- Allowed reasons per POS. All active reasons of the company that match the direction are selectable.
- Per-user or per-role toggles; toggles are per POS only. The stock user-level cash-move permission is reused, not replaced. (The manager-only back-office closing rule reuses the stock `group_pos_manager` group; it adds no new role.)
- Cash-in/out amount limits or approval thresholds. The vault alert threshold only notifies; it never limits or blocks.
- Real-time push of the alert state between devices (bus notifications). Each device refreshes on its own events.
- Blocking sales, payments, or closing when the vault threshold is reached.
- Non-cash payment methods (card, bank, and so on) at closing. They stay unchanged.
- A new denomination catalog. The existing `pos.bill` and `pos.config.default_bill_ids` are reused; operators add new coins and bills there.
- Changing or replacing the stock `MoneyDetailsPopup` behavior when toggles are off.
- Discrepancy thresholds or other changes to Odoo's existing closing-difference logic.
- Reasons on cash moves created outside `try_cash_in_out` (for example, closing difference lines or manual backend statement lines).

## Capabilities

`openspec/specs/` is empty (greenfield). All capabilities are new.

### New Capabilities
- `denomination-breakdown-domain`: pure rules for breakdown totals and validation (integer non-negative quantities, allowed bills, rounding-aware sum match, presence when required), independent of the ORM.
- `cash-denomination-config`: the four per-POS denomination toggles, their defaults, their visibility (cash control only; the cash-IN toggle only when cash-in is enabled), and their delivery to the POS frontend.
- `cash-in-control`: the per-POS cash-in toggle (default off, applied to existing configs at install), its settings visibility, frontend delivery, the popup behavior when off (no "Cash In" button, "out" mode), server rejection of `_type == 'in'` (including offline replays), its relation to the stock `_has_cash_move_permission()` (additive, both required), and the documented behavior change.
- `cash-count-records`: the persisted count header and lines (fields, snapshots, attribution, company, reason, link to statement lines) plus reporting views, menu, and access and record rules.
- `cash-denomination-enforcement`: server-side acceptance and rejection of opening, cash IN and OUT, and POS UI closing operations when their toggle is on. This includes offline-replay safety and keeping the text notes.
- `closing-manager-override`: with the closing toggle on, the rule for closing a session without a recorded closing breakdown (managers only, non-managers rejected), independent of the entry point (back-office button, imbalance wizard, direct RPC); the guarantee that the POS UI path is not blocked when it recorded a breakdown; the session flag, user, date/time, and chatter message; and the session views and filter that expose it.
- `pos-denomination-ui`: the id-keyed breakdown popup and the POS flow changes (read-only amount, forced breakdown, payload transport) for each toggle.
- `cash-move-reasons`: the reason catalog model, the vault `out`-only constraint, seed data (single "Vault" reason), the `pos.config` default cash-out reason, loading to the POS, the pure reason-validation rules (presence, active, company, direction, vault only on `out`), the reason selector and note in the cash move popup, `extras['reason_id']` transport, server validation including **rejection of a missing reason**, storage on the statement line and count header, `payment_ref` composition, and the backend views and security. It also records the invariant that keeps a future Vault Status possible: every POS cash move has exactly one reason, and every statement line with an `is_vault` reason is an outflow to the vault.
- `vault-withdrawal-alert`: the per-POS threshold (Monetary, 0 = disabled, visible only with cash control), the pure expected-cash and threshold rules, the server method and its parity with `get_closing_control_data`, the POS refresh triggers (load, order sync, cash move), the non-blocking notification, the persistent navbar indicator and its clearing rule, the one-click vault cash-out (out mode, vault reason preselected, stock permission respected), offline behavior (last known state), and the guarantee that it never blocks POS functions.

**Why separate capabilities**: `cash-in-control` forbids an operation type outright (denomination toggles only change how an amount is entered), has its own default and install-time change, and ships and reverts on its own. `closing-manager-override` adds a role exception, audit data, and a guard on methods the POS path also calls, so "the POS path is not blocked" becomes an explicit, testable requirement. `vault-withdrawal-alert` does not depend on denominations (only on cash control and, for the one-click cash-out, on `cash-move-reasons`) and reverts with threshold 0.

### Modified Capabilities
- None.

## Approach

1. **Layering (hexagonal-lite)**
   - A `domain/` package holds plain dataclasses and functions: `BreakdownLine(bill_id, bill_value, quantity)`, `compute_total()`, `validate_breakdown(lines, amount, allowed_bill_ids, rounding, required)`, `validate_reason(reason, move_type, company_id)` on a plain reason value object (a `None` reason is an error), a move-type rule (for example `validate_move_type(move_type, cash_in_allowed)`), a closing rule (for example `evaluate_closing(toggle_on, has_count, is_manager)` returning allowed / allowed-and-flag / rejected), and cash rules (`compute_expected_cash(opening, cash_payment_amounts, statement_line_amounts)`, `is_withdrawal_required(expected, threshold, rounding)`). They return typed errors or values and never import the ORM.
   - Odoo models are thin adapters. They fetch the config, allowed bills, currency rounding, the reason record, the session amounts, and the user's groups, call the domain, map errors to `UserError`/`ValidationError`, and persist records.

2. **Transport**
   - **Cash IN and OUT**: patch `CashMovePopup._prepareTryCashInOutPayload` to add `extras['denomination_lines']` and `extras['reason_id']`. This mirrors pos_hr's `employee_id` pattern, so the public signature does not change. The positional `reason` argument now carries the optional note. The server override checks, in this order and before any statement line is created: the stock permission (kept in the super call path), the cash-in toggle, the reason (missing → `UserError`), then the breakdown. `_prepare_account_bank_statement_line_vals` sets `reason_id` and composes `payment_ref` from the reason name and the note. Count records are then created and linked to the statement lines in the same sudo context.
   - **Opening**: add an optional kwarg to `set_opening_control(cashbox_value, notes, denomination_lines=None)`, sent through the currently unused `kwargs` slot of `pos.data.call`. The public method only passes the kwarg through. All logic lives in the inheritable `_set_opening_control_data`.

     **This is a deliberate, additive exception to the "DO NOT INHERIT THIS METHOD" docstring.** The signature becomes a strict superset, and no business logic is duplicated in the public method. It must be marked with a code comment and recorded as an ADR in the design.
   - **Closing**: add the same optional kwarg to `post_closing_cash_details(counted_cash, denomination_lines=None)`. The stock POS already sends `counted_cash` as a kwarg (`closing_popup.js:207-216`), so the new key travels next to it. This method records `cash_register_balance_end_real`. It applies to the cash payment method count only.

3. **Persistence model: header + lines (recommended)**
   - **Header** (`pos.cash.denomination.count`): session, config (related, stored), company (from session), move type (`opening`/`in`/`out`/`closing`), total, date, user, employee (optional field, filled when `pos_hr` data is available), reason (cash moves only), and a statement line link for cash moves.
   - **Lines** (`pos.cash.denomination.count.line`): `bill_id`, snapshot `bill_value`, `quantity`, stored `subtotal`, plus stored related header fields (session, config, company, move type, date, reason) so pivot and graph views group directly on lines.
   - **Rationale**: one count event maps to one header, which anchors the statement link, attribution, reason, and total; denormalized stored fields on lines keep reporting simple. Design may still revisit this choice.
   - The statement line is the source of truth for the reason. The header copies it so count reports do not need to join through the statement line.

4. **Employee attribution without a hard dependency on `pos_hr`**
   - Read `extras.get('employee_id')` for cash moves, and `session.employee_id` for opening and closing, only when that field exists (`'employee_id' in session._fields`).
   - Store the value in a Many2one declared conditionally, or as an integer plus a display name. The design decides which, because a Many2one to `hr.employee` normally requires the `hr` dependency.

5. **Frontend**
   - A new OWL popup component emits `[{bill_id, quantity}]` and the total.
   - Patches check `this.pos.config.<toggle>` to make the amount input read-only and to open the popup. They then pass the breakdown through the transport above and keep appending the note text.
   - The `CashMovePopup` patch adds a reason selector. Its options are the loaded reasons whose direction matches the selected type (or is `both`). When the type is OUT, it is preselected with `pos.config.default_cash_out_reason_id` unless an initial reason prop is given. When the type is IN, it has no preselection. Confirm is disabled until a reason is selected. The existing text field is relabeled as an optional note.
   - `CashMovePopup` declares a strict `static props` list (`cash_move_popup.js:21`), so the patch extends it with optional initial-type and initial-reason props, and `pos.cashMove()` (`pos_store.js:475`) is patched to forward them. Stock callers pass nothing and keep the stock behavior.
   - The `CashMovePopup` template is extended so the "Cash In" button renders only when the cash-in toggle is on. When it is off, the state type stays `"out"` and cannot be switched to `"in"`.

6. **Reason catalog decisions**
   - **Always active, no toggle.** The catalog is active as soon as the module is installed. A toggle would allow cash moves without a reason, which would create gaps in the data a future Vault Status depends on. Operators who do not care can keep the Vault default and never change it, so the cost is one preselected field.
   - **Vault is out-only (settled).** Money never returns from the vault to a register, so only one vault reason is seeded: "Vault" (`out`, `is_vault=True`). A model constraint (`@api.constrains('is_vault', 'direction')`) forbids `is_vault=True` with any direction other than `out`, so operators cannot create an inbound or `both` vault reason. The domain reason rule enforces the same invariant for defense in depth. The `direction` field keeps `in` / `out` / `both` for non-vault reasons.
   - **No per-POS allowed reasons.** All active reasons of the company (or shared ones) that match the direction are offered. Only the cash-out default is per POS. Per-POS allow-lists can be added later without a data migration.
   - **Server validation (settled)**: the reason must be present, exist, be active, belong to the session's company or be shared, and have a direction compatible with the move type. A call to `try_cash_in_out` without `extras['reason_id']` raises `UserError`. There is no fallback reason and no silent default to Vault. Accepted costs: cash moves queued offline before the upgrade, external scripts or modules that call `try_cash_in_out` without a reason, and core test `test_point_of_sale_flow.py:3212` fail while this module is installed (see Risks).
   - **Vault Status readiness**: because vault reasons are out-only, the future vault balance is the sum of the absolute amounts of statement lines whose reason has `is_vault=True`, grouped by company (and by POS or session when needed), minus any vault outflows recorded outside the POS (out of scope here). This change only has to guarantee that `reason_id` is stored, indexed, never defaulted silently to a vault reason, and never a vault reason on a cash IN.

7. **Cash-in control (settled)**
   - A stored Boolean on `pos.config`, default `False`. Because the column is created with a default, installing the module sets it to `False` on all existing POS configs. This is intended.
   - Server: in the `try_cash_in_out` override, when `_type == 'in'` and the session's config has cash-in off, raise `UserError` before any statement line or count record is created. This check does not depend on the UI, so it also covers offline-queued replays, scripts, and other callers.
   - Frontend: see Approach 5. The stock `_has_cash_move_perm` gate for opening the popup (`pos_store.js:1376`) is not changed, because cash OUT stays available.
   - The cash-IN denomination toggle is only shown in settings when cash-in is on. If cash-in is later turned off, the cash-IN denomination toggle keeps its stored value but has no effect; the design decides whether to reset it.

8. **Strict TDD and test order**: runner first, then the domain (RED/GREEN/REFACTOR), then cash-in control, reasons, vault alert, count models, enforcement, closing override, JS, and tours.

9. **Back-office closing control (settled)**
   - **Verified call graph** (`odoo-src`, read-only): the POS closing popup calls `post_closing_cash_details` (`closing_popup.js:207`), then `update_closing_control_state_session`, then `close_session_from_ui` (`closing_popup.js:238`). `close_session_from_ui` calls `action_pos_session_closing_control` (`pos_session.py:626`). The back-office "Close Session & Post Entries" button (`pos_session_view.xml:11`) and the imbalance wizard (`wizard/pos_close_session_wizard.py:18`) call the same method. `action_pos_session_closing_control` then goes through `action_pos_session_validate` / `action_pos_session_close` to `_validate_session`; `action_pos_session_validate` and `action_pos_session_close` are also public and RPC-callable.
   - **Consequence**: a guard that only checks "who is calling `action_pos_session_closing_control`" would wrongly block the POS path for non-managers. The guard must therefore key on **whether a closing count exists for the session**, not on the entry point:
     - closing toggle off → no change (stock);
     - a closing count exists (recorded by `post_closing_cash_details` under enforcement) → allowed, no flag. This covers the POS path, including the imbalance wizard reached from a POS redirect;
     - no closing count, user is a POS manager → allowed, session flagged (Boolean + user + date/time) and a chatter message posted;
     - no closing count, user is not a POS manager → `UserError`.
   - **Placement**: the guard sits at a choke point that every public close path reaches (candidates: `action_pos_session_close` or `_validate_session`), so direct RPC calls to `action_pos_session_validate` / `action_pos_session_close` cannot bypass it. The design picks the exact method and proves by test that the POS path, the back-office button, the wizard, and direct RPC all behave as above. The guard raises before `_validate_session` creates any accounting entry; the state write made earlier in `action_pos_session_closing_control` is rolled back with the transaction.
   - The manager check uses the real user (`self.env.user`), evaluated before any `sudo()` switch in `_validate_session` (`pos_session.py:427`).
   - Rescue sessions (closed only from the back office, `pos_session.py:399-408`) follow the same rule: managers may close them and they are flagged.

10. **Vault withdrawal alert (settled)**
    - **Expected cash**: stock POS keeps no live cash balance client-side. The server computes it only in `get_closing_control_data` (`pos_session.py:778-808`): `cash_register_balance_start` + default cash method payments of closed orders + `sum(statement_line_ids.amount)`. The module adds a session helper that collects the same inputs and calls the pure `compute_expected_cash`. It does not override `get_closing_control_data`; a parity test asserts that both return the same amount, so a future core change is detected.
    - **Server method** (working name `get_vault_withdrawal_state`): returns `{expected_cash, threshold, required}` for the session, with the same `group_pos_user` access check as `get_closing_control_data`. It returns `required = False` when cash control is off or the threshold is 0. Being server-side, it is correct when several devices share one session.
    - **Refresh**: on POS load, after each successful order sync, and after each successful cash move. The design may piggy-back the state on the order sync response instead of an extra RPC, if that is less invasive.
    - **Display**: on a transition from "not required" to "required" (and on load when already required), show one non-blocking notification "Vault withdrawal required". While required, show a persistent navbar indicator. It disappears only after a refresh reports expected cash below the threshold. Offline, the indicator keeps the last known state.
    - **One-click cash-out**: clicking the indicator calls the patched `pos.cashMove()` with type `out` and a vault reason: the POS default cash-out reason when it is a vault reason, otherwise the first active vault reason by sequence, otherwise no preselection. When the user lacks the stock cash-move permission, the click shows a notification instead of opening the popup, matching the stock gate. All other reason, cash-in, and denomination rules apply unchanged.
    - **Never blocking**: the alert adds no checks to sales, payments, cash moves, or closing.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `docker-compose.yml`, test docs | New | Odoo 19 + Postgres test runner (first task) |
| `pos_cash_denomination_control/__manifest__.py`, `__init__.py`, `hooks.py` | New | Addon skeleton, depends `point_of_sale`; post-init hook sets the default cash-out reason on existing configs |
| `pos_cash_denomination_control/domain/` | New | Pure-Python breakdown, reason, move-type, closing-override, expected-cash, and threshold rules |
| `pos_cash_denomination_control/models/pos_config.py` | New (inherit) | Cash-in toggle (default off), four denomination toggles, `default_cash_out_reason_id`, vault withdrawal threshold, frontend delivery |
| `pos_cash_denomination_control/models/pos_cash_move_reason.py` | New | Reason catalog model, vault `out`-only constraint, `pos.load.mixin` loading |
| `pos_cash_denomination_control/models/account_bank_statement_line.py` | New (inherit) | `reason_id` field on statement lines |
| `pos_cash_denomination_control/models/pos_cash_denomination_count*.py` | New | Header + lines models (with reason) |
| `pos_cash_denomination_control/models/pos_session.py` | New (inherit) | Cash-in rejection, required reason, opening/cash move/closing enforcement, `payment_ref`, persistence, closing-override guard and flag fields, expected-cash helper and alert method, reason model registered in `_load_pos_data_models` |
| `pos_cash_denomination_control/data/pos_cash_move_reason_data.xml` | New | Seeded "Vault" reason only (`out`, `is_vault`, `noupdate`) |
| `pos_cash_denomination_control/security/` | New | Access rights, multi-company record rules (counts and reasons) |
| `pos_cash_denomination_control/views/` | New | POS settings (cash-in toggle, denomination toggles, default reason, threshold), reason configuration views/menu, count list/pivot/graph, reporting menu, statement line reason filter, session flag fields and filter |
| `pos_cash_denomination_control/static/src/` | New | Breakdown popup, reason selector, `CashMovePopup` template/logic/props patch, `pos.cashMove()` patch, navbar indicator, alert refresh logic, patches to opening/closing popups |
| `pos_cash_denomination_control/static/tests/` | New | Hoot unit tests (reason mock data, cash-in disabled popup, navbar indicator), tours |
| `pos_cash_denomination_control/tests/` | New | Domain unit, TransactionCase, HttpCase tests |
| `pos_cash_denomination_control/readme/` | New | OCA README fragments, including behavior changes and known conflicts |
| `pos_cash_denomination_control/i18n/` | New | Translatable reason names and UI strings |
| `odoo-src/` | None | Read-only reference; never edited |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Installing the module disables cash-in on all existing POS configs; users who relied on it lose it without warning | Med (intended by the business) | Documented in the README and release notes. Re-enable per POS in settings. Covered by an install test that asserts existing configs have cash-in off |
| Core or third-party tests and scripts that perform a cash IN through `try_cash_in_out` fail while this module is installed (cash-in is off by default) | Med | Document it. In CI, run core tests without this module, or tag the known conflicts. Tests in this module enable cash-in explicitly where needed |
| Required `reason_id` (settled: reject) breaks callers of `try_cash_in_out` that do not send it: cash moves queued offline before the upgrade, other modules or scripts, and core test `test_point_of_sale_flow.py:3212` when core tests run with this module installed | Med (accepted cost) | Documented in the README as a known conflict. Upgrade procedure: sync all POS devices before upgrading and reload clients after. In CI, run core tests without this module or tag the known conflict. Never default to Vault |
| Cash-in queued offline before the toggle was turned off (or before upgrade) is rejected at replay | Low | Intended: the server check is the source of truth. Same rejection UX as other replay rejections (open design question 1) |
| Hiding the "Cash In" button through a template extension breaks if Enterprise or another module rewrites the popup template | Low | Server rejection still holds. Use a minimal xpath on the button. Hoot test asserts the button is absent; smoke-test on Enterprise |
| Additive kwarg on the "DO NOT INHERIT" `set_opening_control` conflicts with another module that overrides it | Low | Strict-superset signature and passthrough only. The logic stays in `_set_opening_control_data`. ADR plus an explicit code comment. Test with `pos_hr` installed |
| Offline-queued RPC replays against a changed config (toggle or allowed bills changed after queuing) | Med | Payload is self-contained (bill ids, quantities, amount, reason id). Validation uses the config at replay time. The design decides how the user is informed |
| Offline-queued cash move whose reason was archived or moved to another company before replay | Low | Validation at replay time rejects it, with the same UX as other replay rejections. Archiving reasons is rare; document it for operators |
| Closing guard wrongly blocks the POS path, because `close_session_from_ui` calls `action_pos_session_closing_control` (`pos_session.py:626`) | Med | Guard keys on "closing count exists", not on the caller (Approach 9). TransactionCase and tour cover a non-manager closing from the POS with a breakdown |
| Closing guard is bypassed through another public close method (`action_pos_session_validate`, `action_pos_session_close`) or the imbalance wizard | Med | Guard placed at a common choke point; tests call each public method directly as a non-manager |
| Non-manager staff can no longer close rescue sessions or forgotten sessions from the back office when the closing toggle is on | Low (intended) | Documented. A manager closes them and the session is flagged |
| Expected-cash formula drifts from core `get_closing_control_data` after an Odoo update | Low | Parity TransactionCase comparing both amounts |
| Alert state is stale on multi-device sessions or offline: another device's sales or cash-outs are only reflected at this device's next refresh; offline keeps the last known state | Med (accepted) | Server is the source of truth; refresh on load, sync, and cash move. Non-blocking by design, so staleness has no functional impact. Documented. The extra query per sync is a small aggregate (or piggy-backed on the sync response) |
| Navbar patch breaks under Enterprise or other POS navbar overrides | Low | Minimal xpath; Hoot test; Enterprise smoke test. The alert is informational, so a failure does not affect cash integrity |
| Extending `CashMovePopup` strict `static props` conflicts with another module that also extends them | Low | Only add optional props; test with `pos_hr` installed |
| Operators try to create an inbound vault reason to model a return from the vault | Low | Model constraint rejects `is_vault=True` with a non-`out` direction, with a clear message. Documented in the README |
| Default Many2one to seeded data is not applied to existing `pos.config` rows at install (the data record does not exist yet when the column is created) | Med | Post-init hook sets `default_cash_out_reason_id` on existing configs. The field default uses `env.ref(..., raise_if_not_found=False)`. Covered by an install test |
| Operators delete, archive, or reassign the seeded Vault reason and break the default | Low | `noupdate` data; the `pos.config` Many2one uses `ondelete='restrict'`; the popup handles a missing or archived default by showing no preselection |
| Reason name translation in `payment_ref` depends on the language active at replay time | Low | Compose `payment_ref` on the server with the session user's language. The design pins this down |
| A float-keyed `MoneyDetailsPopup` state leaks into the persisted payload | Med | New id-keyed popup. The payload contract is `[{bill_id, quantity}]` only |
| Exact path that serializes `pos.config` fields to the POS frontend is unknown | Med | Design-time spike, covered by a Hoot/tour assertion |
| Rounding mismatch between `pos.bill.value` (16,4) and session currency | Med | Compare with the currency rounding in the domain layer. Use explicit test cases |
| Employee attribution needs `hr.employee` without depending on `pos_hr` | Med | Design picks a conditional-field or soft-reference strategy. Tests run with and without `pos_hr` |
| Enterprise POS asset overrides break the UI patches | Low | Patch only public component methods. Smoke-test on Enterprise before deploy |
| Total size (about 3,300–3,800 authored lines) exceeds the 400-line review budget | High | Chained PR slicing forecast below. Strategy decision needed before apply (ask-on-risk) |

## Rough Slicing Forecast (ask-on-risk, ~400 lines per PR)

Cash-in control, reasons, and the vault alert do not depend on denominations, so they ship first. The alert follows reasons (its cash-out preselects a vault reason); the closing override follows enforcement (it needs the count model).

| Slice | Content | Est. lines |
|-------|---------|-----------|
| 1 | docker-compose runner + addon skeleton + test command docs | ~150 |
| 2 | Domain layer (breakdown, reason incl. missing reason and vault `out`-only, move-type rule, closing rule, expected cash and threshold rules) + unit tests | ~380 |
| 3 | Cash-in control: `pos.config` toggle + settings view + frontend delivery + `try_cash_in_out` rejection + `CashMovePopup` button hiding + TransactionCase + Hoot tests + README note | ~200 |
| 4 | Reason catalog backend: model + vault constraint, single seed, post-init hook, security, config views/menu, `pos.config` default, statement line field, POS loading, `try_cash_in_out` reason validation (missing → reject) and `payment_ref` + TransactionCase + README known conflicts | ~400 |
| 5 | Reason selector, note, and optional initial type/reason props in `CashMovePopup` + `pos.cashMove()` patch + Hoot tests | ~280 |
| 6 | Vault alert backend: threshold field + settings view + frontend delivery + expected-cash helper + `get_vault_withdrawal_state` + TransactionCase (incl. parity with `get_closing_control_data`) | ~250 |
| 7 | Vault alert frontend: refresh hooks (load, sync, cash move), notification, navbar indicator, one-click vault cash-out + Hoot tests + README | ~300 |
| 8 | `pos.config` denomination toggles + settings view + count header/lines models (with reason) + security + reporting views/menu + TransactionCase | ~400 |
| 9 | `pos.session` denomination enforcement (opening, cash IN/OUT, POS UI closing) + TransactionCase | ~400 |
| 10 | Closing override: guard at the choke point, session flag fields, chatter message, session views and filter + TransactionCase for every close path + README | ~220 |
| 11 | Breakdown popup + opening/cash move/closing patches + Hoot tests | ~400–500 (may split 11a popup / 11b patches) |
| 12 | HttpCase tours (opening, cash-out with reason, cash-in disabled, reason rejection, denomination rejection, POS closing with breakdown, vault alert and one-click cash-out) | ~380 |

Decision needed before apply: Yes (chain strategy). Chained PRs recommended: Yes. 400-line budget risk: High.

## Rollback Plan

- **Cash-in control**: to restore stock cash-in on a POS, turn the cash-in toggle on in its settings. No data changes are needed. Reverting slice 3 or uninstalling the module removes the toggle and restores stock cash-in for all POS configs.
- **Denominations**: the feature is opt-in and every denomination toggle defaults to off. The first-line rollback is to turn toggles off per POS, which restores stock behavior for opening, cash moves, and closing immediately with no data loss.
- **Closing override**: turning the closing toggle off disables the guard immediately; any user can close from the back office again as in stock. Existing flags stay on past sessions as history. Reverting slice 10 removes the guard and the flag fields.
- **Vault alert**: set the threshold to 0 per POS; the indicator and notifications stop at the next refresh. Reverting slices 6–7 removes the field, the method, and the navbar patch. No stored data depends on it.
- **Reasons**: the catalog has no toggle, so turning it off at runtime is not possible. The rollback is to revert slices 4–5 or to uninstall the module. As a mitigation without code changes, operators keep the Vault default, which reduces the cashier's extra step to confirming a preselected value. External callers blocked by the required reason are only unblocked by reverting slice 4 or uninstalling.
- If the module itself misbehaves, uninstall `pos_cash_denomination_control`:
  - the toggle fields, the threshold, the reason catalog, `reason_id` on statement lines, the session flag fields, and the count models and their data are dropped;
  - core `pos.session`, `account.bank.statement.line`, and notes and chatter are unaffected. The text notes were always written the stock way, `payment_ref` still contains the reason name and note as text, and the chatter messages for manager closings remain, so the history stays readable;
  - the additive kwargs and `extras` keys disappear with the override, and the JS falls back to the stock popups, navbar, "Cash In" button, and free-text reason.

  Before uninstalling in production, export the count lines, the statement line reasons, and the session flags if reporting history or future Vault Status data must be kept.
- Each chained PR slice can be reverted on its own. Slices 1–2 add no runtime behavior. Slices 6–7 add no runtime behavior while every threshold is 0. Slices 8, 10, and 11 add no runtime behavior while the denomination toggles are off.

## Dependencies

- Odoo 19.0 Community (`point_of_sale`). The reference source is under `odoo-src/`, read-only.
- Docker and docker-compose to provision the test runner (first task). Strict TDD stays disabled in `openspec/config.yaml` until the runner exists.
- `pos_hr` is optional. Coexistence is required, but it is not a dependency.
- Open questions. There are no open product questions. The remaining items are design decisions and do not block the proposal:
  1. Offline replay rejection UX: how the cashier is told that a queued operation was rejected after reconnecting (design).
  2. Employee storage strategy without a hard `hr` dependency (design).
  3. Exact choke-point method for the closing guard and proof that every close path behaves as specified (design).
  4. Alert refresh transport: a separate RPC or a piggy-back on the order sync response (design).
- Defaults chosen in this proposal that the orchestrator may override without reopening scope (not blocking):
  - the vault alert notification is shown once per transition into "required" (and on load), not after every sync;
  - the navbar indicator is shown to every POS user; clicking it without the stock cash-move permission shows a notification instead of the popup;
  - the one-click cash-out preselects the POS default cash-out reason if it is a vault reason, otherwise the first active vault reason.

## Success Criteria

- [ ] With all four denomination toggles off and the threshold at 0, opening, selling, and closing behave exactly like stock Odoo 19. Cash moves behave like stock except for the required reason and cash IN being off by default. Verified by tours and TransactionCase regressions.
- [ ] After install, every existing and new POS config has cash-in disabled. With cash-in off, the cash move popup has no "Cash In" button and opens in "out" mode, and the server rejects `try_cash_in_out` with `_type == 'in'` with a `UserError`, even when called directly.
- [ ] With cash-in on and the stock cash-move permission granted, cash IN works as in stock Odoo (plus the reason rules). Without the permission, cash IN and OUT stay rejected as in stock.
- [ ] The cash-IN denomination toggle is visible in settings only when cash-in is enabled.
- [ ] With a denomination toggle on, the matching amount input is read-only, and the amount can only be set through the breakdown popup.
- [ ] With a denomination toggle on, the server rejects: a missing breakdown; a sum that does not match within currency rounding; bills not allowed for the config; negative or non-integer quantities. This also holds for offline-queued replays.
- [ ] Each accepted counted operation creates one header and N lines with the correct session, company, move type, cashier (and employee with `pos_hr`), reason (cash moves), bill snapshot, quantity, and subtotal. Cash moves are linked to their statement line.
- [ ] Closing enforcement applies only to the cash payment method count. Non-cash methods are unchanged.
- [ ] With the closing toggle on: a non-manager closing from the POS UI with a breakdown succeeds; a non-manager closing without a recorded breakdown through the back-office button, the wizard, or any public close method gets a `UserError` and no accounting entry is created; a manager closing without a breakdown succeeds and the session shows the flag, the user, the date/time, and a chatter message; sessions can be filtered by the flag.
- [ ] Opening and closing notes and chatter still contain the human-readable breakdown text.
- [ ] After install, exactly one seeded reason, "Vault" (`out`, `is_vault=True`), exists; there is no "From vault" reason. Every existing and new POS config has "Vault" as its default cash-out reason.
- [ ] Creating or editing a reason with `is_vault=True` and a direction other than `out` raises a validation error.
- [ ] The cash move popup shows only direction-compatible, active, company-allowed reasons. Cash OUT is preselected with the POS default. Confirm is not possible without a reason. This works with and without denomination toggles.
- [ ] The server rejects a cash move without `extras['reason_id']`, and a reason that is inactive, belongs to another company, or has an incompatible direction, with a `UserError` and no statement line created.
- [ ] Every accepted POS cash move stores `reason_id` on its statement line, no cash IN ever stores a vault reason, and `payment_ref` contains the reason name and the note when given.
- [ ] The vault threshold field is visible only when the POS has cash control. With threshold 0 nothing is shown.
- [ ] With a threshold set, when expected cash reaches or exceeds it (after load, an order sync, or a cash move), the POS shows the "Vault withdrawal required" notification and a navbar indicator; a cash-out that brings expected cash below the threshold removes the indicator at the next refresh.
- [ ] Clicking the indicator opens the cash move popup in "out" mode with a vault reason preselected. Sales, payments, and closing are never blocked by the alert.
- [ ] The expected cash returned by the alert method equals `get_closing_control_data()['default_cash_details']['amount']` for the same session.
- [ ] Back-office users can pivot and graph count lines by POS, date, move type, denomination, and reason under POS Reporting, can filter statement lines by reason, and multi-company record rules are respected.
- [ ] The README documents: cash-in disabled on install and how to re-enable it; the required reason and its known conflicts (pre-upgrade offline moves, external callers, core test); the manager-only back-office closing rule; and the vault alert.
- [ ] The module installs and all tests pass with and without `pos_hr` installed, in the docker-compose runner.
- [ ] Domain layer tests (breakdown, reason, move-type, closing, expected-cash, and threshold rules) run without the Odoo ORM.
