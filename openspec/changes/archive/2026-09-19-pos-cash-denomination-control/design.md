# Design: POS Cash Denomination Control

Change: `pos-cash-denomination-control` | Proposal: rev #3 (approved) | Target: Odoo 19.0 Community and Enterprise
Reference source: `odoo-src/addons/point_of_sale` and `odoo-src/addons/pos_hr` (read-only). All `file:line` references below point there unless stated otherwise.

## Technical Approach

One addon, `pos_cash_denomination_control`, depends only on `point_of_sale`. It uses a hexagonal-lite split:

- **Domain (`domain/`)**: pure Python with no `odoo` import. It holds all business rules (breakdown validation, reason rules, cash-in rule, closing decision, expected cash, and the threshold rule). It raises typed domain errors or returns plain values.
- **Adapters (`models/`)**: thin Odoo overrides. They read records, build plain value objects, call the domain, map domain errors to translated `UserError`/`ValidationError`, and persist records. Every override calls `super()`.
- **Frontend (`static/src/`)**: Owl patches and one new popup. They only collect input and transport it. The server is the only authority.

Transport follows the proposal: `extras` for cash moves, and additive kwargs on `set_opening_control` and `post_closing_cash_details`. Stock frontend code builds the opening and closing kwargs as inline literals, so a narrow, one-shot **kwargs staging** patch on `PosData.call` delivers them (ADR-5). Internally, the server moves data between methods through the **context**, not through extra positional or keyword arguments, so it stays safe with `pos_hr` and any MRO order (ADR-1).

## Verified Extension Points (Odoo 19.0)

| Concern | Location | Finding used by the design |
|---|---|---|
| Opening (public) | `models/pos_session.py:1792` `set_opening_control(cashbox_value, notes)` | Has the "DO NOT INHERIT" docstring (`:1797`). Returns early if the state is not `opening_control` (`:1799`). |
| Opening (internal) | `models/pos_session.py:1773` `_set_opening_control_data(cashbox_value, notes)` | `pos_hr` overrides it with a **fixed** signature (`pos_hr/models/pos_session.py:23`). |
| Cash move | `models/pos_session.py:1879` `try_cash_in_out(_type, amount, reason, partner_id, extras)` | Permission check at `:1880`. Loops over `self.filtered('cash_journal_id')` and bulk-creates statement lines in sudo (`:1892`). Returns nothing. |
| Statement line vals | `models/pos_session.py:1869` | `payment_ref = '-'.join([session.name, extras['translatedType'], reason])` (`:1875`). `pos_hr` extends it (`pos_hr/models/pos_session.py:89`). |
| Closing count | `models/pos_session.py:654` `post_closing_cash_details(counted_cash)` | Sets `cash_register_balance_end_real` (`:676`). Called **online only** (no `queue`, `closing_popup.js:207-216`). |
| Close paths | `models/pos_session.py:388/413/417/424` | `closing_control` goes to `validate`, then `close`, then `_validate_session`. `close_session_from_ui` (`:626`) and the wizard (`wizard/pos_close_session_wizard.py:18`) call `action_pos_session_closing_control`. `_validate_session` is the only method that writes `state='closed'` (`:482`). It does `cr.rollback()` and returns a wizard on imbalance (`:457-458`). |
| Rescue close | `models/pos_session.py:401-408` | Overwrites `cash_register_balance_end_real` before validation. |
| Expected cash | `models/pos_session.py:778-808` | `start + default cash (first type=='cash') payments of closed non pay_later orders + sum(sudo statement_line_ids.amount)`. |
| POS data models | `models/pos_session.py:139` `_load_pos_data_models` | Extended by appending the model name (`pos_hr` pattern, `:17-21`). |
| Config to frontend | `models/pos_load_mixin.py:49-56,70-72`; `models/pos_config.py:276-304` | `pos.config` does **not** override `_load_pos_data_fields`, so it returns `[]`, and `read([])` loads **every readable field**. Relations come from `_load_pos_data_relations` with `fields=[]` (`pos_session.py:105-136`, all non-manual fields). **Spike resolved**: declaring a stored field with no `groups` is enough. |
| Allowed bills | `models/pos_bill.py:25-26` | Domain `['|', ('id','in', config.default_bill_ids.ids), ('pos_config_ids','=',False)]`. |
| Cash permission | `models/res_users.py:24-26`; `pos_config.py:290`; `static/src/app/services/pos_store.js:1375-1377` | This gate is unchanged. |
| Cash move UI | `static/src/app/components/popups/cash_move_popup/cash_move_popup.js:21,31,43-107` | Strict props array. The type starts as `"out"`. `reason` is required by `isValidCashMove` (`:105-107`). The receipt receives `reason` (`:78-84`). |
| `pos.cashMove()` | `static/src/app/services/pos_store.js:475-478` | `makeAwaitable(this.dialog, CashMovePopup)` with no props. |
| Opening UI | `static/src/app/components/popups/opening_control_popup/opening_control_popup.js:39-47` | Inline call `[id, amount, notes], {}` with `queue=true`. |
| Closing UI | `static/src/app/components/popups/closing_popup/closing_popup.js:199-262`; `.xml:61-70` | Inline kwargs `{counted_cash}`. Has the `fa-money` and `fa-clone` buttons. |
| Order sync hook | `static/src/app/services/pos_store.js:1555-1672` | `syncAllOrders` returns the synced orders. `afterProcessServerData` (`:719`) runs at load. |
| Offline queue | `static/src/app/services/data_service.js:551-721,823-841,930` | Queued calls are stored with `args:[...arguments]`, so kwargs are kept. On replay, a server rejection is rethrown. `syncData` does **not** shift the item, and `checkConnectivity` (`:84-94`) swallows the error, so a rejected item **blocks the queue**. `unsyncData` is only in memory (no persistence found). **Confirmed empirically in Phase 13** (`static/tests/tours/offline_queue_tour.js`, `test_offline_queue_is_memory_only`): a cash-out confirmed while offline is queued (`network.unsyncData.length === 1`), then lost across a page reload performed while still offline (`network.unsyncData.length === 0` after reload), and no statement line is ever created for it — this was a static-analysis claim only until this tour ran it end-to-end. |
| Navbar | `static/src/app/components/navbar/navbar.xml:31-32` | `div.status-buttons` is a flex container. |
| Hoot mocks | `static/tests/unit/data/generate_model_definitions.js:54,107`; `pos_hr/static/tests/unit/data/hr_employee.data.js:43` | Extend with `patch(hootPosModels, [...])` and patch the mock `PosSession`/`PosConfig`. |

