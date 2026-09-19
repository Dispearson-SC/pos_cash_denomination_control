import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { reasonsForMoveType } from "@pos_cash_denomination_control/app/utils/reasons";
import { DenominationBreakdownPopup } from "@pos_cash_denomination_control/app/components/popups/denomination_breakdown_popup/denomination_breakdown_popup";

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
        this.pcdcBreakdownLines = null;
    },
    onClickButton(type) {
        if (type === "in" && !this.pos.config.allow_cash_in) {
            this.state.type = "out";
            return;
        }
        super.onClickButton(type);
        this.state.reasonId = this._defaultReasonId();
        // A breakdown entered for the previous type no longer applies: the
        // applicable toggle (in vs out) may differ for the new type.
        this.pcdcBreakdownLines = null;
    },
    /**
     * `pos-denomination-ui` spec (Requirement: Read-Only Amount Input):
     * `cash_count_out_required` for an "out" move, `cash_count_in_required`
     * for an "in" move, both gated by `cash_control`.
     */
    get pcdcCountRequired() {
        if (!this.pos.config.cash_control) {
            return false;
        }
        return this.state.type === "in"
            ? this.pos.config.cash_count_in_required
            : this.pos.config.cash_count_out_required;
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
        return (
            this.env.utils.isValidFloat(this.state.amount) &&
            Boolean(this.state.reasonId) &&
            (!this.pcdcCountRequired || Boolean(this.pcdcBreakdownLines))
        );
    },
    /**
     * Opens the denomination breakdown popup instead of the stock small-screen
     * numpad when a breakdown is required (regardless of screen size), since
     * the amount field is read-only and settable only through the breakdown.
     */
    async openNumpadDialog() {
        if (!this.pcdcCountRequired) {
            return super.openNumpadDialog();
        }
        this.dialog.add(DenominationBreakdownPopup, {
            title: _t("Cash movement breakdown"),
            initialLines: this.pcdcBreakdownLines || [],
            getPayload: ({ total, lines }) => {
                this.state.amount = this.env.utils.formatCurrency(total, false);
                this.pcdcBreakdownLines = lines;
            },
        });
    },
    _prepareTryCashInOutPayload() {
        const result = super._prepareTryCashInOutPayload(...arguments);
        const extras = {
            ...result[result.length - 1],
            reason_id: this.state.reasonId,
            note: this.state.note,
        };
        if (this.pcdcCountRequired) {
            extras.denomination_lines = this.pcdcBreakdownLines || [];
        }
        result[result.length - 1] = extras;
        return result;
    },
});
