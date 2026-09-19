import { test, expect } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";

definePosModels();

const makeReason = (store, vals = {}) =>
    store.models["pos.cash.move.reason"].create({
        name: "Reason",
        direction: "out",
        is_vault: false,
        sequence: 10,
        company_id: false,
        ...vals,
    });

const mountCashMovePopup = async ({ store, props = {}, configure } = {}) => {
    const posStore = store ?? (await setupPosEnv());
    if (configure) {
        configure(posStore);
    }
    const popup = await mountWithCleanup(CashMovePopup, {
        props: { close: () => {}, ...props },
    });
    return { store: posStore, popup };
};

test("OUT popup preselects the POS default reason", async () => {
    let defaultReason;
    const { popup } = await mountCashMovePopup({
        configure: (store) => {
            defaultReason = makeReason(store, { name: "Vault" });
            store.config.default_cash_out_reason_id = defaultReason;
        },
    });
    expect(popup.state.reasonId).toBe(defaultReason.id);
});

test("IN popup has no preselection", async () => {
    const { popup } = await mountCashMovePopup({
        configure: (store) => {
            store.config.allow_cash_in = true;
            const defaultReason = makeReason(store, { name: "Vault" });
            store.config.default_cash_out_reason_id = defaultReason;
        },
    });
    popup.onClickButton("in");
    expect(popup.state.reasonId).toBe(false);
});

test("Selector filters reasons by direction", async () => {
    const { store, popup } = await mountCashMovePopup();
    const outReason = makeReason(store, { name: "Out", direction: "out" });
    const inReason = makeReason(store, { name: "In", direction: "in" });
    const bothReason = makeReason(store, { name: "Both", direction: "both" });

    const availableIds = popup.availableReasons.map((reason) => reason.id);

    expect(availableIds.includes(outReason.id)).toBe(true);
    expect(availableIds.includes(bothReason.id)).toBe(true);
    expect(availableIds.includes(inReason.id)).toBe(false);
});

test("Confirm is disabled until a reason is selected", async () => {
    const { popup } = await mountCashMovePopup();
    popup.state.amount = "10";
    popup.state.reasonId = false;
    await animationFrame();

    expect(".button.confirm").not.toBeEnabled();
});

test("Missing default reason yields no preselection", async () => {
    const { popup } = await mountCashMovePopup();
    expect(popup.state.reasonId).toBe(false);
});

test("_prepareTryCashInOutPayload merges reason_id and note into extras", async () => {
    const { store, popup } = await mountCashMovePopup();
    const reason = makeReason(store, { name: "Bank Deposit" });
    popup.state.reasonId = reason.id;
    popup.state.note = "till audit";

    const result = popup._prepareTryCashInOutPayload();
    const extras = result[result.length - 1];

    expect(extras.reason_id).toBe(reason.id);
    expect(extras.note).toBe("till audit");
});

test("A stock caller passing no props still mounts and defaults to out", async () => {
    const { popup } = await mountCashMovePopup();
    expect(popup.state.type).toBe("out");
});

test("initialReasonId prop preselects the given reason", async () => {
    const store = await setupPosEnv();
    const reason = makeReason(store, { name: "Preselected" });

    const { popup } = await mountCashMovePopup({
        store,
        props: { initialReasonId: reason.id },
    });

    expect(popup.state.reasonId).toBe(reason.id);
});

test("Archived default reason yields no preselection", async () => {
    // Hoot limitation (same one documented in reasons_loading.test.js): the
    // mocked PosSession.load_data() loads with a hardcoded empty domain, so
    // an archived reason can't be created here and then proven excluded
    // from the load the way pos.load.mixin's real domain excludes it
    // server-side. We simulate the resulting client state directly instead:
    // a default reason id that never resolved to a loaded record, exactly
    // what an archived default produces once the real domain excludes it.
    const { popup } = await mountCashMovePopup({
        configure: (store) => {
            store.config.default_cash_out_reason_id = false;
        },
    });
    expect(popup.state.reasonId).toBe(false);
});