## Module File Tree (OCA style)

Repository root layout (OCA style: the addon lives at the repository root, which is mounted read-only into the container; Odoo only loads folders containing `__manifest__.py`):

```
caja-boveda/
├── docker-compose.yml
├── docker/Dockerfile                 # FROM odoo:19.0 + Google Chrome (tours, Hoot)
├── docker/odoo.conf                  # addons_path, db host, without_demo policy
├── scripts/test.sh                   # drop/create test DB, run the test command
├── pos_cash_denomination_control/
│   ├── __init__.py  __manifest__.py  hooks.py
│   ├── domain/  __init__.py errors.py money.py breakdown.py reasons.py
│   │            cash_moves.py closing.py cash_position.py text.py
│   ├── models/  __init__.py domain_errors.py pos_cash_move_reason.py pos_config.py
│   │            res_config_settings.py pos_session.py account_bank_statement_line.py
│   │            pos_cash_denomination_count.py pos_cash_denomination_count_line.py
│   ├── data/pos_cash_move_reason_data.xml
│   ├── security/ir.model.access.csv  security/security.xml
│   ├── views/   pos_cash_move_reason_views.xml res_config_settings_views.xml
│   │            pos_cash_denomination_count_views.xml pos_session_views.xml
│   │            account_bank_statement_line_views.xml menus.xml
│   ├── static/src/app/
│   │   ├── utils/breakdown.js                         # pure JS helpers (total, payload, note text)
│   │   ├── services/data_service_patch.js              # kwargs staging + replay rejection
│   │   ├── services/pos_store_patch.js                 # cashMove(opts), vault alert, rejection UX
│   │   ├── components/popups/denomination_breakdown_popup/  .js .xml
│   │   ├── components/popups/cash_move_popup/cash_move_popup_patch.{js,xml}
│   │   ├── components/popups/opening_control_popup/opening_control_popup_patch.{js,xml}
│   │   ├── components/popups/closing_popup/closing_popup_patch.{js,xml}
│   │   └── components/navbar/vault_alert_indicator/ .js .xml .scss  + navbar_patch.{js,xml}
│   ├── static/tests/unit/  data/*.data.js  *.test.js
│   ├── static/tests/tours/ *_tour.js  utils/*_util.js
│   ├── tests/   __init__.py common.py test_domain_*.py test_domain_purity.py
│   │            test_install.py test_cash_in_control.py test_reasons.py test_counts.py
│   │            test_enforcement_*.py test_closing_override.py test_vault_alert.py
│   │            test_frontend.py test_hoot.py
│   ├── readme/  DESCRIPTION.md CONFIGURE.md USAGE.md ROADMAP.md CONTRIBUTORS.md
│   └── i18n/pos_cash_denomination_control.pot (+ es.po)
└── openspec/ ...
```

Reason for `addons/`: the repository also holds `odoo-src/` and `openspec/`, so a dedicated directory gives a clean `addons_path` mount.

### Manifest

```python
{
    "name": "POS Cash Denomination Control",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "license": "LGPL-3",
    "depends": ["point_of_sale"],
    "data": [
        "security/security.xml", "security/ir.model.access.csv",
        "data/pos_cash_move_reason_data.xml",
        "views/pos_cash_move_reason_views.xml", "views/res_config_settings_views.xml",
        "views/pos_cash_denomination_count_views.xml", "views/pos_session_views.xml",
        "views/account_bank_statement_line_views.xml", "views/menus.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": ["pos_cash_denomination_control/static/src/**/*"],
        "web.assets_tests": ["pos_cash_denomination_control/static/tests/tours/**/*"],
        "web.assets_unit_tests": ["pos_cash_denomination_control/static/tests/unit/**/*"],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
}
```

This follows the `pos_hr` bundle pattern (`pos_hr/__manifest__.py:27-37`). `point_of_sale._assets_pos` is included by `assets_prod` and by the unit-test setup (`point_of_sale/__manifest__.py:100-114,217-220`).

### Hooks

`post_init_hook(env)`: look up the vault reason with `env.ref("pos_cash_denomination_control.pos_cash_move_reason_vault")`, then run `UPDATE pos_config SET default_cash_out_reason_id = %s WHERE default_cash_out_reason_id IS NULL` and invalidate the `pos.config` model cache. The hook uses SQL on purpose: `pos.config.write` (`pos_config.py:632-672`) runs `_check_modules_to_install` and `_check_groups_implied`, which can trigger side effects on existing configs during install. `cash_in_enabled` needs no hook, because the Boolean column is created with default `False` for all existing rows. No uninstall hook is needed.

## Domain Layer (pure Python)

All modules use only the standard library (`dataclasses`, `decimal`, `enum`, `typing`). Money uses `Decimal(str(x))` internally.

