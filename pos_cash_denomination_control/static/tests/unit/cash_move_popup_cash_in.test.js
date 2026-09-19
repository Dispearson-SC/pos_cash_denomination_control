import { test, expect } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";

definePosModels();

const mountCashMovePopup = async (allowCashIn) => {
    const store = await setupPosEnv();
    store.config.allow_cash_in = allowCashIn;
    const popup = await mountWithCleanup(CashMovePopup, {
        props: { close: () => {} },
    });
    return { store, popup };
};

test("POS receives cash-in flag", async () => {
    const store = await setupPosEnv();
    store.config.allow_cash_in = true;
    expect(store.config.allow_cash_in).toBe(true);
});

test("Popup hides Cash In when disabled", async () => {
    const { popup } = await mountCashMovePopup(false);
    expect(".input-type").toHaveCount(1);
    expect(".input-type").toHaveText("Cash Out");
    expect(popup.state.type).toBe("out");
});

test("Popup type cannot be switched to in when disabled", async () => {
    const { popup } = await mountCashMovePopup(false);
    popup.onClickButton("in");
    expect(popup.state.type).toBe("out");
});

test("Popup shows both options when enabled", async () => {
    await mountCashMovePopup(true);
    expect(".input-type").toHaveCount(2);
});
