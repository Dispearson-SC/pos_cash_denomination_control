import { test, expect } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { DenominationBreakdownPopup } from "@pos_cash_denomination_control/app/components/popups/denomination_breakdown_popup/denomination_breakdown_popup";

definePosModels();

// Stock demo bills (`pos_bill.data.js`): id 6 -> value 1.00, id 9 -> value 10.00.
const ONE_BILL_ID = 6;
const TEN_BILL_ID = 9;

const mountBreakdownPopup = async ({ props = {} } = {}) => {
    const store = await setupPosEnv();
    const popup = await mountWithCleanup(DenominationBreakdownPopup, {
        props: { title: "Opening", getPayload: () => {}, close: () => {}, ...props },
    });
    return { store, popup };
};

test("Popup confirm returns an id-keyed array", async () => {
    let payload;
    const { popup } = await mountBreakdownPopup({
        props: { getPayload: (result) => (payload = result) },
    });
    popup.state[ONE_BILL_ID] = 2;
    popup.state[TEN_BILL_ID] = 1;

    popup.confirm();

    expect(payload.lines).toEqual([
        { bill_id: ONE_BILL_ID, quantity: 2 },
        { bill_id: TEN_BILL_ID, quantity: 1 },
    ]);
});

test("Popup computes a total matching the domain rule", async () => {
    const { popup } = await mountBreakdownPopup();
    popup.state[ONE_BILL_ID] = 3; // 3 x 1.00
    popup.state[TEN_BILL_ID] = 2; // 2 x 10.00

    expect(popup.total).toBe(23);
});

test("Note text is generated from the entered breakdown", async () => {
    let payload;
    const { popup } = await mountBreakdownPopup({
        props: { getPayload: (result) => (payload = result) },
    });
    popup.state[ONE_BILL_ID] = 4;

    popup.confirm();

    expect(payload.notesText).toMatch("4");
    expect(payload.notesText).toMatch("Opening details");
});
