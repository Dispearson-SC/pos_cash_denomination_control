## Exploration: pos-cash-denomination-control

### Current State (Odoo 19.0 point_of_sale + pos_hr)

**Denominations (`pos.bill`)** — `odoo-src/addons/point_of_sale/models/pos_bill.py`. Fields: `name`, `value` (Float, digits (16,4)), `pos_config_ids` (m2m). Loaded to POS via `_load_pos_data_domain`: bills that are either in `config.default_bill_ids` or global (`pos_config_ids` empty). `pos.config.default_bill_ids` (m2m, `pos_config.py:152`) is the per-POS allow-list. No new catalog needed — confirmed reusable as-is.

**MoneyDetailsPopup** (`static/src/app/components/popups/money_details_popup/money_details_popup.js`) is the only existing denomination-breakdown UI. `state.moneyDetails` is `{ [bill.value]: qty }` — **keyed by `bill.value` (a float), not `bill.id`**. `confirm()` returns `{ total, moneyDetailsNotes, moneyDetails, action }` via `getPayload`. `moneyDetailsNotes` is a human-readable text block; `moneyDetails` (the structured dict) is **never sent to the server** by any current caller — only `total` (as the free-amount field) and `moneyDetailsNotes` (appended to opening/closing notes) survive the RPC boundary.

**Opening** (`OpeningControlPopup`, `static/.../opening_control_popup/opening_control_popup.js`): `openDetailsPopup()` opens `MoneyDetailsPopup`, sets `this.state.openingCash` (free input) from `total`, and `this.moneyDetails` (private component field, never sent). `confirm()` calls `pos.data.call('pos.session', 'set_opening_control', [session.id, parseFloat(state.openingCash), state.notes], {}, true)` — **queue=true** (5th arg), i.e. this call goes through the offline-tolerant queue, not guaranteed-online.

Server: `pos_session.py:1792` `set_opening_control(cashbox_value: int, notes: str)` — docstring: **"DO NOT INHERIT THIS METHOD. Inherit `_set_opening_control_data` instead."** (`pos_session.py:1797`). `_set_opening_control_data(cashbox_value, notes)` (`:1773`) sets state, posts a message, sets `cash_register_balance_start = cashbox_value`. `pos_hr` inherits `_set_opening_control_data` cleanly (adds `message_post` with `author_id`) — confirms this is the sanctioned extension point and pos_hr already uses it, so our module can coexist.

**Cash in/out** (`CashMovePopup`, `static/.../cash_move_popup/cash_move_popup.js`): free `state.amount` input, no denomination UI at all today. `confirm()` builds `extras = { formattedAmount, translatedType }` then calls `pos.data.call('pos.session', 'try_cash_in_out', this._prepareTryCashInOutPayload(type, amount, reason, partnerId, extras), {}, true)` — also **queue=true**. `_prepareTryCashInOutPayload` returns `[[session.id], type, amount, reason, partnerId, extras]`.

`pos_hr` patches exactly `_prepareTryCashInOutPayload` (`pos_hr/static/.../cash_move_popup.js`) to inject `employee_id` into the `extras` dict (the last positional arg) — **this is the sanctioned, already-proven pattern for passing extra structured data through `try_cash_in_out` without touching the public signature**.

Server: `pos_session.py:1879` `try_cash_in_out(_type, amount, reason, partner_id, extras)`. Checks `_has_cash_move_permission()`, computes `sign`, then for each session in `self.filtered('cash_journal_id')` calls `_prepare_account_bank_statement_line_vals(session, sign, amount, reason, partner_id, extras)` and bulk-creates `account.bank.statement.line` records (sudo). `_prepare_account_bank_statement_line_vals` (`:1869`) is the override point pos_hr already uses (`pos_hr/models/pos_session.py:89`) to read `extras.get('employee_id')` and set `vals['employee_id']`. Same pattern applies for us: read `extras.get('denomination_lines')` there (or override `try_cash_in_out` itself for validation, since vals-prep happens per-session in a loop and enforcement must reject the whole call, not silently drop lines).

