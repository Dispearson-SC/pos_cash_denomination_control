import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { PosSession } from "@point_of_sale/../tests/unit/data/pos_session.data";
import { PosCashMoveReason } from "./pos_cash_move_reason.data";

patch(hootPosModels, [...hootPosModels, PosCashMoveReason]);

patch(PosSession.prototype, {
    _load_pos_data_models() {
        return [...super._load_pos_data_models(), "pos.cash.move.reason"];
    },
});