```python
# errors.py
class DomainError(Exception):
    code: str                      # stable machine code
    def __init__(self, code: str, **params): ...
class BreakdownError(DomainError): ...   # MISSING, MALFORMED, NON_INTEGER_QUANTITY, NEGATIVE_QUANTITY,
                                         # BILL_NOT_ALLOWED, DUPLICATE_BILL, TOTAL_MISMATCH
class ReasonError(DomainError): ...      # MISSING, NOT_FOUND, INACTIVE, WRONG_COMPANY,
                                         # DIRECTION_MISMATCH, VAULT_NOT_OUT
class MoveTypeError(DomainError): ...    # UNKNOWN_TYPE, CASH_IN_DISABLED

# money.py
def compare_amounts(a: float, b: float, rounding: float) -> int   # -1/0/1, rounds (a-b)/rounding HALF_UP
def is_zero(value: float, rounding: float) -> bool                # same semantics as Odoo float_compare

# breakdown.py
@dataclass(frozen=True)
class BreakdownLine: bill_id: int; bill_value: float; quantity: int
@dataclass(frozen=True)
class Breakdown: lines: tuple[BreakdownLine, ...]; total: float
def parse_lines(raw, allowed_bills: Mapping[int, float]) -> tuple[BreakdownLine, ...]
    # raw: list of {"bill_id", "quantity"}; int or integral float accepted, bool and str rejected;
    # duplicates, negatives, and unknown or not-allowed bills rejected; zero-quantity lines dropped
def compute_total(lines) -> float                 # sum(quantity * bill_value), Decimal based
def validate_breakdown(raw, amount, allowed_bills, rounding, required) -> Breakdown | None
    # raw is None and required     -> MISSING
    # raw is None and not required -> None (stock path)
    # otherwise parse, compute the total, and raise TOTAL_MISMATCH unless compare_amounts(total, amount) == 0
    # an empty list is valid only when the amount is zero

# reasons.py
@dataclass(frozen=True)
class ReasonSnapshot: id: int; active: bool; company_id: int | None; direction: str; is_vault: bool
def validate_reason_definition(direction: str, is_vault: bool) -> None      # VAULT_NOT_OUT
def is_direction_compatible(direction: str, move_type: str) -> bool         # out: out/both; in: in/both
def validate_reason(reason: ReasonSnapshot | None, move_type: str, company_id: int) -> None
    # None -> MISSING; inactive -> INACTIVE; company not in (None, company_id) -> WRONG_COMPANY;
    # vault and move_type != "out" -> VAULT_NOT_OUT; incompatible direction -> DIRECTION_MISMATCH

# cash_moves.py
def validate_move_type(move_type: str, cash_in_enabled: bool) -> None      # UNKNOWN_TYPE, CASH_IN_DISABLED
def count_required(move_type: str, toggles: CountToggles, cash_control: bool) -> bool
    # the cash-in toggle is effective only when cash-in is enabled; everything requires cash_control

# closing.py
class ClosingDecision(Enum): ALLOWED = "allowed"; ALLOWED_FLAGGED = "allowed_flagged"; REJECTED = "rejected"
def evaluate_closing(count_required: bool, has_valid_count: bool, is_manager: bool) -> ClosingDecision

# cash_position.py
def compute_expected_cash(opening: float, cash_payment_amounts: Iterable[float],
                          statement_line_amounts: Iterable[float]) -> float
    # opening + sum(payments) + sum(statement lines): same order and float arithmetic as the core
def is_withdrawal_required(expected: float, threshold: float, rounding: float) -> bool
    # threshold > 0 and compare_amounts(expected, threshold, rounding) >= 0
@dataclass(frozen=True)
class VaultState: expected_cash: float; threshold: float; required: bool

# text.py
def compose_payment_text(reason_name: str, note: str | None) -> str       # "Vault" or "Vault: note"
```

Error messages are **not** in the domain. `models/domain_errors.py` maps `code` to an `_()` message with parameters, so all translations stay in the Odoo layer.

**Test discovery**: `tests/test_domain_*.py` subclass `odoo.tests.BaseCase`. It is a `unittest.TestCase` with Odoo tag metadata and no cursor or env, so `--test-tags` picks the tests up. They are tagged `@tagged("at_install", "pcdc", "pcdc_domain")` and imported from `tests/__init__.py`. They use no `env`. `tests/test_domain_purity.py` parses every `domain/*.py` with `ast` and fails if it finds an `odoo` import, which enforces "no ORM" by test. The availability of `BaseCase` in 19.0 is verified in slice 1 against the image source (the sparse clone has no `odoo/tests`).

## Data Model

### `pos.cash.move.reason` (new)

| Field | Type | Notes |
|---|---|---|
| `name` | Char, required, `translate=True` | |
| `direction` | Selection `out`/`in`/`both`, required, default `out` | |
| `is_vault` | Boolean | |
| `sequence` | Integer, default 10 | `_order = "sequence, id"` |
| `active` | Boolean, default True | |
| `company_id` | Many2one `res.company`, `index=True` | Empty means shared |

- Constraints: SQL `models.Constraint("CHECK(NOT is_vault OR direction = 'out')", ...)` (same style as `pos_note.py:16`), plus `@api.constrains('is_vault', 'direction')`, which calls `validate_reason_definition` and gives a clear message.
- `_inherit = ['pos.load.mixin']`. `_load_pos_data_domain` returns `[('company_id', 'in', [False, config.company_id.id])]` (the mixin search already excludes inactive records). `_load_pos_data_fields` returns `['id', 'name', 'direction', 'is_vault', 'sequence', 'company_id']`.
- Loaded by appending it in `pos.session._load_pos_data_models`.
- Seed (`noupdate="1"`): `pos_cash_move_reason_vault` with name "Vault", direction `out`, `is_vault=True`, no company.

### `pos.config` (inherit)

| Field | Type | Default |
|---|---|---|
| `allow_cash_in` | Boolean | False |
| `cash_count_opening_required` | Boolean | False |
| `cash_count_out_required` | Boolean | False |
| `cash_count_in_required` | Boolean | False |
| `cash_count_closing_required` | Boolean | False |
| `default_cash_out_reason_id` | Many2one `pos.cash.move.reason`, `ondelete='restrict'`, `check_company=True`, domain `[('direction','in',('out','both')), ('company_id','in',[False, company_id])]` | `env.ref(..., raise_if_not_found=False)` |
| `vault_withdrawal_threshold` | Monetary (`currency_field='currency_id'`) | 0; SQL CHECK `>= 0` |

- The names are final. They are descriptive and unlikely to collide with core or Enterprise fields.
- `res.config.settings` gets `pos_<name>` related fields with `readonly=False`.
- Settings view: a new `<block id="pcdc_cash_section">` inserted with `xpath //block[@id='pos_payment_section']` `position="after"` (`views/res_config_settings_views.xml:75`). It is `invisible="not pos_cash_control"`, and the cash-IN count setting is `invisible="not pos_cash_in_enabled"`.
- **Cash-IN count toggle when cash-in is turned off (resolved)**: the stored value is kept but has no effect (`count_required` checks `cash_in_enabled`). Re-enabling cash-in restores the operator's earlier choice, and no onchange side effect is needed.

