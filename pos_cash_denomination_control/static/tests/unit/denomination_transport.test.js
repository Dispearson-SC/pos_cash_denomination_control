import { test, expect } from "@odoo/hoot";
import { mountWithCleanup, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { OpeningControlPopup } from "@point_of_sale/app/components/popups/opening_control_popup/opening_control_popup";
import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";
import { translateCashMoveType } from "@pos_cash_denomination_control/app/utils/cash_move_type";

definePosModels();

// Covers spec `pos-denomination-ui` (Requirement: Breakdown Is Transported
// To The Server). `store.data.execute` is intercepted right before the ORM
// round-trip, so the assertions observe the kwargs exactly as
// `PosData.call`'s ADR-5 staging merge produced them, without a real RPC.

const BREAKDOWN_LINES = [{ bill_id: 6, quantity: 2 }];

test("Opening RPC includes the denomination_lines kwarg", async () => {
    const store = await setupPosEnv();
    store.config.cash_count_opening_required = true;
    const popup = await mountWithCleanup(OpeningControlPopup, { props: { close: () => {} } });
    popup.pcdcBreakdownLines = BREAKDOWN_LINES;

    let captured;
    patchWithCleanup(store.data, {
        async execute(params) {
            if (params.model === "pos.session" && params.method === "set_opening_control") {
                captured = params.kwargs;
                return undefined;
            }
            return super.execute(params);
        },
    });

    await popup.confirm();

    expect(captured.denomination_lines).toEqual(BREAKDOWN_LINES);
});

test("Cash move RPC includes denomination_lines in extras", async () => {
    const store = await setupPosEnv();
    store.config.cash_count_out_required = true;
    const popup = await mountWithCleanup(CashMovePopup, { props: { close: () => {} } });
    popup.pcdcBreakdownLines = BREAKDOWN_LINES;

    const result = popup._prepareTryCashInOutPayload(
        "out",
        20,
        "",
        store.user.partner_id.id,
        { formattedAmount: "$ 20.00", translatedType: translateCashMoveType("out") }
    );
    const extras = result[result.length - 1];

    expect(extras.denomination_lines).toEqual(BREAKDOWN_LINES);
});

test("Closing RPC includes the denomination_lines kwarg", async () => {
    const store = await setupPosEnv();
    store.config.cash_count_closing_required = true;
    const popup = await mountWithCleanup(ClosePosPopup, {
        props: {
            orders_details: { quantity: 0, amount: 0 },
            opening_notes: "",
            default_cash_details: {
                id: 1,
                name: "Cash",
                amount: 100,
                opening: 100,
                payment_amount: 0,
                moves: [],
            },
            non_cash_payment_methods: [],
            is_manager: true,
            amount_authorized_diff: null,
            close: () => {},
        },
    });
    popup.pcdcBreakdownLines = BREAKDOWN_LINES;

    let captured;
    patchWithCleanup(store.data, {
        async execute(params) {
            if (params.model === "pos.session" && params.method === "post_closing_cash_details") {
                captured = params.kwargs;
                // Stop right after the interesting call: a "successful:
                // false" response short-circuits `closeSession()` before it
                // reaches `update_closing_control_state_session` /
                // `close_session_from_ui`, which this test does not need.
                return { successful: false, message: "test-stop" };
            }
            return super.execute(params);
        },
    });

    await popup.closeSession();

    expect(captured.denomination_lines).toEqual(BREAKDOWN_LINES);
});

// Covers design.md ADR-5's `try/finally` clearing invariant (Phase 12
// REFACTOR task): a staged kwarg must never survive a failed RPC, or it
// could leak into a later, unrelated `(model, method)` call.

test("Staged opening kwargs clear even when confirm() throws", async () => {
    const store = await setupPosEnv();
    store.config.cash_count_opening_required = true;
    const popup = await mountWithCleanup(OpeningControlPopup, { props: { close: () => {} } });
    popup.pcdcBreakdownLines = BREAKDOWN_LINES;
    patchWithCleanup(store.data, {
        async execute(params) {
            if (params.model === "pos.session" && params.method === "set_opening_control") {
                throw new Error("forced failure");
            }
            return super.execute(params);
        },
    });

    let threw = false;
    try {
        await popup.confirm();
    } catch {
        threw = true;
    }

    expect(threw).toBe(true);
    expect(store.data._pcdcStagedKwargs).toBe(null);
});

test("Staged closing kwargs clear even when closeSession() throws", async () => {
    const store = await setupPosEnv();
    store.config.cash_count_closing_required = true;
    const popup = await mountWithCleanup(ClosePosPopup, {
        props: {
            orders_details: { quantity: 0, amount: 0 },
            opening_notes: "",
            default_cash_details: {
                id: 1,
                name: "Cash",
                amount: 100,
                opening: 100,
                payment_amount: 0,
                moves: [],
            },
            non_cash_payment_methods: [],
            is_manager: true,
            amount_authorized_diff: null,
            close: () => {},
        },
    });
    popup.pcdcBreakdownLines = BREAKDOWN_LINES;
    patchWithCleanup(store.data, {
        async execute(params) {
            if (params.model === "pos.session" && params.method === "post_closing_cash_details") {
                throw new Error("forced failure");
            }
            return super.execute(params);
        },
    });

    let threw = false;
    try {
        await popup.closeSession();
    } catch {
        threw = true;
    }

    expect(threw).toBe(true);
    expect(store.data._pcdcStagedKwargs).toBe(null);
});
