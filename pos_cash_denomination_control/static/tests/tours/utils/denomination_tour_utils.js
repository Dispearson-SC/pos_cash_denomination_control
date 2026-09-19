/**
 * Shared tour helpers for `pos_cash_denomination_control`'s end-to-end
 * tours (spec `pos-denomination-ui`, Requirement: End-To-End Flows Are
 * Verified By Tours).
 *
 * `DenominationBreakdownPopup` always lists every `pos.bill` the server
 * allows for the config (`pos.bill._load_pos_data_domain`'s `OR
 * pos_config_ids = False` clause also always includes the core seed bills,
 * regardless of a config's own `default_bill_ids`), so a tour cannot rely
 * on the popup showing only one row. `denomination_breakdown_popup.xml`
 * carries a `data-bill-name` attribute per row (Phase 13 addition, for
 * tour targeting only — no behavior change) so a specific bill's quantity
 * input can be addressed directly by the same `name` Python setup gave it,
 * independent of currency formatting or bill ordering.
 *
 * `DenominationBreakdownPopup` stacks on top of the popup that opened it
 * (`dialog.add` never closes the caller), so every step below is scoped by
 * the breakdown popup's own title (the exact `_t(...)` string each caller
 * passes) to never hit the caller's own same-named button (for example
 * `CashMovePopup`'s `.button.confirm`) while both are visible at once.
 */

function scoped(title, suffix = "") {
    return `.o_dialog:has(.modal-header:contains("${title}")) ${suffix}`.trim();
}

export function enterBreakdownQuantity(title, billName, quantity) {
    return {
        content: `Enter denomination quantity ${quantity} for bill "${billName}" in the "${title}" popup`,
        trigger: scoped(title, `div[data-bill-name="${billName}"] input.o_input`),
        run: `edit ${quantity}`,
    };
}

export function confirmBreakdownPopup(title) {
    return {
        content: `Confirm the "${title}" denomination breakdown`,
        trigger: scoped(title, ".button.confirm"),
        run: "click",
    };
}

/**
 * `openTrigger` clicks the icon button that opens the breakdown popup
 * (different per caller: opening, cash move, or closing popup); `title` is
 * the popup's own title, used to scope every subsequent step to it;
 * `billName` is the `pos.bill.name` Python setup gave the bill under test.
 */
export function enterBreakdown(openTrigger, title, billName, quantity) {
    return [
        {
            content: `Open the "${title}" denomination breakdown popup`,
            trigger: openTrigger,
            run: "click",
        },
        enterBreakdownQuantity(title, billName, quantity),
        confirmBreakdownPopup(title),
    ];
}

export function selectCashMoveReason(reasonName) {
    return {
        content: `Select cash-move reason "${reasonName}"`,
        trigger: "select.pcdc-reason-select",
        run: `selectByLabel ${reasonName}`,
    };
}
