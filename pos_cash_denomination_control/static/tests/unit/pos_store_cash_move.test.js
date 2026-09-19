import { test, expect } from "@odoo/hoot";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";

definePosModels();

const stubDialogAdd = (store) => {
    let captured;
    patchWithCleanup(store.dialog, {
        add(component, props, options) {
            captured = { component, props };
            options?.onClose?.();
            return () => {};
        },
    });
    return () => captured;
};

test("cashMove with no options delegates to the stock popup with no extra props", async () => {
    const store = await setupPosEnv();
    const getCaptured = stubDialogAdd(store);

    await store.cashMove();

    const { component, props } = getCaptured();
    expect(component).toBe(CashMovePopup);
    expect(props.initialType).toBe(undefined);
    expect(props.initialReasonId).toBe(undefined);
});

test("cashMove with options opens the popup preconfigured", async () => {
    const store = await setupPosEnv();
    const getCaptured = stubDialogAdd(store);

    await store.cashMove({ initialType: "out", initialReasonId: 7 });

    const { component, props } = getCaptured();
    expect(component).toBe(CashMovePopup);
    expect(props.initialType).toBe("out");
    expect(props.initialReasonId).toBe(7);
});
