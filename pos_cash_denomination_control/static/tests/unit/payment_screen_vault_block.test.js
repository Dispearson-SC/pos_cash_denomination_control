import { test, expect } from "@odoo/hoot";
import { mountWithCleanup, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv, getFilledOrder } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { VaultAlertIndicator } from "@pos_cash_denomination_control/app/components/navbar/vault_alert_indicator/vault_alert_indicator";

definePosModels();

/**
 * Covers spec `vault-withdrawal-blocking` (client-side portion): sale
 * validation is refused while `pos.config.vault_withdrawal_blocking` is on
 * and `pos.vaultAlert.required` is true (T2), the block offers the
 * withdrawal reusing `VaultAlertIndicator.preselectedVaultReasonId` (T3),
 * a cashier without cash-move permission gets a message pointing at a
 * supervisor instead of a dead end (T4), and the block lifts on its own
 * once `pos.vaultAlert.required` goes back to false (T5) -- no manual
 * unlock, since `validateOrder` reads the live reactive state on every
 * call rather than caching a decision.
 */

async function mountPaymentScreen(store) {
    const order = await getFilledOrder(store);
    return mountWithCleanup(PaymentScreen, { props: { orderUuid: order.uuid } });
}

function patchSuperValidation() {
    let called = 0;
    patchWithCleanup(OrderPaymentValidation.prototype, {
        async validateOrder() {
            called++;
        },
    });
    return () => called;
}

test("Validation proceeds normally when blocking is off", async () => {
    const store = await setupPosEnv();
    store.config.vault_withdrawal_blocking = false;
    store.vaultAlert.required = true;
    const getCalled = patchSuperValidation();
    const comp = await mountPaymentScreen(store);

    await comp.validateOrder();

    expect(getCalled()).toBe(1);
});

test("Validation proceeds normally when blocking is on but no withdrawal is required", async () => {
    const store = await setupPosEnv();
    store.config.vault_withdrawal_blocking = true;
    store.vaultAlert.required = false;
    const getCalled = patchSuperValidation();
    const comp = await mountPaymentScreen(store);

    await comp.validateOrder();

    expect(getCalled()).toBe(1);
});

test("Validation is refused when blocking is on and a withdrawal is required", async () => {
    const store = await setupPosEnv();
    store.config.vault_withdrawal_blocking = true;
    store.vaultAlert.required = true;
    store.vaultAlert.expected = 1500;
    store.vaultAlert.threshold = 1000;
    const getCalled = patchSuperValidation();
    const dialogs = [];
    patchWithCleanup(store.dialog, {
        add(component, props) {
            dialogs.push({ component, props });
            return () => {};
        },
    });
    const comp = await mountPaymentScreen(store);

    await comp.validateOrder();

    expect(getCalled()).toBe(0);
    expect(dialogs.length).toBe(1);
    // Confidentiality: neither the expected drawer cash nor the vault
    // withdrawal threshold may ever reach the cashier-facing dialog body.
    const body = dialogs[0].props.body;
    expect(body).not.toInclude(comp.env.utils.formatCurrency(1500));
    expect(body).not.toInclude(comp.env.utils.formatCurrency(1000));
});

test("Blocked dialog offers the withdrawal when the cashier has permission", async () => {
    const store = await setupPosEnv();
    store.config.vault_withdrawal_blocking = true;
    store.vaultAlert.required = true;
    store.vaultAlert.expected = 1500;
    store.vaultAlert.threshold = 1000;
    patchWithCleanup(store, {
        get showCashMoveButton() {
            return true;
        },
    });
    let captured;
    patchWithCleanup(store, {
        cashMove(options) {
            captured = options;
            return Promise.resolve();
        },
    });
    let capturedDialog;
    patchWithCleanup(store.dialog, {
        add(component, props) {
            capturedDialog = { component, props };
            return () => {};
        },
    });
    const comp = await mountPaymentScreen(store);

    await comp.validateOrder();
    await capturedDialog.props.confirm();

    expect(captured.initialType).toBe("out");
    expect(captured.initialReasonId).toBe(
        VaultAlertIndicator.preselectedVaultReasonId(store)
    );
    // Confidentiality: this dialog must never reveal the expected cash or
    // the vault withdrawal threshold to the cashier.
    expect(capturedDialog.component).toBe(ConfirmationDialog);
    expect(capturedDialog.props.title).toBe("Register blocked");
    expect(capturedDialog.props.confirmLabel).toBe("Withdraw cash");
    expect(capturedDialog.props.body).toBe(
        "A vault withdrawal is required before any sale can be validated."
    );
    expect(capturedDialog.props.body).not.toInclude(
        comp.env.utils.formatCurrency(1500)
    );
    expect(capturedDialog.props.body).not.toInclude(
        comp.env.utils.formatCurrency(1000)
    );
});

test("Blocked dialog points at a supervisor when the cashier lacks cash-move permission", async () => {
    const store = await setupPosEnv();
    store.config.vault_withdrawal_blocking = true;
    store.vaultAlert.required = true;
    store.vaultAlert.expected = 1500;
    store.vaultAlert.threshold = 1000;
    patchWithCleanup(store, {
        get showCashMoveButton() {
            return false;
        },
    });
    let cashMoveCalled = false;
    patchWithCleanup(store, {
        cashMove() {
            cashMoveCalled = true;
            return Promise.resolve();
        },
    });
    let capturedComponent;
    let capturedProps;
    patchWithCleanup(store.dialog, {
        add(component, props) {
            capturedComponent = component;
            capturedProps = props;
            return () => {};
        },
    });
    const comp = await mountPaymentScreen(store);

    await comp.validateOrder();

    expect(cashMoveCalled).toBe(false);
    expect(capturedProps.confirm).toBe(undefined);
    // Confidentiality: this dialog must never reveal the expected cash or
    // the vault withdrawal threshold to the cashier.
    expect(capturedComponent).toBe(AlertDialog);
    expect(capturedProps.title).toBe("Register blocked");
    expect(capturedProps.body).toBe(
        "A vault withdrawal is required before any sale can be validated. Ask a supervisor to perform it."
    );
    expect(capturedProps.body).not.toInclude(comp.env.utils.formatCurrency(1500));
    expect(capturedProps.body).not.toInclude(comp.env.utils.formatCurrency(1000));
});

test("Block lifts by itself once the vault alert is no longer required", async () => {
    const store = await setupPosEnv();
    store.config.vault_withdrawal_blocking = true;
    store.vaultAlert.required = true;
    const getCalled = patchSuperValidation();
    patchWithCleanup(store.dialog, {
        add() {
            return () => {};
        },
    });
    const comp = await mountPaymentScreen(store);

    await comp.validateOrder();
    expect(getCalled()).toBe(0);

    // A real cash-out already updates this through `refreshVaultState`
    // (`services/pos_store_patch.js`); this asserts the payment screen
    // itself needs no manual unlock -- it simply reads the live state.
    store.vaultAlert.required = false;
    await comp.validateOrder();

    expect(getCalled()).toBe(1);
});
