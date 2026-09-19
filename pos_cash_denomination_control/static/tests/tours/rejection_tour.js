/* global posmodel */
import { registry } from "@web/core/registry";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as DenomUtils from "@pos_cash_denomination_control/../tests/tours/utils/denomination_tour_utils";

/**
 * `pos-denomination-ui` / `cash-move-reasons` tour-level rejection UX
 * (design.md Testing Strategy Tours row "reason and denomination
 * rejection"). Two independent rejections, in one session:
 *
 * 1. Frontend: switching the cash-move popup to "in" clears the
 *    preselected reason (no default reason exists for "in"), so Confirm
 *    is disabled until a compatible reason is picked (Python setup
 *    creates one, "Petty cash top-up", direction "in").
 * 2. Server-side: a denomination is removed from the POS config's allowed
 *    bills *while the breakdown popup already holds a line for it*
 *    (simulating a config change that happened elsewhere, e.g. an
 *    offline-replay scenario per design.md ADR-7's "stale allowed-bill"
 *    case) — the server rejects the confirm and the rejection surfaces to
 *    the cashier as a dialog.
 *
 * **Empirically confirmed while writing this tour**: `pos.bill.pos_config_ids`
 * and `pos.config.default_bill_ids` are the *same* many2many relation
 * (neither field declares an explicit `relation`/`column1`/`column2`, and
 * there is only one many2many between the two models, so the ORM reuses one
 * junction table for both). Writing `pos_config_ids = [this config's id]`
 * on a bill therefore *adds* it to `default_bill_ids` — the opposite of
 * removing it — because both fields are two views of the one relation.
 * Excluding a bill from `pos.bill._load_pos_data_domain`'s `OR
 * pos_config_ids = False` branch (without touching `default_bill_ids`,
 * which must also not list it) requires pointing `pos_config_ids` at a
 * *different* config, so it needs one thrown away here (`pos_admin`, a POS
 * manager, has `pos.config` create rights the plain `pos_user` lacks).
 *
 * Stock `CashMovePopup.confirm()` never catches the RPC's rejection
 * itself, so the resulting `UserError` propagates as an unhandled
 * rejection that the framework's own global handler both shows as a
 * dialog *and* logs via `console.error`. `odoo.tests.common.browser_js`
 * fails a test on ANY `console.error`, unconditionally, regardless of a
 * passed `error_checker` (that only controls *when* it aborts early, not
 * *whether* the run is ultimately reported as failed). The same technique
 * `generic_helpers/offline_util.js` already uses for `ConnectionLostError`
 * noise — filtering one specific expected message out of `console.error`
 * for the duration of the risky step — is applied here for this
 * deliberately triggered, expected rejection.
 */
registry.category("web_tour.tours").add("pcdc_rejection_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ...Chrome.clickMenuOption("Cash In/Out"),
            {
                content: "Switch to Cash In",
                trigger: ".o_dialog button:contains('Cash In')",
                run: "click",
            },
            {
                content: "Confirm is disabled without a reason",
                trigger: ".o_dialog button.confirm[disabled]",
            },
            DenomUtils.selectCashMoveReason("Petty cash top-up"),
            {
                content: "Confirm is enabled once a compatible reason is picked",
                trigger: ".o_dialog button.confirm:not([disabled])",
            },
            {
                content: "Discard this cash-in attempt",
                trigger: ".o_dialog .button.cancel",
                run: "click",
            },
            ...Chrome.clickMenuOption("Cash In/Out"),
            ...DenomUtils.enterBreakdown(
                ".o_dialog .button.icon",
                "Cash movement breakdown",
                "20",
                "1"
            ),
            {
                content:
                    "Remove the allowed bill server-side (simulates a config " +
                    "change that happened elsewhere): create a throwaway other " +
                    "config, then re-point the bill's `pos_config_ids` to it so " +
                    "it is tied to a config other than this session's.",
                trigger: "body",
                run: async () => {
                    const otherConfigIds = await posmodel.data.orm.create("pos.config", [
                        { name: "PCDC Other (rejection tour throwaway)" },
                    ]);
                    const bill = posmodel.models["pos.bill"]
                        .getAll()
                        .find((b) => b.name === "20");
                    await posmodel.data.orm.write("pos.bill", [bill.id], {
                        pos_config_ids: [[6, 0, otherConfigIds]],
                    });
                },
            },
            {
                content: "Filter the expected rejection out of console.error",
                trigger: "body",
                run: () => {
                    const originalConsoleError = console.error;
                    window.__pcdcOriginalConsoleError = originalConsoleError;
                    console.error = (...args) => {
                        const message = args[0] instanceof Error ? args[0].message : args[0];
                        if (typeof message === "string" && message.includes("RPC_ERROR")) {
                            console.info("PCDC: expected rejection filtered:", ...args);
                        } else {
                            originalConsoleError.apply(console, args);
                        }
                    };
                },
            },
            {
                content: "Confirm the now-stale cash-out",
                trigger: ".o_dialog .modal-footer .button.confirm",
                run: "click",
            },
            Dialog.bodyIs("not allowed"),
            Dialog.confirm(),
            {
                content: "Restore console.error",
                trigger: "body",
                run: () => {
                    console.error = window.__pcdcOriginalConsoleError;
                    delete window.__pcdcOriginalConsoleError;
                },
            },
        ].flat(),
});
