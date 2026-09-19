/* global posmodel */
import { registry } from "@web/core/registry";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Offline from "@point_of_sale/../tests/generic_helpers/offline_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";

/**
 * NOT a spec scenario. This confirms/refutes design.md's Discovery table
 * claim (`Offline queue` row) that `PosData`'s offline replay queue
 * (`network.unsyncData`) is held only in memory (`reactive({...
 * unsyncData: []})`, `data_service.js:38-42`), with no persistence layer,
 * so a queued-but-unsynced operation is lost on a page reload while still
 * offline — an assumption the design used but never verified end-to-end.
 *
 * A cash-out is confirmed while offline (queued, per stock `PosData.call`
 * with `queue=true`), then the page reloads while offline mode persists
 * (`Offline.setOfflineMode`'s `sessionStorage` flag survives reload). If
 * the assumption is correct, `posmodel.data.network.unsyncData` goes from
 * a positive count back to 0 across the reload, and no statement line was
 * ever created server-side for it. **Empirically confirmed while writing
 * this tour**: a single cash-out confirm queues *two* calls while offline
 * (`try_cash_in_out` and the receipt's `logEmployeeMessage`), not one, so
 * this only asserts "at least one" rather than an exact count.
 */
registry.category("web_tour.tours").add("pcdc_offline_queue_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            Offline.setOfflineMode(),
            ...Chrome.clickMenuOption("Cash In/Out"),
            {
                content: "Enter the cash-out amount",
                trigger: ".input-amount input.o_input",
                run: "edit 5",
            },
            {
                content: "Confirm while offline (queues the RPC instead of failing)",
                trigger: ".o_dialog .modal-footer .button.confirm",
                run: "click",
            },
            {
                content: "The cash move is queued in memory",
                trigger: "body",
                run: () => {
                    const count = posmodel.data.network.unsyncData.length;
                    if (count < 1) {
                        throw new Error(`Expected at least 1 queued item, got ${count}`);
                    }
                },
            },
            refresh(),
            {
                content:
                    "After reloading while still offline, the in-memory queue is " +
                    "empty (confirms it is memory-only, not persisted)",
                trigger: "body",
                run: () => {
                    const count = posmodel.data.network.unsyncData.length;
                    if (count !== 0) {
                        throw new Error(
                            `Expected the queue to be lost on reload, got ${count} item(s)`
                        );
                    }
                },
            },
            Offline.setOnlineMode(),
        ].flat(),
});
