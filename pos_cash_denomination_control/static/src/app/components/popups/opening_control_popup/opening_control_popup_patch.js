import { OpeningControlPopup } from "@point_of_sale/app/components/popups/opening_control_popup/opening_control_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { DenominationBreakdownPopup } from "@pos_cash_denomination_control/app/components/popups/denomination_breakdown_popup/denomination_breakdown_popup";

/**
 * `pos-denomination-ui` spec (Requirement: Read-Only Amount Input +
 * Requirement: Breakdown Is Transported To The Server) + design.md ADR-5:
 * when the opening toggle is on, the opening cash amount becomes read-only
 * (see `.xml`) and settable only through `DenominationBreakdownPopup`;
 * confirming without a breakdown is blocked with a notification, and
 * confirming with one stages `{denomination_lines}` for the one-shot
 * `PosData.call` merge (`data_service_patch.js`).
 */
patch(OpeningControlPopup.prototype, {
    setup() {
        super.setup();
        this.notification = useService("notification");
        this.pcdcBreakdownLines = null;
    },

    /** `pos.config.cash_control && pos.config.cash_count_opening_required`. */
    get pcdcCountRequired() {
        return Boolean(
            this.pos.config.cash_control && this.pos.config.cash_count_opening_required
        );
    },

    async openDetailsPopup() {
        if (!this.pcdcCountRequired) {
            return super.openDetailsPopup();
        }
        const action = _t("Cash control - opening");
        await this.pos.openCashbox(action);
        this.dialog.add(DenominationBreakdownPopup, {
            title: action,
            initialLines: this.pcdcBreakdownLines || [],
            getPayload: ({ total, lines, notesText }) => {
                this.state.openingCash = this.env.utils.formatCurrency(total, false);
                this.pcdcBreakdownLines = lines;
                if (notesText) {
                    this.state.notes = notesText;
                }
            },
        });
    },

    async confirm() {
        if (this.pcdcCountRequired && !this.pcdcBreakdownLines) {
            this.notification.add(
                _t("Enter the opening cash breakdown before confirming."),
                { type: "danger" }
            );
            return;
        }
        if (this.pcdcCountRequired) {
            this.pos.data.stagePcdcKwargs("pos.session", "set_opening_control", {
                denomination_lines: this.pcdcBreakdownLines,
            });
        }
        try {
            await super.confirm();
        } finally {
            this.pos.data.clearPcdcStagedKwargs();
        }
    },
});
