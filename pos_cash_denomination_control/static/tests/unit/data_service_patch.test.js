import { test, expect } from "@odoo/hoot";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { RPCError } from "@web/core/network/rpc";

definePosModels();

// Covers design.md ADR-7 (no capability spec ID — derived from the design's
// offline-replay-rejection contract). `PosData.execute` is called directly
// with the same shape `syncData` uses on replay (`data_service.js:829`:
// `{...data.args[0], uuid: data.uuid}`), so these tests exercise the real
// patched `execute()` without a real ORM round-trip.

const makeBusinessError = (name, message = "Rejected") => {
    const error = new RPCError("Odoo Server Error");
    error.data = { name, message };
    return error;
};

const captureReplayRejected = () => {
    let captured;
    const handler = (ev) => (captured = ev.detail);
    window.addEventListener("pcdc-replay-rejected", handler);
    return {
        get: () => captured,
        cleanup: () => window.removeEventListener("pcdc-replay-rejected", handler),
    };
};

test("A replayed try_cash_in_out business rejection dispatches an event and is dropped", async () => {
    const store = await setupPosEnv();
    patchWithCleanup(store.data.orm, {
        async call() {
            throw makeBusinessError("odoo.exceptions.UserError", "no reason given");
        },
    });
    const listener = captureReplayRejected();

    const result = await store.data.execute({
        type: "call",
        model: "pos.session",
        method: "try_cash_in_out",
        args: [],
        kwargs: {},
        queue: true,
        uuid: "replay-uuid-1",
    });

    listener.cleanup();
    expect(result).toBe(true);
    expect(listener.get().method).toBe("try_cash_in_out");
    expect(listener.get().message).toBe("no reason given");
});

test("A replayed set_opening_control business rejection dispatches an event and is dropped", async () => {
    const store = await setupPosEnv();
    patchWithCleanup(store.data.orm, {
        async call() {
            throw makeBusinessError("odoo.exceptions.ValidationError", "stale denomination lines");
        },
    });
    const listener = captureReplayRejected();

    const result = await store.data.execute({
        type: "call",
        model: "pos.session",
        method: "set_opening_control",
        args: [],
        kwargs: {},
        queue: true,
        uuid: "replay-uuid-2",
    });

    listener.cleanup();
    expect(result).toBe(true);
    expect(listener.get().method).toBe("set_opening_control");
});

test("A replayed post_closing_cash_details business rejection dispatches an event and is dropped", async () => {
    const store = await setupPosEnv();
    patchWithCleanup(store.data.orm, {
        async call() {
            throw makeBusinessError("odoo.exceptions.ValidationError", "stale denomination lines");
        },
    });
    const listener = captureReplayRejected();

    const result = await store.data.execute({
        type: "call",
        model: "pos.session",
        method: "post_closing_cash_details",
        args: [],
        kwargs: {},
        queue: true,
        uuid: "replay-uuid-5",
    });

    listener.cleanup();
    expect(result).toBe(true);
    expect(listener.get().method).toBe("post_closing_cash_details");
});

test("A live (non-replay) rejection is not swallowed", async () => {
    const store = await setupPosEnv();
    patchWithCleanup(store.data.orm, {
        async call() {
            throw makeBusinessError("odoo.exceptions.UserError", "no reason given");
        },
    });

    let threw = false;
    try {
        await store.data.execute({
            type: "call",
            model: "pos.session",
            method: "try_cash_in_out",
            args: [],
            kwargs: {},
            queue: true,
            uuid: "",
        });
    } catch {
        threw = true;
    }

    expect(threw).toBe(true);
});

test("A rejection for an unrelated method is not swallowed", async () => {
    const store = await setupPosEnv();
    patchWithCleanup(store.data.orm, {
        async call() {
            throw makeBusinessError("odoo.exceptions.UserError", "no reason given");
        },
    });

    let threw = false;
    try {
        await store.data.execute({
            type: "call",
            model: "pos.session",
            method: "some_other_method",
            args: [],
            kwargs: {},
            queue: true,
            uuid: "replay-uuid-3",
        });
    } catch {
        threw = true;
    }

    expect(threw).toBe(true);
});

test("A non-business error on replay is not swallowed", async () => {
    const store = await setupPosEnv();
    patchWithCleanup(store.data.orm, {
        async call() {
            throw new Error("unexpected");
        },
    });

    let threw = false;
    try {
        await store.data.execute({
            type: "call",
            model: "pos.session",
            method: "try_cash_in_out",
            args: [],
            kwargs: {},
            queue: true,
            uuid: "replay-uuid-4",
        });
    } catch {
        threw = true;
    }

    expect(threw).toBe(true);
});