**Closing** (`ClosePosPopup`, `static/.../closing_popup/closing_popup.js`): `openDetailsPopup()` — same `MoneyDetailsPopup` pattern as opening, sets `state.payments[defaultCashId].counted` from `total`; `moneyDetails` again stays client-only. `closeSession()` calls, in order: `pos.pushOrdersWithClosingPopup()`, then (if `cash_control`) `post_closing_cash_details(session.id, { counted_cash })`, then `update_closing_control_state_session(session.id, notes)`, then `close_session_from_ui(session.id, bankPaymentMethodDiffPairs)`.

Server: `post_closing_cash_details(counted_cash)` (`pos_session.py:654`) just sets `cash_register_balance_end_real = counted_cash` after `_cannot_close_session()` checks — no notes/details param at all today. `update_closing_control_state_session(notes)` (`:646`) sets state + `closing_notes` and posts a message. Both are candidates for enforcement/extension but are separate calls (not one atomic RPC like opening/cash-out), and `close_session_from_ui` (`:597`) is the final commit step, called after these two — meaning enforcement for closing would need to hold state across up to 3 sequential RPCs or be re-validated at `close_session_from_ui` time using session fields set by the prior 2 calls.

**pos.config**: `cash_control` is a **computed** Boolean (`_compute_cash_control`, not stored, derived from `payment_method_ids.filtered('is_cash_count')`) — our new toggles must be plain stored Booleans, and should probably be visible only when `cash_control` is true in the view.

**Data loading to frontend**: `pos.config._load_pos_data_read` (`pos_config.py:280`) exists and is the override point to inject computed/derived fields into the payload; models inheriting `pos.load.mixin` expose fields via `_load_pos_data_fields(config)` (`pos_load_mixin.py:49-56`). Existing plain booleans (`cash_control`, `amount_authorized_diff`, `default_bill_ids`) are read in JS as `this.pos.config.*`, strongly suggesting that declaring the field is sufficient. **Residual unknown**: the exact path that serializes `pos.config` to the client must be pinned down during design (spike).

**Offline behavior**: Both `set_opening_control` and `try_cash_in_out` are called with `queue=true` through `PosData.call` (`data_service.js:930`), so they can be queued in IndexedDB and replayed later (`data_service.js:49-83`). **Consequence**: server-side breakdown validation must be fully self-contained in the single RPC payload.

**Multi-company / access**: `pos.session` and `account.bank.statement.line` already carry `company_id`. `pos.bill` has no `company_id` — the new line model must derive/store `company_id` from the session for record rules.

**pos_hr employee attribution pattern** (`pos_hr/models/pos_session.py`, `pos_hr/models/account_bank_statement.py`): `account.bank.statement.line.employee_id` is added by pos_hr and populated via `extras['employee_id']` from a patched `_prepareTryCashInOutPayload` using `this.pos.getCashier().id`. For opening, pos_hr resolves `_get_message_author()` from `session.employee_id`. **For our line model**: attribution should read `session.employee_id` when pos_hr is installed (fallback `session.user_id`) for opening; for cash-out, accept `extras['employee_id']` if present to stay consistent with `account.bank.statement.line.employee_id`.

**Test infrastructure (Odoo 19)**:
- Domain/pure-Python: plain `unittest` tests, no base class.
- ORM: `odoo.addons.point_of_sale.tests.common.CommonPosTest`; session-oriented tests use `TestPointOfSaleHttpCommon` (`point_of_sale/tests/test_frontend.py:34`) with `with_new_session(config, user)` and `start_pos_tour(tour_name, login=...)`.
- HttpCase tours: `static/tests/pos/tours/*.js`, registered in `registry.category("web_tour.tours")`, helpers in `static/tests/pos/tours/utils/*_util.js` and `static/tests/generic_helpers/dialog_util.js`. `pos_hr` mirrors this under its own `static/tests/tours/`.
- Hoot JS unit tests: `static/tests/unit/**/*.test.js`, mock data factories at `static/tests/unit/data/{model}.data.js`; component test pattern shown by `pos_hr/static/tests/unit/components/popups/cash_move_popup.test.js`.

