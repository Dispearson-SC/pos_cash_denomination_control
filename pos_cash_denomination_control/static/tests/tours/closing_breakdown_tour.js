import { registry } from "@web/core/registry";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as DenomUtils from "@pos_cash_denomination_control/../tests/tours/utils/denomination_tour_utils";

/**
 * `pos-denomination-ui` spec, Scenario: "Closing tour with a breakdown
 * succeeds" + `closing-manager-override` spec, Scenario: "Non-manager
 * closing with a recorded breakdown succeeds (tour)". The closing toggle
 * is on (opening is not, so the tour sets the opening amount directly);
 * the tour logs in as the plain `pos_user` (never a manager, per
 * `start_pos_tour`'s default `login`), sets the opening amount to match
 * the closing breakdown it will enter (no orders in between), and closes
 * the register. A matching count means no payment difference, so
 * `ClosePosPopup.confirm()` closes immediately with no extra confirmation
 * dialog.
 */
registry.category("web_tour.tours").add("pcdc_closing_breakdown_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            {
                content: "Set the opening amount to match the closing breakdown",
                trigger: ".cash-input-sub-section input",
                run: "edit 20",
            },
            Dialog.confirm("Open Register"),
            ...Chrome.clickMenuOption("Close Register"),
            ...DenomUtils.enterBreakdown(
                "button.fa-money",
                "Cash control - closing",
                "20",
                "1"
            ),
            {
                content: "Close the register",
                trigger: ".o_dialog .modal-footer button:contains('Close Register')",
                run: "click",
                expectUnloadPage: true,
            },
        ].flat(),
});
