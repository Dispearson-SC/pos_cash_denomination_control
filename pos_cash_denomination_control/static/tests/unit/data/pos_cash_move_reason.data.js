import { models } from "@web/../tests/web_test_helpers";

export class PosCashMoveReason extends models.ServerModel {
    _name = "pos.cash.move.reason";

    _load_pos_data_fields() {
        return ["id", "name", "direction", "is_vault", "sequence", "company_id"];
    }

    _records = [
        {
            id: 1,
            name: "Company Reason",
            direction: "out",
            is_vault: false,
            sequence: 10,
            company_id: 1,
        },
        {
            id: 2,
            name: "Shared Reason",
            direction: "both",
            is_vault: false,
            sequence: 20,
            company_id: false,
        },
    ];
}
