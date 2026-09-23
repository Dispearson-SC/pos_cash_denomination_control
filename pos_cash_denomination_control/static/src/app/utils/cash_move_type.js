/**
 * A real, extractable translation for core's cash-move `type` state
 * ("in"/"out").
 *
 * Core's `cash_move_popup.js` computes `const translatedType = _t(type)`,
 * calling `_t()` on a runtime variable. Odoo's translation extractor only
 * scans for literal string arguments, so it never emits a `msgid` for
 * either value: `point_of_sale`'s own catalogue has no `msgid "out"` at
 * all, and its `msgid "in"` is translated `"en"` -- the Spanish
 * preposition, harvested from some unrelated literal elsewhere in that
 * catalogue. A cash-out therefore showed the raw `"out"` to the operator,
 * and a cash-in showed `"en"`, which looks deliberate and is arguably
 * worse.
 *
 * This addon owns and translates two explicit literals instead, so this
 * function's return value is always a genuine translatable string in this
 * addon's own `.po` files.
 *
 * See odd/tasks/spanish-translations.md T3.
 */
import { _t } from "@web/core/l10n/translation";

export function translateCashMoveType(type) {
    return type === "in" ? _t("Cash In") : _t("Cash Out");
}
