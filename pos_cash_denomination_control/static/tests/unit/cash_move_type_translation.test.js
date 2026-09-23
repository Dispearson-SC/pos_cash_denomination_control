import { test, expect } from "@odoo/hoot";
import { mountWithCleanup, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";

definePosModels();

// Covers the untranslated cash-move type reported live: core's
// `cash_move_popup.js` computes `const translatedType = _t(this.state.type)`
// on a runtime variable ("in"/"out"), which Odoo's extractor never sees, so
// neither `point_of_sale`'s nor this addon's catalogue ever gained a real
// `msgid` for it. A cash-out showed the raw `"out"`; a cash-in showed `"en"`
// (the Spanish preposition, harvested from an unrelated literal). This addon
// now computes its own extractable literal and must flow it to all three
// consumers core uses it for: the employee log message, the
// `try_cash_in_out` extras, and the printed `CashMoveReceipt`.
// See odd/tasks/spanish-translations.md T3.

const mountCashMovePopup = async () => {
    const store = await setupPosEnv();
    const popup = await mountWithCleanup(CashMovePopup, {
        props: { close: () => {} },
    });
    return { store, popup };
};

test("Cash-out confirm sends an explicit 'Cash Out' literal, not the raw type", async () => {
    const { store, popup } = await mountCashMovePopup();
    popup.state.type = "out";
    popup.state.amount = "20";
    popup.state.reason = "test reason";

    let tryCashInOutExtras;
    patchWithCleanup(store.data, {
        async execute(params) {
            if (params.model === "pos.session" && params.method === "try_cash_in_out") {
                tryCashInOutExtras = params.args[params.args.length - 1];
                return undefined;
            }
            return super.execute(params);
        },
    });

    let loggedAction;
    patchWithCleanup(popup.pos, {
        async logEmployeeMessage(action) {
            loggedAction = action;
        },
    });

    let printedProps;
    patchWithCleanup(popup.printer, {
        async print(component, props) {
            printedProps = props;
            return true;
        },
    });

    await popup.confirm();

    expect(tryCashInOutExtras.translatedType).toBe("Cash Out");
    expect(loggedAction).toInclude("Cash Out");
    expect(loggedAction).not.toInclude("out - ");
    expect(printedProps.translatedType).toBe("Cash Out");
});

test("Cash-in confirm sends an explicit 'Cash In' literal, never the raw preposition", async () => {
    const { store, popup } = await mountCashMovePopup();
    store.config.allow_cash_in = true;
    popup.state.type = "in";
    popup.state.amount = "20";
    popup.state.reason = "test reason";

    let tryCashInOutExtras;
    patchWithCleanup(store.data, {
        async execute(params) {
            if (params.model === "pos.session" && params.method === "try_cash_in_out") {
                tryCashInOutExtras = params.args[params.args.length - 1];
                return undefined;
            }
            return super.execute(params);
        },
    });

    let printedProps;
    patchWithCleanup(popup.printer, {
        async print(component, props) {
            printedProps = props;
            return true;
        },
    });

    await popup.confirm();

    expect(tryCashInOutExtras.translatedType).toBe("Cash In");
    expect(printedProps.translatedType).toBe("Cash In");
});
