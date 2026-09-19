import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { DenominationBreakdownPopup } from "@pos_cash_denomination_control/app/components/popups/denomination_breakdown_popup/denomination_breakdown_popup";

/**
 * `pos-denomination-ui` spec (Requirement: Read-Only Amount Input) +
 * design.md ADR-5: when the closing toggle is on, only the cash payment
 * method's counted amount becomes read-only (see `.xml`) and settable only
 * through `DenominationBreakdownPopup`. Non-cash payment methods are
 * untouched. RPC staging (`closeSession()`, ADR-5) is wired in Phase 12's
 * second slice, once `data_service_patch.js` exists.
 */
patch(ClosePosPopup.prototype, {
    setup() {
        super.setup();
        this.pcdcBreakdownLines = null;
    },

    /** `pos.config.cash_control && pos.config.cash_count_closing_required`. */
    get pcdcClosingCountRequired() {
        return Boolean(
            this.pos.config.cash_control && this.pos.config.cash_count_closing_required
        );
    },

    canConfirm() {
        return (
            super.canConfirm() &&
            (!this.pcdcClosingCountRequired || Boolean(this.pcdcBreakdownLines))
        );
    },

    /** Auto-fill from the expected amount would bypass the required count. */
    autoFillCashCount() {
        if (this.pcdcClosingCountRequired) {
            return;
        }
        super.autoFillCashCount();
    },

    async openDetailsPopup() {
        if (!this.pcdcClosingCountRequired) {
            return super.openDetailsPopup();
        }
        const action = _t("Cash control - closing");
        this.hardwareProxy.openCashbox(action);
        this.dialog.add(DenominationBreakdownPopup, {
            title: action,
            initialLines: this.pcdcBreakdownLines || [],
            getPayload: ({ total, lines, notesText }) => {
                this.state.payments[this.props.default_cash_details.id].counted =
                    this.env.utils.formatCurrency(total, false);
                this.pcdcBreakdownLines = lines;
                if (notesText) {
                    this.state.notes = notesText;
                }
            },
        });
    },

    async closeSession() {
        if (this.pcdcClosingCountRequired) {
            this.pos.data.stagePcdcKwargs("pos.session", "post_closing_cash_details", {
                denomination_lines: this.pcdcBreakdownLines,
            });
        }
        try {
            await super.closeSession();
        } finally {
            this.pos.data.clearPcdcStagedKwargs();
        }
    },
});
