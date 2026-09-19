import { test, expect } from "@odoo/hoot";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

test("POS receives active reasons matching its company", async () => {
    const store = await setupPosEnv();
    const reasons = store.models["pos.cash.move.reason"].getAll();
    const names = reasons.map((reason) => reason.name).sort();

    // Company-scoped and shared (company-less) reasons both load. Real
    // per-company exclusion (a reason of a *different* company never
    // loading) is proven server-side by the multi-company record rule
    // (tests/test_reasons.py::test_multi_company_record_rule_hides_other_company_reasons)
    // and by _load_pos_data_domain itself: the mocked PosSession.load_data()
    // in this addon's Hoot harness calls search_read([], ...) with no
    // domain, so it cannot exercise per-model domain filtering the way the
    // real backend's pos.load.mixin does.
    expect(names).toEqual(["Company Reason", "Shared Reason"]);
    const companyReason = reasons.find((reason) => reason.name === "Company Reason");
    expect(companyReason.direction).toBe("out");
    expect(companyReason.is_vault).toBe(false);
});