### `account.bank.statement.line` (inherit)

- `cash_move_reason_id`: Many2one to the reason, `ondelete='restrict'`, `index='btree_not_null'`.
- `pos_cash_count_id`: Many2one to `pos.cash.denomination.count`, `ondelete='set null'`, `index='btree_not_null'`.
- The `cash_move_` prefix avoids a generic `reason_id` name on a core accounting model (collision safety).

### `pos.cash.denomination.count` (header, new)

| Field | Type |
|---|---|
| `session_id` | Many2one `pos.session`, required, `ondelete='cascade'`, index |
| `config_id` | related `session_id.config_id`, stored, index |
| `company_id` | related `session_id.company_id`, stored, index |
| `currency_id` | related `session_id.currency_id` |
| `move_type` | Selection `opening`/`in`/`out`/`closing`, required, index |
| `total` | Monetary (snapshot from `Breakdown.total`) |
| `date` | Datetime, required, default now, index |
| `user_id` | Many2one `res.users`, required (set explicitly, never from the sudo uid) |
| `employee_ref` | Integer (soft reference to `hr.employee`) |
| `employee_name` | Char (snapshot) |
| `reason_id` | Many2one reason, `ondelete='restrict'`, index (cash moves only) |
| `note` | Text |
| `statement_line_ids` | One2many `account.bank.statement.line`, inverse `pos_cash_count_id` |
| `line_ids` | One2many lines |

- Constraint: `CHECK(total >= 0)`.
- Immutability: no write, create, or unlink ACL for any group. All writes go through adapter code in `sudo()`.
- The closing count is **replaced** on retry: the adapter unlinks the previous closing header of the same session before it creates the new one, so reports never double-count a closing.

### `pos.cash.denomination.count.line` (new)

| Field | Type |
|---|---|
| `count_id` | Many2one header, required, `ondelete='cascade'`, index |
| `bill_id` | Many2one `pos.bill`, `ondelete='set null'` (stock bill deletion is not blocked) |
| `bill_name`, `bill_value` | Char / Float(16,4) snapshots |
| `quantity` | Integer, `CHECK(quantity >= 0)` |
| `subtotal` | Monetary, stored compute `quantity * bill_value` |
| related stored | `session_id`, `config_id`, `company_id`, `currency_id`, `move_type`, `date`, `reason_id`, `user_id`, `employee_name` |

- Constraint: `UNIQUE(count_id, bill_id)`.

### `pos.session` (inherit)

- `closed_without_denomination_count` (Boolean, readonly, `copy=False`, index)
- `closed_without_denomination_count_user_id` (Many2one `res.users`, readonly)
- `closed_without_denomination_count_date` (Datetime, readonly)
- `cash_count_ids` (One2many headers)

### Employee attribution (open question 2, resolved)

**Choice**: a soft reference, `employee_ref` (Integer) plus `employee_name` (Char snapshot), on the header, related onto the lines.

Sources:
- Cash moves: `extras.get('employee_id')`. `pos_hr` injects this key (`pos_hr/static/src/app/components/popups/cash_move_popup/cash_move_popup.js:5-11`).
- Opening and closing: `session.employee_id`, only when `'employee_id' in session._fields`.

The name is resolved only when `'hr.employee' in self.env` (sudo `browse().exists()`). Referential integrity for cash moves already exists on `account.bank.statement.line.employee_id` (`pos_hr/models/account_bank_statement.py:8`). A bridge module (`pos_cash_denomination_control_hr`, auto-install) can later add a real Many2one without a data migration, by reading `employee_ref`.

### Security

- `ir.model.access.csv`:
  - reason: `base.group_user` read; `point_of_sale.group_pos_manager` full access.
  - header and line: `point_of_sale.group_pos_user` read; `group_pos_manager` read.
- `security.xml`:
  - global rule on header and line: `[('company_id','in',company_ids)]`;
  - global rule on reason: `['|',('company_id','=',False),('company_id','in',company_ids)]`.

### Views and menus

- Reasons: list (with `handle` on sequence), form, search, and action. Menu under `point_of_sale.menu_point_config_product`.
- Counts: header list and form (read-only); line list, pivot, graph, and search (group by POS, date, move type, bill value, reason, employee_name). Menu under `point_of_sale.menu_point_rep`.
- Cash moves: **own** list and search views on `account.bank.statement.line` plus an action with domain `[('pos_session_id','!=',False)]`, grouped by `cash_move_reason_id`. Menu under POS Reporting. The design uses its own views instead of inheriting `account` views, so it does not depend on `account` view xmlids (they are not in the sparse clone, and Enterprise may change them).
- Session: the flag fields go after `//field[@name='rescue']` (`views/pos_session_view.xml:18`). The list gets an optional column. The search view gets the filter `closed_without_denomination_count` and a group-by (`view_pos_session_search`, `:122`).

## Server Flows (sequence diagrams)

### Opening

```
OpeningPopup(patched) --stage kwargs--> PosData.call('set_opening_control', [sid, amt, notes], {denomination_lines}, queue=true)
  -> pos.session.set_opening_control(cashbox_value, notes, denomination_lines=None)   [ADR-1 passthrough]
       self = self.with_context(pcdc_opening_lines=freeze(denomination_lines))
       super().set_opening_control(cashbox_value, notes)
         -> (state != opening_control ? return)           # idempotent replay
         -> _set_opening_control_data(v, notes)            # MRO-safe: no new args
              [ours] required = count_required('opening')
                     bd = validate_breakdown(ctx lines, v, allowed_bills, rounding, required)
                     super()                               # pos_hr / core: state, message, balance
                     if bd: create header(opening)+lines (sudo, user_id=env.user, employee from session)
```

`allowed_bills` comes from `env['pos.bill'].search(env['pos.bill']._load_pos_data_domain({}, config))`. This reuses the same domain the POS loads (and any override of it). `freeze()` turns the list into a tuple of `(bill_id, quantity)` pairs so the context value is immutable.

