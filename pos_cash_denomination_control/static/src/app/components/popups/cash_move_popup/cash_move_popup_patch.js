import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";
import { CashMoveReceipt } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_receipt/cash_move_receipt";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { formatDateTime } from "@web/core/l10n/dates";
import { parseFloat } from "@web/views/fields/parsers";
import { reasonsForMoveType } from "@pos_cash_denomination_control/app/utils/reasons";
import { translateCashMoveType } from "@pos_cash_denomination_control/app/utils/cash_move_type";
import { DenominationBreakdownPopup } from "@pos_cash_denomination_control/app/components/popups/denomination_breakdown_popup/denomination_breakdown_popup";

const { DateTime } = luxon;

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
    /**
     * A full override, not a thin wrapper around `super.confirm()`: core
     * computes `translatedType` in a local variable and reuses that same
     * variable for the employee log message, the `try_cash_in_out` extras
     * and the printed `CashMoveReceipt`. There is no seam to intercept a
     * local variable mid-method, so this mirrors core's
     * `point_of_sale/static/src/app/components/popups/cash_move_popup/cash_move_popup.js`
     * `confirm()` (Odoo 19) verbatim except for the `translatedType` line
     * below -- keep this in sync if that method changes upstream.
     */
    async confirm() {
        const amount = parseFloat(this.state.amount);
        const formattedAmount = this.env.utils.formatCurrency(amount);
        if (!amount) {
            this.notification.add(_t("Cash in/out of %s is ignored.", formattedAmount));
            return this.props.close();
        }

        const type = this.state.type;
        const translatedType = translateCashMoveType(type);
        const extras = { formattedAmount, translatedType };
        const reason = this.state.reason.trim();

        await this.pos.data.call(
            "pos.session",
            "try_cash_in_out",
            this._prepareTryCashInOutPayload(type, amount, reason, this.partnerId, extras),
            {},
            true
        );
        await this.pos.logEmployeeMessage(
            `${_t("Cash")} ${translatedType} - ${_t("Amount")}: ${formattedAmount}`,
            "CASH_DRAWER_ACTION"
        );
        const order = this.pos.models["pos.order"].create({
            session_id: this.pos.session,
            company_id: this.pos.company,
            config_id: this.pos.config,
            user_id: this.pos.user,
            ticket_code: "",
            tracking_number: "",
            sequence_number: 0,
            pos_reference: "",
            state: "cancel", // transient receipt-only order, must never reach IndexedDB
        });
        await this.printer.print(CashMoveReceipt, {
            reason,
            translatedType,
            order: order,
            formattedAmount,
            date: formatDateTime(DateTime.now()),
        });
        this.pos.models["pos.order"].delete(order);

        this.props.close();
        this.notification.add(
            _t("Successfully made a cash %s of %s.", type, formattedAmount),
            3000
        );
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
    /**
     * Bound method rather than an inline `t-on-change` arrow expression:
     * an inline `parseInt(...)` call in the compiled template expression
     * threw `TypeError: ... is not a function` at runtime against a real
     * `<select>` `change` event (found via Phase 13's E2E tour — the Hoot
     * unit tests never exercised this path, since they set
     * `popup.state.reasonId` directly instead of dispatching a DOM event).
     */
    onReasonChange(ev) {
        this.state.reasonId = ev.target.value ? parseInt(ev.target.value) : false;
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
