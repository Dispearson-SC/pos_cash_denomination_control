import { registry } from "@web/core/registry";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as DenomUtils from "@pos_cash_denomination_control/../tests/tours/utils/denomination_tour_utils";

/**
 * `pos-denomination-ui` spec, Scenario: "Opening tour with a breakdown
 * succeeds". The opening toggle is on; entering 2 units of the "20" bill
 * (Python setup creates it) must produce the opening balance the test
 * asserts against.
 */
registry.category("web_tour.tours").add("pcdc_opening_breakdown_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            ...DenomUtils.enterBreakdown(
                ".opening-cash-section .button.icon",
                "Cash control - opening",
                "20",
                "2"
            ),
            Dialog.confirm("Open Register"),
        ].flat(),
});
