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

    // Order follows `this.bills` iteration order, which is descending by
    // value (Phase 12's own "sorted descending" task), so the 10.00 bill
    // comes first.
    expect(payload.lines).toEqual([
        { bill_id: TEN_BILL_ID, quantity: 1 },
        { bill_id: ONE_BILL_ID, quantity: 2 },
    ]);
});

test("Popup computes a total matching the domain rule", async () => {
    const { popup } = await mountBreakdownPopup();
    popup.state[ONE_BILL_ID] = 3; // 3 x 1.00
    popup.state[TEN_BILL_ID] = 2; // 2 x 10.00

    expect(popup.total).toBe(23);
});

test("Bills are sorted descending by value (cashier consistency with stock MoneyDetailsPopup)", async () => {
    const { popup } = await mountBreakdownPopup();

    const values = popup.bills.map((bill) => bill.value);

    expect(values).toEqual([...values].sort((a, b) => b - a));
    // Sanity check: the demo bills are not already sorted descending by id,
    // so this assertion cannot pass by accident of insertion order.
    expect(values[0]).toBeGreaterThan(values[values.length - 1]);
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
