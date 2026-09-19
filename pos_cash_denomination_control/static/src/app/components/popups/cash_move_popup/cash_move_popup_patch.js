import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";
import { patch } from "@web/core/utils/patch";

patch(CashMovePopup.prototype, {
    onClickButton(type) {
        if (type === "in" && !this.pos.config.allow_cash_in) {
            this.state.type = "out";
            return;
        }
        super.onClickButton(type);
    },
});
