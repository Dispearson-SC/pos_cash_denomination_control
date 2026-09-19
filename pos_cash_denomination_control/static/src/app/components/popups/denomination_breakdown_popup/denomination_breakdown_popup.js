import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { NumericInput } from "@point_of_sale/app/components/inputs/numeric_input/numeric_input";
import { useService } from "@web/core/utils/hooks";
import {
    buildBreakdownNoteText,
    buildBreakdownPayload,
    computeBreakdownTotal,
} from "@pos_cash_denomination_control/app/utils/breakdown";

/**
 * Denomination breakdown popup (`pos-denomination-ui` spec, design.md
 * ADR-2). Unlike the stock `MoneyDetailsPopup`, state is keyed by
 * `pos.bill.id`, never by float value, so bills sharing the same value are
 * never conflated. Only non-negative integer quantities are accepted, and
 * Confirm is disabled otherwise.
 */
export class DenominationBreakdownPopup extends Component {
    static template = "pos_cash_denomination_control.DenominationBreakdownPopup";
    static components = { NumericInput, Dialog };
    static props = {
        title: String,
        initialLines: { type: Array, optional: true },
        getPayload: Function,
        close: Function,
    };
    static defaultProps = {
        initialLines: [],
    };

    setup() {
        this.pos = usePos();
        this.ui = useService("ui");
        // The same set the server allows at load time, sorted descending by
        // value — matching stock `MoneyDetailsPopup`'s own order
        // (`money_details_popup.js:5`, `sort((a, b) => b - a)`) for cashier
        // consistency between the two popups.
        this.bills = [...this.pos.models["pos.bill"].getAll()].sort(
            (a, b) => b.value - a.value
        );
        const initialQuantities = Object.fromEntries(
            this.props.initialLines.map((line) => [line.bill_id, line.quantity])
        );
        this.state = useState(
            Object.fromEntries(
                this.bills.map((bill) => [bill.id, initialQuantities[bill.id] ?? 0])
            )
        );
    }

    get total() {
        return computeBreakdownTotal(this.bills, this.state);
    }

    /** Only non-negative integer quantities are accepted for every bill. */
    get isValid() {
        return this.bills.every((bill) => {
            const quantity = this.state[bill.id];
            return Number.isInteger(quantity) && quantity >= 0;
        });
    }

    confirm() {
        if (!this.isValid) {
            return;
        }
        this.props.getPayload({
            total: this.total,
            lines: buildBreakdownPayload(this.bills, this.state),
            notesText: buildBreakdownNoteText(this.props.title, this.bills, this.state, (value) =>
                this.env.utils.formatCurrency(value)
            ),
        });
        this.props.close();
    }
}
