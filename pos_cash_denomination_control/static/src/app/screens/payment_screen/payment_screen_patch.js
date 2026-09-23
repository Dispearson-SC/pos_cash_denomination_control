import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { VaultAlertIndicator } from "@pos_cash_denomination_control/app/components/navbar/vault_alert_indicator/vault_alert_indicator";

/**
 * Spec `vault-withdrawal-blocking`: refuses to validate ANY sale while
 * `pos.config.vault_withdrawal_blocking` is on and the vault withdrawal
 * alert is active (`pos.vaultAlert.required`, kept current by
 * `PosStore.refreshVaultState` -- read live on every call, so the block
 * lifts by itself once a cash-out brings expected cash back under the
 * threshold, with no manual unlock needed here).
 *
 * This is a WORKFLOW CONTROL, not a security boundary: it runs entirely in
 * the POS client and can be bypassed with developer tools. Server-side
 * rejection is deliberately not pursued here -- POS orders sync after the
 * sale has physically happened, so refusing them at sync time would
 * destroy real transactions instead of preventing them.
 *
 * `l10n_mx_edi_pos` also patches `PaymentScreen` (confirmed by reading its
 * source in the container), though not `validateOrder`. This patch still
 * calls `super()` and never assumes it is the only patch present, since
 * this client is Mexican and that addon may be installed in production.
 */
patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate = false) {
        if (this.pcdcVaultBlockActive()) {
            this.pcdcShowVaultBlockedDialog();
            return;
        }
        return super.validateOrder(...arguments);
    },

    pcdcVaultBlockActive() {
        return Boolean(this.pos.config.vault_withdrawal_blocking) && this.pos.vaultAlert.required;
    },

    /**
     * Offers the withdrawal in the same interaction (T3) when the cashier
     * has the stock cash-move permission, reusing
     * `VaultAlertIndicator.preselectedVaultReasonId` rather than
     * reimplementing that resolution rule. Otherwise (T4 -- the DEFAULT,
     * not an edge case, since an ordinary cashier holds neither
     * `point_of_sale.group_pos_manager` nor `account.group_account_invoice`)
     * the cashier is told a supervisor must perform the withdrawal, instead
     * of being left at a dead end with no explanation and no exit.
     */
    pcdcShowVaultBlockedDialog() {
        const { expected, threshold } = this.pos.vaultAlert;
        const expectedFormatted = this.env.utils.formatCurrency(expected);
        const thresholdFormatted = this.env.utils.formatCurrency(threshold);
        if (!this.pos.showCashMoveButton) {
            this.dialog.add(AlertDialog, {
                title: _t("Register blocked"),
                body: _t(
                    "Expected cash (%(expected)s) has reached the vault withdrawal threshold (%(threshold)s). You don't have permission to record cash movements: ask a supervisor to perform the vault withdrawal.",
                    { expected: expectedFormatted, threshold: thresholdFormatted }
                ),
            });
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Register blocked"),
            body: _t(
                "Expected cash (%(expected)s) has reached the vault withdrawal threshold (%(threshold)s). Perform a cash withdrawal before validating any sale.",
                { expected: expectedFormatted, threshold: thresholdFormatted }
            ),
            confirmLabel: _t("Withdraw cash"),
            confirm: () =>
                this.pos.cashMove({
                    initialType: "out",
                    initialReasonId: VaultAlertIndicator.preselectedVaultReasonId(this.pos),
                }),
        });
    },
});
