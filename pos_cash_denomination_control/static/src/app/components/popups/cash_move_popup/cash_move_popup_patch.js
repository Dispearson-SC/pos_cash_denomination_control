import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";
import { patch } from "@web/core/utils/patch";
import { reasonsForMoveType } from "@pos_cash_denomination_control/app/utils/reasons";

patch(CashMovePopup, {
    props: [...CashMovePopup.props, "initialType?", "initialReasonId?"],
});

patch(CashMovePopup.prototype, {
    setup() {
        super.setup();
        if (this.props.initialType) {
            this.state.type = this.props.initialType;
        }
        this.state.reasonId = this.props.initialReasonId ?? this._defaultReasonId();
        this.state.note = "";
    },
    onClickButton(type) {
        if (type === "in" && !this.pos.config.allow_cash_in) {
            this.state.type = "out";
            return;
        }
        super.onClickButton(type);
        this.state.reasonId = this._defaultReasonId();
    },
    /**
     * The reasons whose direction is compatible with the current move type
     * (an exact match, or a shared "both" reason). Backs `cash-move-reasons`
     * spec's "Selector filters reasons by direction" scenario.
     */
    get availableReasons() {
        return reasonsForMoveType(this.pos.models["pos.cash.move.reason"].getAll(), this.state.type);
    },
    /**
     * The POS default cash-out reason, only for an "out" move. A missing
     * default yields no preselection; an archived default yields no
     * preselection too, because `pos.load.mixin`'s domain already excludes
     * inactive reasons from the frontend load, so an archived default's
     * relation never resolves to a loaded record (`cash-move-reasons` spec).
     */
    _defaultReasonId() {
        if (this.state.type !== "out") {
            return false;
        }
        const defaultReason = this.pos.config.default_cash_out_reason_id;
        return defaultReason ? defaultReason.id : false;
    },
    isValidCashMove() {
        return this.env.utils.isValidFloat(this.state.amount) && Boolean(this.state.reasonId);
    },
    _prepareTryCashInOutPayload() {
        const result = super._prepareTryCashInOutPayload(...arguments);
        result[result.length - 1] = {
            ...result[result.length - 1],
            reason_id: this.state.reasonId,
            note: this.state.note,
        };
        return result;
    },
});
