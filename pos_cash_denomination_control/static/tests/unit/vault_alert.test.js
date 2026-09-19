import { test, expect } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-dom";
import { mountWithCleanup, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv, getFilledOrder } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { VaultAlertIndicator } from "@pos_cash_denomination_control/app/components/navbar/vault_alert_indicator/vault_alert_indicator";

definePosModels();

const makeReason = (store, vals = {}) =>
    store.models["pos.cash.move.reason"].create({
        name: "Reason",
        direction: "out",
        is_vault: false,
        sequence: 10,
        company_id: false,
        ...vals,
    });

test("Threshold delivered to POS frontend", async () => {
    const store = await setupPosEnv();
    store.config.vault_withdrawal_threshold = 1000;

    expect(store.config.vault_withdrawal_threshold).toBe(1000);
});

test("State refreshes on load", async () => {
    let called = false;
    patchWithCleanup(PosStore.prototype, {
        refreshVaultState() {
            called = true;
            return super.refreshVaultState(...arguments);
        },
    });

    await setupPosEnv();

    expect(called).toBe(true);
});

test("refreshVaultState runs after syncAllOrders successfully syncs an order", async () => {
    const store = await setupPosEnv();
    let called = false;
    patchWithCleanup(store, {
        refreshVaultState() {
            called = true;
        },
    });

    await getFilledOrder(store, {}, true);
    await store.syncAllOrders();

    expect(called).toBe(true);
});

test("refreshVaultState does not run when syncAllOrders has nothing to sync", async () => {
    const store = await setupPosEnv();
    let called = false;
    patchWithCleanup(store, {
        refreshVaultState() {
            called = true;
        },
    });

    await store.syncAllOrders();

    expect(called).toBe(false);
});

test("refreshVaultState runs after cashMove completes", async () => {
    const store = await setupPosEnv();
    patchWithCleanup(store.dialog, {
        add(component, props, options) {
            options?.onClose?.();
            return () => {};
        },
    });
    let called = false;
    patchWithCleanup(store, {
        refreshVaultState() {
            called = true;
        },
    });

    await store.cashMove({ initialType: "out" });

    expect(called).toBe(true);
});

test("refreshVaultState runs after a no-options cashMove completes", async () => {
    const store = await setupPosEnv();
    patchWithCleanup(store.dialog, {
        add(component, props, options) {
            options?.onClose?.();
            return () => {};
        },
    });
    let called = false;
    patchWithCleanup(store, {
        refreshVaultState() {
            called = true;
        },
    });

    await store.cashMove();

    expect(called).toBe(true);
});

test("Notification shown once on transition to required", async () => {
    const store = await setupPosEnv();
    store.config.vault_withdrawal_threshold = 100;
    const notifications = [];
    patchWithCleanup(store.notification, {
        add(message) {
            notifications.push(message);
            return () => {};
        },
    });
    const responses = [
        { expected_cash: 50, threshold: 100, required: false },
        { expected_cash: 150, threshold: 100, required: true },
    ];
    patchWithCleanup(store.data, {
        async silentCall() {
            return responses.shift();
        },
    });

    await store.refreshVaultState();
    await store.refreshVaultState();

    expect(notifications.length).toBe(1);
});

test("Notification shown on load when already required", async () => {
    const store = await setupPosEnv();
    store.config.vault_withdrawal_threshold = 100;
    const notifications = [];
    patchWithCleanup(store.notification, {
        add(message) {
            notifications.push(message);
            return () => {};
        },
    });
    patchWithCleanup(store.data, {
        async silentCall() {
            return { expected_cash: 500, threshold: 100, required: true };
        },
    });

    await store.refreshVaultState();

    expect(notifications.length).toBe(1);
});

test("Indicator persists across multiple refreshes without repeated notification", async () => {
    const store = await setupPosEnv();
    store.config.vault_withdrawal_threshold = 100;
    const notifications = [];
    patchWithCleanup(store.notification, {
        add(message) {
            notifications.push(message);
            return () => {};
        },
    });
    patchWithCleanup(store.data, {
        async silentCall() {
            return { expected_cash: 500, threshold: 100, required: true };
        },
    });

    await store.refreshVaultState();
    await store.refreshVaultState();
    await store.refreshVaultState();

    expect(notifications.length).toBe(1);
    expect(store.vaultAlert.required).toBe(true);
});

test("Indicator retains last known state while offline", async () => {
    const store = await setupPosEnv();
    store.config.vault_withdrawal_threshold = 100;
    patchWithCleanup(store.data, {
        async silentCall() {
            return { expected_cash: 500, threshold: 100, required: true };
        },
    });

    await store.refreshVaultState();
    expect(store.vaultAlert.required).toBe(true);

    store.data.network.offline = true;
    await store.refreshVaultState();

    expect(store.vaultAlert.required).toBe(true);
});

test("Indicator is not shown when required is False", async () => {
    const store = await setupPosEnv();
    store.vaultAlert.required = false;

    await mountWithCleanup(VaultAlertIndicator, { props: {} });
    await animationFrame();

    expect(".vault-alert-indicator").toHaveCount(0);
});

test("Indicator is shown when required is True", async () => {
    const store = await setupPosEnv();
    store.vaultAlert.required = true;

    await mountWithCleanup(VaultAlertIndicator, { props: {} });
    await animationFrame();

    expect(".vault-alert-indicator").toHaveCount(1);
});

test("Click preselects the POS default vault reason", async () => {
    const store = await setupPosEnv();
    const vaultReason = makeReason(store, { name: "Vault", is_vault: true });
    store.config.default_cash_out_reason_id = vaultReason;
    let captured;
    patchWithCleanup(store, {
        cashMove(options) {
            captured = options;
            return Promise.resolve();
        },
    });
    const indicator = await mountWithCleanup(VaultAlertIndicator, { props: {} });

    await indicator.onClick();

    expect(captured.initialType).toBe("out");
    expect(captured.initialReasonId).toBe(vaultReason.id);
});

test("Click preselects the first active vault reason when the default is not a vault reason", async () => {
    const store = await setupPosEnv();
    const nonVaultDefault = makeReason(store, { name: "Bank", is_vault: false });
    makeReason(store, { name: "Vault B", is_vault: true, sequence: 20 });
    const earlierVault = makeReason(store, { name: "Vault A", is_vault: true, sequence: 10 });
    store.config.default_cash_out_reason_id = nonVaultDefault;
    let captured;
    patchWithCleanup(store, {
        cashMove(options) {
            captured = options;
            return Promise.resolve();
        },
    });
    const indicator = await mountWithCleanup(VaultAlertIndicator, { props: {} });

    await indicator.onClick();

    expect(captured.initialReasonId).toBe(earlierVault.id);
});

test("Click shows no preselection when no vault reason exists", async () => {
    const store = await setupPosEnv();
    let captured;
    patchWithCleanup(store, {
        cashMove(options) {
            captured = options;
            return Promise.resolve();
        },
    });
    const indicator = await mountWithCleanup(VaultAlertIndicator, { props: {} });

    await indicator.onClick();

    expect(captured.initialReasonId).toBe(false);
});

test("Click without stock cash-move permission shows a notification instead of the popup", async () => {
    const store = await setupPosEnv();
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
    const notifications = [];
    patchWithCleanup(store.notification, {
        add(message) {
            notifications.push(message);
            return () => {};
        },
    });
    const indicator = await mountWithCleanup(VaultAlertIndicator, { props: {} });

    await indicator.onClick();

    expect(cashMoveCalled).toBe(false);
    expect(notifications.length).toBe(1);
});
