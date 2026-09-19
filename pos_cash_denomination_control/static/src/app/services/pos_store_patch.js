import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    /**
     * Opens the cash move popup. With no options, this behaves exactly like
     * the stock method. With `{initialType, initialReasonId}`, it forwards
     * them as props so a caller (the vault withdrawal alert's one-click
     * cash-out, Phase 7) can open the popup preconfigured.
     */
    cashMove(options = {}) {
        if (Object.keys(options).length === 0) {
            return super.cashMove();
        }
        this.openCashbox(_t("Cash in / out"));
        return makeAwaitable(this.dialog, CashMovePopup, options);
    },
});
