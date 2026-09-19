import { test, expect } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { OpeningControlPopup } from "@point_of_sale/app/components/popups/opening_control_popup/opening_control_popup";
import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";

definePosModels();

// Covers spec `pos-denomination-ui` (Requirement: Read-Only Amount Input
// When The Applicable Denomination Toggle Is On). The default Hoot demo
// `pos.config` already has `cash_control: true` and a "Cash" payment method
// (`pos_config.data.js`, `pos_payment_method.data.js`), so only the
// denomination toggle itself needs to be set per scenario.

const defaultCashDetails = () => ({
    id: 1,
    name: "Cash",
    amount: 100,
    opening: 100,
    payment_amount: 0,
    moves: [],
});

const mountClosePosPopup = async (props = {}) =>
    mountWithCleanup(ClosePosPopup, {
        props: {
            orders_details: { quantity: 0, amount: 0 },
            opening_notes: "",
            default_cash_details: defaultCashDetails(),
            non_cash_payment_methods: [],
            is_manager: true,
            amount_authorized_diff: null,
            close: () => {},
            ...props,
        },
    });

test("Opening amount field is read-only when the opening toggle is on", async () => {
    const store = await setupPosEnv();
    store.config.cash_count_opening_required = true;

    await mountWithCleanup(OpeningControlPopup, { props: { close: () => {} } });

    expect(".opening-cash-section input").toHaveAttribute("readonly");
});

test("Cash move amount field is read-only when the applicable toggle is on", async () => {
    const store = await setupPosEnv();
    store.config.cash_count_out_required = true;

    await mountWithCleanup(CashMovePopup, { props: { close: () => {} } });

    expect(".input-amount input").toHaveAttribute("readonly");
});

test("Closing cash amount field is read-only when the closing toggle is on", async () => {
    const store = await setupPosEnv();
    store.config.cash_count_closing_required = true;

    await mountClosePosPopup();

    expect(".cash-input input").toHaveAttribute("readonly");
});

test("Amount field is editable when the toggle is off", async () => {
    const store = await setupPosEnv();
    store.config.cash_count_opening_required = false;

    await mountWithCleanup(OpeningControlPopup, { props: { close: () => {} } });

    expect(".opening-cash-section input").not.toHaveAttribute("readonly");
});