### Affected Areas (reference only; all under odoo-src)

- `models/pos_config.py:120-152` — new stored Booleans on our inherited `pos.config`.
- `models/pos_session.py:1773-1892` — `_set_opening_control_data`, `_prepare_account_bank_statement_line_vals` / `try_cash_in_out`, `post_closing_cash_details` / `update_closing_control_state_session` / `close_session_from_ui`.
- `models/pos_bill.py` — reused unmodified; line model FKs to `pos.bill` and snapshots `bill_value`.
- `static/.../opening_control_popup/opening_control_popup.js` — lock free input, force breakdown, send structured breakdown.
- `static/.../cash_move_popup/cash_move_popup.js` — same for cash-out; inject breakdown into `extras` via `_prepareTryCashInOutPayload`.
- `static/.../money_details_popup/money_details_popup.js` — float-keyed state; do not reuse as-is for persistence.
- `pos_hr/models/account_bank_statement.py`, `pos_hr/models/pos_session.py` — patterns for extras threading and employee attribution.
- `tests/test_frontend.py::TestPointOfSaleHttpCommon`, `tests/common.py::CommonPosTest` — base classes to reuse.

### Approaches

1. **`extras`-dict transport for cash-out + extended positional signature for opening.** Cons: `set_opening_control` is called with a fixed positional arg list. Effort: Medium.
2. **(Recommended) `extras` for cash moves + additive `denomination_lines=None` kwarg on `set_opening_control`, passed through the unused `kwargs` slot of `pos.data.call(model, method, args, kwargs, queue)`.** Business logic stays in the inheritable `_set_opening_control_data`; the public method becomes a passthrough. Additive, non-breaking, single atomic RPC. Cons: touches the signature of the method documented as "DO NOT INHERIT" — needs explicit sign-off. Effort: Medium.
3. **Dedicated breakdown RPC before the existing call.** Cons: two-phase race with queued/offline replay; orchestration state. Effort: High. Rejected.

### Closing / Cash-In recommendation

- **Cash IN**: same popup, same transport, same validation — expose a third independent toggle (default off). Cheap with approach 2.
- **Closing**: `MoneyDetailsPopup` is already wired into `ClosePosPopup.openDetailsPopup()`. Apply the approach-2 pattern to `post_closing_cash_details(counted_cash, denomination_lines=None)` (the method that records the counted total); the follow-up calls need no change. Recommend a fourth toggle.

### Risks

- **Float-as-key** in `MoneyDetailsPopup` state: the persisted payload must be `[{bill_id, quantity}]` keyed by `pos.bill.id`. Recommend a new dedicated id-keyed popup component.
- **`set_opening_control` signature change**: additive kwarg; needs explicit sign-off in proposal/design.
- **Offline replay**: single self-contained payload per action; approach 3 unsafe.
- **`pos.config` field delivery** path to the frontend not fully pinned down — design spike.
- **Rounding**: compare Σ(qty × bill_value) to the amount with the session currency rounding (`float_compare` / `currency.compare_amounts`), never `==`.
- **`pos.bill` has no `company_id`**: derive company from session; allowed-bill validation must reuse `pos.bill._load_pos_data_domain` logic.
- **Sudo creation** of statement lines in `try_cash_in_out`: the count-line model must be created in the same sudo context and carry its own access rules.

### Rough Size Forecast

About 6 work areas, likely over the 400-line PR budget as one slice:
1. Pure-Python domain module + unit tests.
2. Count-line model(s) + access rules + views/reporting + TransactionCase tests.
3. `pos.config` toggles + settings view + data-loading spike.
4. `pos.session` enforcement (opening, cash moves, optional closing) + tests.
5. JS id-keyed breakdown popup + patches + Hoot tests + `.data.js` mocks.
6. HttpCase tours (opening, cash-out, rejection).

### Ready for Proposal

Yes. Two decisions to resolve explicitly in proposal/design: (a) sign-off on the additive `set_opening_control` kwarg; (b) whether cash-IN and closing get their own toggles now (recommended: yes).
