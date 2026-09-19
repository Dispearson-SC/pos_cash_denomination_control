# Denomination count reports

Locator: `odd/tasks/denomination-count-reports.md` · Engram mirror: `odd/denomination-count-reports/tasks` (project `caja-boveda`)

## Objective
Make denomination records navigable from POS sessions: one row per cash movement (total + reason) that drills down into its denomination lines, and a line report that links back to the session.

## Problem / Why
Only the line-level report exists (`pos.cash.denomination.count.line` list/pivot/graph). The movement header (`pos.cash.denomination.count`) has no views, and sessions have no entry point to their denomination movements. Users need "a 1,500 withdrawal with reason Vault" as one row, with the breakdown one click away, and navigation to the session.

## Scope (authorized by the user on 2026-09-19)
- Smart button on the `pos.session` form: "Denomination Movements" (with count) opening that session's movements.
- Movement (header) views: list (date, session, POS, move type, reason, total, user/employee, note), form (header fields + session link + read-only denomination lines), search (filters by move type/reason; group by session, POS, move type, reason, date). Row click opens the movement form with its breakdown.
- Menu entry "Denomination Movements" under POS Reporting, next to the existing line report.
- Line report: add the POS session column, group-by session, and a per-row control that opens the session form.
- "Open session" button on the movement form.
- Spanish translations for all new strings (`i18n/es.po` + `.pot`).

Out of scope: changing defaults of the denomination toggles (user decided they stay off), new data/models.

## Constraints
- Odoo 19; addon at repo root; views inherit/extend only (no core template replacement); records remain read-only for all users (existing ACLs: writes only via sudo adapter code).
- Multi-company record rules already apply to header and lines.
- Strict TDD (runner `./scripts/test.sh`, source: `openspec/config.yaml` `strict_tdd: true`). Verify with `./scripts/test.sh` and `./scripts/test.sh pos_hr`.
- Branch `feature/pos-cash-denomination-control-16-count-reports` from `-15-i18n-es`. Conventional Commits, no AI attribution. No push/PR/merge.
- Delivery: feature-branch-chain continues; forecast ~300–450 authored lines.

## Tasks
- [x] T1 Movement views (list/form/search), action, and menu; tests first. Route: delegated (2+ non-trivial files).
- [x] T2 Session smart button + `action_view_denomination_movements` + movement count; tests first. Route: delegated (same writer).
- [x] T3 Line report: session column, group-by session, open-session control; movement form "Open session" button; tests first. Route: delegated (same writer).
- [ ] T4 Spanish translations for new strings; full suite green in both runs. Route: delegated (same writer).

## Acceptance criteria
- Session form shows a "Denomination Movements" button with the correct count; it opens only that session's movements.
- Movement list shows one row per movement with total and reason; opening a row shows its denomination lines.
- Movement and line reports can be grouped by session; a line or movement can navigate to the session form.
- UI strings appear in Spanish for es_MX.
- `./scripts/test.sh` and `./scripts/test.sh pos_hr`: 0 failed, count > 148.

## Progress / Evidence
- Created 2026-09-19. Trigger evidence: writer trigger (views XML + models + tests + i18n = 4+ files).
- Branch `feature/pos-cash-denomination-control-16-count-reports` created from `-15-i18n-es` (93ba20f).
- T1–T3 implemented together (tightly coupled: models + views + tests). TDD evidence:
  - RED: `tests/test_count_reports.py` (12 tests, tag `pcdc_count_reports`) — `./scripts/test.sh "" -- --test-tags pcdc_count_reports/pos_cash_denomination_control` → `3 failed, 8 error(s) of 12 tests`.
  - GREEN after implementation: same command → `0 failed, 0 error(s) of 12 tests`.
  - Added: `pos.cash.denomination.count.action_open_session()`, `pos.cash.denomination.count.line.action_open_session()`, `pos.session.pcdc_count_movement_count` (compute, no `@api.depends`, mirrors core `_compute_order_count`) + `action_view_denomination_movements()`.
  - Views: movement list/form/search + `action_pos_cash_denomination_count` + menu `menu_pos_cash_denomination_count_movement` (sequence 7, `Cash Moves` bumped to 8) in `pos_cash_denomination_count_views.xml`/`menus.xml`; session smart button via xpath on `//div[@name='button_box']` (confirmed present on `point_of_sale.view_pos_session_form` in the installed Odoo 19 image) in `pos_session_view.xml`; line list session column (`optional="show"`) + `action_open_session` row button + search group-by-session in `pos_cash_denomination_count_views.xml`.
  - Multi-company: added a header-level rule test (`test_header_multi_company_rule_hides_other_company_movements`) alongside the pre-existing line-level one; both pass unmodified — new views/action did not touch record rules.
- T4 (i18n) in progress next.

## Next step
T4: regenerate `.pot`, translate new strings into `i18n/es.po`, run both full suites.