### Cash IN/OUT

```
CashMovePopup(patched).confirm -> _prepareTryCashInOutPayload: extras += {reason_id, note, denomination_lines?}
  -> try_cash_in_out(_type, amount, reason, partner_id, extras)   [override, before super]
       1 permission: _has_cash_move_permission() else AccessError  (same message as core; super re-checks)
       for session in self.filtered('cash_journal_id'):
       2 validate_move_type(_type, config.allow_cash_in)                  -> UserError
       3 validate_reason(snapshot(extras.get('reason_id')), _type, company) -> UserError
       4 bd = validate_breakdown(extras.get('denomination_lines'), amount, ..., required)
       5 header = create count(in/out) with reason and note (sudo) if bd
       super(with_context(pcdc_count_by_session={sid: header.id}))
         -> _prepare_account_bank_statement_line_vals [override]
              note = extras['note'] if 'note' in extras else reason
              text = compose_payment_text(reason_rec.name, note)       # env language of the RPC
              vals = super(session, sign, amount, text, partner_id, extras)   # pos_hr adds employee_id
              vals |= {cash_move_reason_id, pos_cash_count_id from context}
       6 refresh nothing server-side; the client refreshes the vault state
```

- Every check runs before any row is created, so a `UserError` leaves no side effects.
- If `extras` has no `reason_id`, `_prepare_...` does not add a reason. That path is only reachable by non-`try_cash_in_out` callers, because step 3 has already rejected the move.
- `payment_ref` uses the reason name translated in the **RPC env language**. This is the same language the client used for `translatedType`.

### Closing (POS UI)

```
ClosePosPopup(patched).closeSession: if required -> stage {denomination_lines} for post_closing_cash_details
  super.closeSession(): pushOrders -> post_closing_cash_details(sid, {counted_cash, denomination_lines})
     [override] bd = validate_breakdown(lines, counted_cash, ..., required)  -> UserError before super
                res = super(counted_cash)
                if res.successful and bd: unlink old closing header; create closing header (sudo)
  -> update_closing_control_state_session (unchanged)
  -> close_session_from_ui -> action_pos_session_closing_control -> ... -> _validate_session [guard]
```

### Back-office close guard (open question 3, resolved)

**Placement**: override `_validate_session` (`pos_session.py:424`).
- It is private, so it cannot be called by RPC.
- It is the **only** writer of `state='closed'` (`:482`).
- Every public path reaches it: the POS UI, the back-office button, the wizard, `action_pos_session_validate`, and `action_pos_session_close`.

```
_validate_session(...)  [override, before super and before core's sudo() at :427-428]
   cfg = self.config_id; required = cfg.cash_control and cfg.cash_count_closing_required
   has_valid = latest closing header exists and compare(total, cash_register_balance_end_real) == 0
   decision = evaluate_closing(required, has_valid, self.env.user.has_group('point_of_sale.group_pos_manager'))
   REJECTED -> UserError (no accounting entry is created; the earlier state write rolls back)
   res = super(...)
   if decision == ALLOWED_FLAGGED and self.state == 'closed':   # not flagged when super returned the imbalance wizard
       sudo().write(flag, user_id=env.user, date=now); message_post(chatter)
   return res
```

The count must match `cash_register_balance_end_real`, so the following cases work as specified:
- Rescue sessions (`:408` overwrites the balance) become manager-only and are flagged.
- A back-office edit of the counted cash after a POS count invalidates the count.
- The POS path (count recorded by `post_closing_cash_details` in an earlier, committed RPC) passes for non-managers, including the wizard reached after a POS redirect.

### Vault state

`pos.session.get_vault_withdrawal_state()`:
1. Runs the same `group_pos_user` check as `:779-780`, then `ensure_one()`.
2. `_pcdc_expected_cash_inputs()` collects the same inputs as `:782-787` and `:803`.
3. Calls `compute_expected_cash` and then `is_withdrawal_required`.
4. Returns `{expected_cash, threshold, required}`. `required` is `False` when cash control is off or the threshold is 0.

It does not override `get_closing_control_data`. A parity test guards against drift.

## Frontend

### New component: `DenominationBreakdownPopup`

- Props: `{ title: String, initialLines?: Array, getPayload: Function, close: Function }`.
- Bills: `pos.models["pos.bill"]`, sorted by value (the same set the server allows at load time).
- State: `{ [bill.id]: quantity }`. It is keyed by id, never by float value.
- Inputs: `NumericInput`. Only non-negative integers are accepted, and Confirm is disabled otherwise.
- `getPayload({ total, lines: [{bill_id, quantity}] (quantity > 0), notesText })`. `notesText` uses the stock `MoneyDetailsPopup` format (`money_details_popup.js:48-65`), so the opening and closing notes stay the same.

### Patches (all use `patch()` with `super`; templates use `t-inherit-mode="extension"`)

