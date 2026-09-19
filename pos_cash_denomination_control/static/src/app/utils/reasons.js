/**
 * Pure helpers for filtering and selecting `pos.cash.move.reason` records.
 *
 * Shared between the cash move popup's reason selector (`cash-move-reasons`
 * spec, Phase 5) and the vault withdrawal alert's one-click cash-out
 * preselection (`vault-withdrawal-alert` spec, Phase 7), so both consumers
 * agree on the exact same direction-filtering and vault-reason-picking
 * rules.
 */

/** Reasons whose direction matches `moveType` exactly, or is "both". */
export function reasonsForMoveType(reasons, moveType) {
    return reasons.filter(
        (reason) => reason.direction === moveType || reason.direction === "both"
    );
}

/**
 * The first active vault reason, ordered by `sequence` then `id`.
 * Returns `undefined` when no active vault reason exists.
 *
 * `is_vault` is the only filter applied here: `pos.cash.move.reason`'s
 * `_load_pos_data_fields` never delivers an `active` field to the frontend
 * (see `models/pos_cash_move_reason.py`), so every loaded reason is already
 * guaranteed active — `pos.load.mixin`'s `search()` call implicitly excludes
 * inactive records server-side (Odoo's standard `active_test` behavior).
 * Checking a client-side `.active` flag here would always be `undefined`
 * and silently exclude every reason.
 */
export function firstActiveVaultReason(reasons) {
    return reasons
        .filter((reason) => reason.is_vault)
        .sort((a, b) => a.sequence - b.sequence || (a.id > b.id ? 1 : -1))[0];
}
