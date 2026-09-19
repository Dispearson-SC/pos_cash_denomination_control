import { PosData } from "@point_of_sale/app/services/data_service";
import { patch } from "@web/core/utils/patch";
import { RPCError } from "@web/core/network/rpc";

/**
 * design.md ADR-5: one-shot kwargs staging for `set_opening_control` and
 * `post_closing_cash_details`. Both methods are called from stock popup
 * code with inline kwarg literals (`{}` / `{counted_cash}`,
 * `opening_control_popup.js:44`, `closing_popup.js:212`), so this narrow
 * patch on `PosData.call` merges in `{denomination_lines}` for exactly the
 * next matching `(model, method)` call, then clears itself immediately —
 * a true one-shot, so a staged value can never leak into an unrelated later
 * call even if a popup's own `try/finally` clearing
 * (`opening_control_popup_patch.js`, `closing_popup_patch.js`) were somehow
 * skipped. The popups' own `confirm`/`closeSession` methods are already
 * async-locked (`useAsyncLockedMethod`), so two stagings can never race.
 *
 * design.md ADR-7: UX for offline-replayed rejected operations. Stock
 * `syncData` (`data_service.js:823-841`) rethrows a replayed call's
 * rejection but never shifts the failed item off `network.unsyncData`, so a
 * business rejection (wrong reason, stale denomination lines, ...)
 * silently blocks every later queued call. `execute()` below catches a
 * rejection only when it is a replay (`uuid` is truthy — only `syncData`
 * sets it, `data_service.js:829`) of `pos.session.try_cash_in_out` /
 * `set_opening_control`, and only for a business RPC error (`UserError`,
 * `ValidationError`, `AccessError`, `MissingError`). In that case it
 * dispatches a `window` `CustomEvent` (handled by `pos_store_patch.js`) and
 * returns a truthy sentinel so `syncData` drops the rejected item instead
 * of retrying it forever. Any other error (a different method/model, a
 * non-business error such as `ConnectionLostError`, or a live/non-replay
 * call) is rethrown unchanged.
 */

const PCDC_STAGED_METHODS = new Set(["set_opening_control", "post_closing_cash_details"]);
const PCDC_REPLAY_REJECTABLE_METHODS = new Set(["try_cash_in_out", "set_opening_control"]);
const PCDC_BUSINESS_ERROR_NAMES = new Set([
    "odoo.exceptions.UserError",
    "odoo.exceptions.ValidationError",
    "odoo.exceptions.AccessError",
    "odoo.exceptions.MissingError",
]);

function isPcdcBusinessError(error) {
    return error instanceof RPCError && PCDC_BUSINESS_ERROR_NAMES.has(error.data?.name);
}

patch(PosData.prototype, {
    async setup() {
        await super.setup(...arguments);
        this._pcdcStagedKwargs = null;
    },

    /** One-shot: consumed (and cleared) by the very next matching `call()`. */
    stagePcdcKwargs(model, method, kwargs) {
        this._pcdcStagedKwargs = { model, method, kwargs };
    },

    clearPcdcStagedKwargs() {
        this._pcdcStagedKwargs = null;
    },

    async call(model, method, args = [], kwargs = {}, queue = false) {
        const staged = this._pcdcStagedKwargs;
        if (
            staged &&
            staged.model === model &&
            staged.method === method &&
            PCDC_STAGED_METHODS.has(method)
        ) {
            this._pcdcStagedKwargs = null;
            kwargs = { ...kwargs, ...staged.kwargs };
        }
        return super.call(model, method, args, kwargs, queue);
    },

    async execute(params) {
        try {
            return await super.execute(...arguments);
        } catch (error) {
            const { model, method, uuid } = params;
            if (
                uuid &&
                model === "pos.session" &&
                PCDC_REPLAY_REJECTABLE_METHODS.has(method) &&
                isPcdcBusinessError(error)
            ) {
                window.dispatchEvent(
                    new CustomEvent("pcdc-replay-rejected", {
                        detail: { method, message: error.data.message },
                    })
                );
                return true;
            }
            throw error;
        }
    },
});