| Target | JS change | Template xpath (robust anchors) |
|---|---|---|
| `CashMovePopup` | `static props = [...CashMovePopup.props, "initialType?", "initialReasonId?"]`. `setup`: state gets `note`, `reasonId`, `breakdown`. The type is forced to `"out"` unless cash-in is enabled. The reason is preselected (initial prop, then the loaded default cash-out reason, otherwise none). `onClickButton('in')` is ignored when cash-in is off and resets the reason. `isValidCashMove` requires a valid amount, a reason, and a matching breakdown when required. `confirm`: sets `state.reason = compose(reasonName, note)` (receipt text), then calls `super.confirm()`. `_prepareTryCashInOutPayload`: calls super, then merges `{reason_id, note, denomination_lines}` into the last element (the `pos_hr` pattern). `openNumpadDialog` opens the breakdown popup when required. | `//button[contains(@t-on-click,"'in'")]`, attribute `t-if="pos.config.cash_in_enabled"`; `//textarea[@name='reason']`, attribute `t-model="state.note"` and label "Note (optional)"; a reason `<select>` inserted `before` `//div[hasclass('form-floating')]`; `//Input`, attribute `readonly="ui.isSmall or pcdcCountRequired"`; a breakdown button `after` the Input container |
| `pos.cashMove(options = {})` (PosStore) | Without options, returns `super.cashMove()`. With options, it opens the cashbox and returns `makeAwaitable(this.dialog, CashMovePopup, {initialType, initialReasonId})`, then refreshes the vault state. | |
| `OpeningControlPopup` | `openDetailsPopup` opens the breakdown popup when required (otherwise super). `confirm` shows a notification and stops if a required breakdown is missing; otherwise it stages kwargs and calls super in `try/finally` to clear the stage. | `//div[hasclass('opening-cash-section')]//Input`, attribute `readonly` |
| `ClosePosPopup` | `openDetailsPopup` opens the breakdown popup when required. `canConfirm` = super and (not required or breakdown). `closeSession` stages kwargs and calls super in `try/finally`. `autoFillCashCount` does nothing when required. | `//Input[contains(@class,'cash-input')]`, attribute `readonly`; `//button[@t-on-click='autoFillCashCount']`, attribute `t-if="!pcdcClosingCountRequired"` |
| `Navbar` | `components` gets `VaultAlertIndicator` | `//div[hasclass('status-buttons')]`, `position="inside"`, `<VaultAlertIndicator/>` (CSS `order:-1` puts it first without depending on sibling order) |
| `PosData` | `call()`: merges staged kwargs for `(pos.session, set_opening_control / post_closing_cash_details)`, one shot. `execute()`: replay rejection handling (ADR-7). | |
| `PosStore` | `afterProcessServerData`, `syncAllOrders` (when orders were synced), and `cashMove` call `refreshVaultState()`. Adds the replay-rejection listener. | |

"Required" flags are computed getters: `pos.config.cash_control && pos.config.cash_count_*_required` (and for IN, also `cash_in_enabled`).

### Vault alert state (PosStore patch)

- `this.vaultAlert = reactive({ required, expected, threshold, known })`.
- `refreshVaultState()` does nothing when offline or when `config.vault_withdrawal_threshold <= 0`. Otherwise it calls `data.silentCall("pos.session", "get_vault_withdrawal_state", [session.id])`. One call runs at a time, with one trailing call if more are requested.
- On a `false -> true` transition, or on load when already required, it calls `notification.add(_t("Vault withdrawal required"), { type: "warning" })`.
- Offline, the indicator keeps the last known state.
- Indicator click: if `!pos.showCashMoveButton`, show a notification. Otherwise call `pos.cashMove({ initialType: "out", initialReasonId })`. `initialReasonId` is the POS default when it is a vault reason, otherwise the first active loaded vault reason by sequence, otherwise nothing.

## Architecture Decisions

### ADR-1: Additive kwarg on `set_opening_control`, with the logic in `_set_opening_control_data` through context

**Choice**: `set_opening_control(cashbox_value, notes, denomination_lines=None)` only puts the lines into the context and calls super. Validation and persistence happen in the `_set_opening_control_data(cashbox_value, notes)` override, which reads the context. A code comment marks the deliberate "DO NOT INHERIT" exception.

**Alternatives considered**:
- Passing the kwarg down to `_set_opening_control_data`. Rejected: `pos_hr`'s fixed-signature override (`pos_hr/models/pos_session.py:23`) would raise `TypeError` whenever it is above ours in the MRO.
- Changing the positional signature. Rejected: it breaks callers.
- A separate RPC. Rejected: the opening is queued offline, so two calls cannot be replayed atomically.

**Rationale**: the public signature is a strict superset, no business logic lives in the public method, and the behavior does not depend on MRO order. The remaining risk is a third-party module that overrides `set_opening_control` with a strict signature *above* ours. That module already violates the core contract, and the risk is documented.

### ADR-2: New id-keyed breakdown popup instead of reusing `MoneyDetailsPopup`

**Choice**: a new `DenominationBreakdownPopup` whose payload is `[{bill_id, quantity}]`. It is used only when a toggle is on.

**Alternatives considered**:
- Patching `MoneyDetailsPopup`. Rejected: its state is keyed by the float value (`money_details_popup.js:30`), and it would change stock behavior when toggles are off.
- Mapping values back to ids. Rejected: ambiguous for bills with the same value.

**Rationale**: the stock popup stays untouched when toggles are off (stock guarantee), and the payload matches the server contract exactly.

### ADR-3: Header plus lines model

**Choice**: a `pos.cash.denomination.count` header and `...count.line`, with denormalized stored related fields on the lines.

**Alternatives considered**:
- Lines only. Rejected: attribution, reason, total, and the statement link would repeat on every line and could get out of sync.
- JSON on the statement line or session. Rejected: it cannot be used in pivot or graph views and has no ACL granularity.

**Rationale**: one count event is one header. It anchors the statement link, the reason, and the attribution. Lines group directly in pivot and graph views.

### ADR-4: Expected cash computed on the server, with a parity test

**Choice**: a session helper that collects the core inputs and calls the pure `compute_expected_cash`, exposed by `get_vault_withdrawal_state`.

**Alternatives considered**:
- A client-side running balance. Rejected: the stock POS keeps none, and it breaks with several devices.
- Overriding `get_closing_control_data`. Rejected: it widens the blast radius on a method that `pos_hr` also extends (`pos_hr/models/pos_session.py:70`).

**Rationale**: the server is correct for any number of devices, and the parity test detects core drift.

### ADR-5: One-shot kwargs staging on `PosData.call` for opening and closing

**Choice**: the popup patch stages `{denomination_lines}` for exactly one `(model, method)` pair right before `super.confirm()` / `super.closeSession()` and clears it in `finally`. The `PosData.call` patch merges the staged kwargs into that call. Because the queue stores `[...arguments]` of `execute` (`data_service.js:705-710`), offline replays keep the kwargs.

**Alternatives considered**:
- Copying the stock `confirm` / `closeSession` bodies (about 60 lines). Rejected: this is fragile under upgrades and under Enterprise or third-party patches.
- A separate "record closing count" RPC. Rejected: it adds a new public write endpoint and two-phase state, and it differs from the approved kwarg contract.
- Temporarily replacing `data.call` on the instance. Rejected: race-prone.

