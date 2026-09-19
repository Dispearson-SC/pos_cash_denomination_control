import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { reactive } from "@odoo/owl";
import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        // `vault-withdrawal-alert` spec: reactive state consumed by the
        // navbar indicator (Phase 7). `known` distinguishes "never refreshed
        // yet" from "refreshed and not required", so the very first refresh
        // that already reports `required` still triggers a notification
        // (the "on load when already required" scenario).
        this.vaultAlert = reactive({
            required: false,
            expected: 0,
            threshold: 0,
            known: false,
        });
        this._vaultRefreshPromise = null;
        this._vaultRefreshQueued = false;
    },

    async afterProcessServerData() {
        await super.afterProcessServerData(...arguments);
        await this.refreshVaultState();
    },

    async syncAllOrders(options = {}) {
        const result = await super.syncAllOrders(options);
        if (Array.isArray(result) && result.length > 0) {
            this.refreshVaultState();
        }
        return result;
    },

    /**
     * Opens the cash move popup. With no options, this behaves exactly like
     * the stock method. With `{initialType, initialReasonId}`, it forwards
     * them as props so a caller (the vault withdrawal alert's one-click
     * cash-out, Phase 7) can open the popup preconfigured. Either way, a
     * completed cash move refreshes the vault withdrawal state.
     */
    async cashMove(options = {}) {
        let result;
        if (Object.keys(options).length === 0) {
            result = await super.cashMove();
        } else {
            this.openCashbox(_t("Cash in / out"));
            result = await makeAwaitable(this.dialog, CashMovePopup, options);
        }
        await this.refreshVaultState();
        return result;
    },

    /**
     * Refreshes the vault withdrawal state from the server. A no-op while
     * offline or when the threshold is disabled (not a positive number —
     * this also covers a config record that never delivered the field at
     * all, which keeps this a no-op for any Hoot test that does not care
     * about the vault alert). At most one call runs at a time; a further
     * request while one is in flight is coalesced into a single trailing
     * call (`vault-withdrawal-alert` spec, "POS Refresh Triggers").
     */
    async refreshVaultState() {
        if (this.data.network.offline || !(this.config.vault_withdrawal_threshold > 0)) {
            return;
        }
        if (this._vaultRefreshPromise) {
            this._vaultRefreshQueued = true;
            return this._vaultRefreshPromise;
        }
        this._vaultRefreshPromise = this._pcdcFetchVaultState().finally(() => {
            this._vaultRefreshPromise = null;
            if (this._vaultRefreshQueued) {
                this._vaultRefreshQueued = false;
                this.refreshVaultState();
            }
        });
        return this._vaultRefreshPromise;
    },

    async _pcdcFetchVaultState() {
        const state = await this.data.silentCall("pos.session", "get_vault_withdrawal_state", [
            this.session.id,
        ]);
        if (!state) {
            return;
        }
        // "Known" is false only before the very first successful refresh, so
        // that first refresh already reporting `required` still notifies
        // once (the "on load when already required" scenario), while a
        // later refresh that is still required does not repeat it.
        const wasRequired = this.vaultAlert.known && this.vaultAlert.required;
        this.vaultAlert.required = state.required;
        this.vaultAlert.expected = state.expected_cash;
        this.vaultAlert.threshold = state.threshold;
        this.vaultAlert.known = true;
        if (state.required && !wasRequired) {
            this.notification.add(_t("Vault withdrawal required"), { type: "warning" });
        }
    },
});
