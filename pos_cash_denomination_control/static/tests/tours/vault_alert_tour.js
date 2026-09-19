import { registry } from "@web/core/registry";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { negate } from "@point_of_sale/../tests/generic_helpers/utils";

/**
 * `vault-withdrawal-alert` spec, tour-level scenarios: "State refreshes
 * after order sync", "State refreshes after cash move", "Indicator is
 * cleared after cash-out brings expected cash below threshold", "Sale
 * completes normally while the alert is active", and the one-click
 * cash-out flow.
 *
 * Python setup: opening amount 100, threshold 150 (not required at
 * first), a single product priced 80 (Cash payment brings expected cash to
 * 180, over threshold).
 */
registry.category("web_tour.tours").add("pcdc_vault_alert_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            {
                content: "Set the opening amount to 100",
                trigger: ".cash-input-sub-section input",
                run: "edit 100",
            },
            Dialog.confirm("Open Register"),
            {
                content: "The vault alert indicator is not shown yet",
                trigger: negate(".vault-alert-indicator"),
            },
            ProductScreen.clickDisplayedProduct("PCDC Vault Product", true, "1", "80.0"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.remainingIs("0.0"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            {
                content: "The vault alert indicator appears after the order syncs",
                trigger: ".vault-alert-indicator",
            },
            ReceiptScreen.clickNextOrder(),
            ProductScreen.isShown(),
            {
                content: "The alert does not block a normal sale",
                trigger: ".vault-alert-indicator",
            },
            ProductScreen.clickDisplayedProduct("PCDC Vault Product", true, "1", "80.0"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank", true, { remaining: "0.0" }),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            ReceiptScreen.clickNextOrder(),
            ProductScreen.isShown(),
            {
                content: "One-click vault cash-out: click the indicator",
                trigger: ".vault-alert-indicator",
                run: "click",
            },
            {
                content: "The cash-move popup opens in 'out' mode with the vault reason preselected",
                trigger: ".o_dialog button.red-highlight:contains('Cash Out')",
            },
            {
                content: "The vault reason is preselected",
                trigger: ".o_dialog select.pcdc-reason-select",
                run: () => {
                    const select = document.querySelector(".o_dialog select.pcdc-reason-select");
                    const selectedText = select.selectedOptions[0]?.textContent.trim();
                    if (selectedText !== "Vault") {
                        throw new Error(
                            `Expected the "Vault" reason to be preselected, got "${selectedText}"`
                        );
                    }
                },
            },
            {
                content: "Enter the cash-out amount",
                trigger: ".o_dialog .input-amount input.o_input",
                run: "edit 40",
            },
            {
                content: "Confirm the one-click vault cash-out",
                trigger: ".o_dialog .modal-footer .button.confirm",
                run: "click",
            },
            {
                content: "The vault alert indicator is cleared",
                trigger: negate(".vault-alert-indicator"),
            },
        ].flat(),
});