**Rationale**: a single atomic RPC and no duplicated stock code. The popups' methods are async-locked (`useAsyncLockedMethod`), so staging cannot leak across calls.

### ADR-6: Alert transport is a dedicated RPC, not a piggy-back on the order sync (open question 4, resolved)

**Choice**: `get_vault_withdrawal_state` through `silentCall`. It is triggered on load, after `syncAllOrders` returns synced orders, and after a cash move.

**Alternative considered**: adding a key to the `sync_from_ui` response. Rejected: the response goes through `missingRecursive` / `loadConnectedData` as model data (`pos_store.js:1600-1605`), and other clients (self-order) share that endpoint.

**Rationale**: isolated, non-blocking, and easy to remove. One small aggregate query per refresh.

### ADR-7: UX for offline-replayed rejected operations (open question 1, resolved)

**Choice**: the `PosData.execute` patch catches errors **only on replays** (a `uuid` is present, and it is only set by `syncData`, `data_service.js:829`). It acts only for `pos.session.try_cash_in_out` / `set_opening_control` and only for business RPC errors (`UserError`, `ValidationError`, `AccessError`, `MissingError`). In that case it dispatches `window` `CustomEvent("pcdc-replay-rejected", {detail:{method, message}})` and returns a truthy sentinel, so `syncData` drops the item. The PosStore listener shows a blocking `AlertDialog`:
- Cash move: "A cash move recorded while offline was rejected and NOT recorded: {message}. Record it again." Then the vault state is refreshed.
- Opening: "The session opening was rejected: {message}." Then the page reloads, which shows the opening popup again. This is the same reload approach as `opening_control_popup.js:54`.

**Alternatives considered**:
- Keeping the stock behavior. Rejected: the rejected item blocks every later queued call silently.
- Changing the server to not raise. Rejected: the proposal requires rejection.

**Rationale**: the server stays the source of truth, the operator is told explicitly, and the queue does not deadlock. Other methods keep the stock behavior.

### ADR-8: Soft employee reference (see Data Model)

**Choice**: Integer plus a name snapshot.

**Alternatives considered**:
- A Many2one to `hr.employee`. Rejected: it needs `hr`.
- A bridge module now. Deferred: it adds a second module to this change.
- `Many2oneReference`. Rejected: it adds complexity for no gain.

### ADR-9: Closing guard keyed on a valid closing count at `_validate_session`

See the flow above. **Alternatives considered**:
- `action_pos_session_closing_control`. Rejected: `validate` and `close` are RPC-callable and bypass it.
- `action_pos_session_close`. Rejected: it works, but `_validate_session` is the single state writer and sits before core's `sudo()`.

### ADR-10: Server composes `payment_ref`; the client composes only the receipt text

**Choice**: the client sets `state.reason` to "Reason: note" only so that the stock receipt prints it. The server ignores the positional `reason` when `extras.note` is present and composes the text from `reason_id`.

**Alternative considered**: patching `CashMoveReceipt`. Rejected: its props are passed inline in `confirm` (`cash_move_popup.js:78-84`).

### Community/Enterprise deltas

The module has no Enterprise-only code. Every patch targets Community components that Enterprise loads unchanged into `point_of_sale._assets_pos`. The Enterprise risk is an Enterprise module that rewrites the same templates. In Owl, a failing xpath in an extension breaks the asset bundle at load time, which means the **POS does not boot**. For that reason all anchors use `hasclass`, `@name`, or `@t-on-click` (no positional paths), and the whole Python and tour suite runs on an Enterprise staging database before deployment (checklist below).

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Domain | breakdown (types, duplicates, allowed bills, rounding edge cases such as 0.005 and 16,4 values, empty list), reason (every code, vault only for out), move type, closing decision table, expected cash, threshold (0, equal, above, rounding), `compose_payment_text`, purity | `BaseCase`, tag `pcdc_domain`, no env; AST purity test |
| Models | install defaults (existing configs: cash-in off, Vault default reason), reason constraints (SQL and Python), ACL and record rules (multi-company) | `TransactionCase` on `point_of_sale.tests.common.CommonPosTest` |
| Enforcement | cash-in rejected, including direct calls; missing, inactive, wrong-company, and wrong-direction reasons; vault on IN; breakdown errors per toggle; nothing created on rejection; header, lines, and statement link; `payment_ref`; opening and closing with and without toggles; idempotent opening replay | `TransactionCase` with `with_user` for a POS user, a manager, and a user without permission |
| Closing guard | non-manager: POS path passes; back-office button, wizard, `action_pos_session_validate`, and `action_pos_session_close` raise and create no `move_id`; manager: flagged and chatter posted; rescue session; mismatched count | `TransactionCase` |
| Vault | parity with `get_closing_control_data()['default_cash_details']['amount']` after orders, cash moves, and difference lines; threshold states; access check | `TransactionCase` |
| JS unit | breakdown popup (id keys, integer validation, payload, notes text); cash move popup (no "Cash In" button when off, reason filtering and preselection, confirm disabled, payload extras, receipt text); `cashMove` options; staging merge and clear; replay rejection sentinel; navbar indicator render and click | Hoot, `static/tests/unit`, mocks patched into `hootPosModels`, `PosSession` (`_load_pos_data_models`, `get_vault_withdrawal_state`), and `PosConfig` records |
| Tours | opening with breakdown; cash-out with reason; cash-in disabled; reason and denomination rejection; POS closing with breakdown as a non-manager; vault alert and one-click cash-out | `HttpCase` on `TestPointOfSaleHttpCommon` (`point_of_sale/tests/test_frontend.py:34`), `start_pos_tour` |
| Coexistence | the suite runs again with `pos_hr` installed | second run `-i pos_cash_denomination_control,pos_hr` |

Hoot runner: `tests/test_hoot.py` is an `HttpCase` that runs `browser_js` on `/web/tests?headless&loglevel=2&preset=desktop&filter=@pos_cash_denomination_control` with the Hoot success signal. The exact URL parameters and signal are copied in slice 1 from the image's `web/tests/test_js.py` (not in the sparse clone).

