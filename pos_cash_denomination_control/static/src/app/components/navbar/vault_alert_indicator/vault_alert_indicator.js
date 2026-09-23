import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { firstActiveVaultReason } from "@pos_cash_denomination_control/app/utils/reasons";

/**
 * Persistent navbar indicator for the `vault-withdrawal-alert` spec. Shown
 * only while `pos.vaultAlert.required` is true (set by
 * `PosStore.refreshVaultState`, `services/pos_store_patch.js`). Clicking it
 * opens the cash move popup in "out" mode with a vault reason preselected
 * ("One-Click Vault Cash-Out" requirement), unless the acting user lacks
 * the stock cash-move permission.
 */
export class VaultAlertIndicator extends Component {
    static template = "pos_cash_denomination_control.VaultAlertIndicator";
    static props = {};

    setup() {
        this.pos = usePos();
        this.notification = useService("notification");
    }

    get vaultAlert() {
        return this.pos.vaultAlert;
    }

    async onClick() {
        if (!this.pos.showCashMoveButton) {
            this.notification.add(_t("You don't have permission to record cash movements."), {
                type: "warning",
            });
            return;
        }
        await this.pos.cashMove({
            initialType: "out",
            initialReasonId: this.preselectedVaultReasonId(),
        });
    }

    /**
     * Instance convenience: delegates to the static resolution rule below
     * using this component's own `pos`.
     */
    preselectedVaultReasonId() {
        return VaultAlertIndicator.preselectedVaultReasonId(this.pos);
    }

    /**
     * Priority: the POS default cash-out reason when it is itself a vault
     * reason, otherwise the first active vault reason by sequence,
     * otherwise no preselection (`false`). Shares `firstActiveVaultReason`
     * with `CashMovePopup`'s own default-reason resolution (Phase 5) so
     * both consumers agree on the same rule.
     *
     * Static (spec `vault-withdrawal-blocking`, T3) so
     * `payment_screen_patch.js`'s blocked-sale dialog can reuse this exact
     * resolution rule without instantiating this component or duplicating
     * the logic.
     */
    static preselectedVaultReasonId(pos) {
        const defaultReason = pos.config.default_cash_out_reason_id;
        if (defaultReason && defaultReason.is_vault) {
            return defaultReason.id;
        }
        const vaultReason = firstActiveVaultReason(pos.models["pos.cash.move.reason"].getAll());
        return vaultReason ? vaultReason.id : false;
    }
}
