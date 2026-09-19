/**
 * Pure helpers for the denomination breakdown popup (`pos-denomination-ui`
 * spec, ADR-2). State is a plain object keyed by `pos.bill.id -> quantity`,
 * never by float value, so bills sharing the same value are never conflated.
 *
 * Mirrors `domain/breakdown.py::compute_total`'s Σ(quantity × bill_value)
 * semantics (see the cross-reference comment there): both implementations
 * must agree on the total for the same lines.
 */

import { _t } from "@web/core/l10n/translation";

/** Σ(quantity × bill.value) for the entered lines. Non-integer or missing
 * quantities count as zero, so a partially-typed input never breaks the
 * running total shown to the user. */
export function computeBreakdownTotal(bills, quantitiesByBillId) {
    return bills.reduce((total, bill) => {
        const quantity = quantitiesByBillId[bill.id];
        return total + (Number.isInteger(quantity) ? quantity : 0) * bill.value;
    }, 0);
}

/** `[{bill_id, quantity}]`, one entry per bill with a strictly positive
 * quantity — matching the server contract (`denomination_lines`). */
export function buildBreakdownPayload(bills, quantitiesByBillId) {
    return bills
        .filter((bill) => quantitiesByBillId[bill.id] > 0)
        .map((bill) => ({ bill_id: bill.id, quantity: quantitiesByBillId[bill.id] }));
}

/**
 * Human-readable breakdown note, mirroring the stock `MoneyDetailsPopup`
 * format (`money_details_popup.js:47-65`): a header line, one
 * "<quantity> x <formatted value>" line per non-zero entry, and a trailing
 * translated total line. Returns `null` when the total is zero, exactly
 * like the stock popup returns a `null` `moneyDetailsNotes` in that case.
 */
export function buildBreakdownNoteText(title, bills, quantitiesByBillId, formatCurrency) {
    const total = computeBreakdownTotal(bills, quantitiesByBillId);
    if (total === 0) {
        return null;
    }
    let notesText = `${title} details: \n`;
    for (const bill of bills) {
        const quantity = quantitiesByBillId[bill.id];
        if (quantity > 0) {
            notesText += `\t${quantity} x ${formatCurrency(bill.value)}\n`;
        }
    }
    notesText += _t("Total: %s", formatCurrency(total));
    return notesText;
}
