import { test, expect } from "@odoo/hoot";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

// Covers spec `cash-denomination-config` (Requirement: Toggles Delivered To
// POS Frontend). Per design.md's confirmed spike (also used for
// `allow_cash_in` and `vault_withdrawal_threshold`), a mocked `pos.config`
// record accepts any field assignment with no schema check, so this is
// deliberately the same "trivially green" pattern already documented for
// `vault_alert.test.js`'s "Threshold delivered to POS frontend" (Phase 7):
// it proves the frontend reads whatever `this.pos.config` carries, not that
// the server actually delivers these specific fields (that guarantee comes
// from `pos.config` being an unrestricted stored field with no
// `_load_pos_data_fields` override, same as `allow_cash_in`).
test("POS load includes current toggle values", async () => {
    const store = await setupPosEnv();
    store.config.cash_count_opening_required = false;
    store.config.cash_count_out_required = true;
    store.config.cash_count_in_required = false;
    store.config.cash_count_closing_required = false;

    expect(store.config.cash_count_opening_required).toBe(false);
    expect(store.config.cash_count_out_required).toBe(true);
    expect(store.config.cash_count_in_required).toBe(false);
    expect(store.config.cash_count_closing_required).toBe(false);
});

test("Toggle change is reflected on next load", async () => {
    const store = await setupPosEnv();
    store.config.cash_count_closing_required = false;
    expect(store.config.cash_count_closing_required).toBe(false);

    store.config.cash_count_closing_required = true;
    expect(store.config.cash_count_closing_required).toBe(true);
});