### Docker runner (dev instance and test runner)

- `docker/Dockerfile`: `FROM odoo:19.0`, `USER root`, install `google-chrome-stable` from Google's `.deb` (headless browser for tours and Hoot; the distribution's `chromium` is a snap stub on Ubuntu), `USER odoo`.
- `docker-compose.yml`:
  - `db`: `postgres:16`, `POSTGRES_USER=odoo`, `POSTGRES_PASSWORD=odoo`, `POSTGRES_DB=postgres`, volume `pgdata`.
  - `odoo`: build `./docker`, `depends_on: db`, `ports: 8069:8069`, environment `HOST=db USER=odoo PASSWORD=odoo`, volumes `.:/mnt/extra-addons:ro` (repository root; the addon lives at the root, OCA style) and `odoo-data:/var/lib/odoo`.
  - `up` runs the dev instance. `run --rm` runs tests in a separate container, so there is no port clash.
- Test command (`scripts/test.sh [extra_modules]`):

```
docker compose exec -T db dropdb -U odoo --if-exists pcdc_test
docker compose run --rm odoo odoo -d pcdc_test \
  -i pos_cash_denomination_control${EXTRA:+,$EXTRA} \
  --test-enable --test-tags /pos_cash_denomination_control \
  --stop-after-init --log-level=test
```

Fast domain loop: `--test-tags pcdc_domain/pos_cash_denomination_control`. With `pos_hr`: `scripts/test.sh pos_hr`. The demo-data flag policy (`--without-demo` or `--with-demo` in 19.0) is confirmed with `odoo --help` in slice 1 and pinned in `docker/odoo.conf`. `openspec/config.yaml` (`apply.test_command`, `strict_tdd: true`) is updated when slice 1 lands.

## Threat Matrix

N/A: there is no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary in the addon. The `scripts/test.sh` helper is developer tooling with fixed arguments and takes no untrusted input.

## Migration / Rollout

- **Install on a database with existing POS configs**:
  - every config gets `allow_cash_in=False` (column default), all count toggles off, threshold 0, and `default_cash_out_reason_id=Vault` (hook);
  - a reason becomes required on every cash move immediately.
- **Upgrade**: the version is `19.0.1.0.0`. Later changes use `migrations/19.0.x.y.z/`. Seed data is `noupdate`.
- **Uninstall**:
  - the ORM drops the new tables and columns, the reason catalog, and the session flags;
  - the core `payment_ref` text and the chatter messages remain;
  - the assets disappear, so the stock UI returns.
  - Export count lines, statement-line reasons, and flags first if the history matters.
- **Coexistence rules** (for code review):
  - always call `super()`;
  - no `replace` templates or `position="replace"`;
  - only optional props are added;
  - public entry points only add optional kwargs;
  - internal data travels through context;
  - no override of `get_closing_control_data`.
- **Known conflicts** (documented in `readme/ROADMAP.md`):
  - core `test_point_of_sale_flow.py:3212` (no reason) and `chrome_tour.js:209` (cash IN and a free-text reason) fail while the module is installed; run core suites without it;
  - external callers of `try_cash_in_out` without `reason_id` are rejected;
  - a third-party strict-signature override of `set_opening_control` or `post_closing_cash_details` above ours raises `TypeError`.
- **Pre-install / pre-upgrade checklist**:
  1. Close all open POS sessions, or at least make sure no session is in `opening_control` with pending offline openings.
  2. Bring every POS device online and wait until the navbar shows no unsynced counter. The offline queue is in memory (confirmed empirically in Phase 13, see the Discovery table's "Offline queue" row), and cash moves queued before the upgrade have no `reason_id`, so they would be rejected — and if the device is reloaded while still offline before syncing, the queued cash move is lost outright, not merely rejected.
  3. Back up the database.
  4. Install on staging (Enterprise if applicable) and run the full suite and tours.
  5. After install, reload every POS client (new assets).
  6. Re-enable cash-in on the POS configs that need it.
  7. Review the default reason and the thresholds.

## Open Questions

- [x] Verify in slice 1 against the `odoo:19.0` image: that `odoo.tests.BaseCase` exists and carries tags; the Hoot `browser_js` URL, filter syntax, and success signal; the demo flag name; and the base distribution for installing Chrome (amd64 only, so ARM hosts need an alternative). **Resolved** (Phase 1, tasks 1.6–1.9; full evidence in `docs/testing.md`):
  - `from odoo.tests import BaseCase` exists; MRO `odoo.tests.common.BaseCase → odoo.tests.case.TestCase → unittest.case.TestCase → object`; `@tagged(...)` stores tags on `test_tags` (not `_tags`).
  - Hoot: `filter` URL param (alias `name`) matches full name or tags as a search string; `tag`/`tags` for exact tag match. For `tests/test_hoot.py` (Phase 13): URL `/web/tests?headless&loglevel=2&preset=desktop&filter=@pos_cash_denomination_control`, success signal `[HOOT] Test suite succeeded`, error checker `odoo.addons.web.tests.test_js.unit_test_error_checker`.
  - Demo flag: `without_demo = False` in `docker/odoo.conf` resolves to `with_demo = True` (demo installed); also the default with neither `--with-demo` nor `--without-demo` passed.
  - Chrome: `google-chrome-stable` (Google's `.deb`, amd64 only — no arm64 build, documented as a known ARM-host limitation) plus the Python **`websocket-client`** package, which is *not* in the base `odoo:19.0` image. Without it, tours silently **skip** ("websocket-client module is not installed") instead of running through Chrome or failing loudly — a real trap for anyone assuming a skip means "not applicable." Fixed in `docker/Dockerfile`. Verified end-to-end: core `point_of_sale` demo tour `pos_pricelist` (`TestUi.test_01_pos_basic_order`) ran headlessly and succeeded (`0 failed, 0 error(s)`).
- [ ] Performance: `get_vault_withdrawal_state` walks `_get_closed_orders()` like the core. It is acceptable for typical daily volumes; switch to a `_read_group` only if profiling shows a problem (the parity test protects any change).

None of these block tasks.
