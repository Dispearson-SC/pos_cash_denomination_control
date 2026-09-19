import { registry } from "@web/core/registry";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import { negate } from "@point_of_sale/../tests/generic_helpers/utils";

/**
 * `cash-in-control` spec, tour-level proof (design.md Testing Strategy
 * Tours row "cash-in disabled"): with `allow_cash_in=False` the "Cash In"
 * button is absent from the cash-move popup and it opens in "out" mode.
 */
registry.category("web_tour.tours").add("pcdc_cash_in_disabled_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ...Chrome.clickMenuOption("Cash In/Out"),
            {
                content: "No 'Cash In' button is shown",
                trigger: negate("button:contains('Cash In')"),
            },
            {
                content: "The popup is in 'out' mode",
                trigger: ".o_dialog button.red-highlight:contains('Cash Out')",
            },
            {
                content: "Discard the popup",
                trigger: ".o_dialog .button.cancel",
                run: "click",
            },
        ].flat(),
});
