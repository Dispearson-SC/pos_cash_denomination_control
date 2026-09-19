import { registry } from "@web/core/registry";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as DenomUtils from "@pos_cash_denomination_control/../tests/tours/utils/denomination_tour_utils";

/**
 * `pos-denomination-ui` spec, Scenario: "Cash-out tour with reason and
 * breakdown succeeds". The cash-OUT toggle is on; the tour explicitly
 * selects a non-default reason (Python setup creates "Bank Deposit",
 * direction "out"), enters a breakdown for the single allowed bill, and
 * confirms. The Python test asserts the resulting statement line carries
 * both the reason and the amount.
 */
registry.category("web_tour.tours").add("pcdc_cash_out_reason_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ...Chrome.clickMenuOption("Cash In/Out"),
            DenomUtils.selectCashMoveReason("Bank Deposit"),
            ...DenomUtils.enterBreakdown(
                ".o_dialog .button.icon",
                "Cash movement breakdown",
                "20",
                "1"
            ),
            {
                content: "Confirm the cash-out",
                trigger: ".o_dialog .modal-footer .button.confirm",
                run: "click",
            },
        ].flat(),
});
