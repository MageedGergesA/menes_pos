/** @odoo-module **/
// S2C-7 — client-side automated cash-machine ORCHESTRATION. Mezze reimplements NO
// device protocol (see docs/sell-ready/payments/cash-machine-audit.md). This layer
// only: (1) exposes normalized cash-machine states, (2) resolves an ADAPTER (the
// TEST simulator, or a PENDING adapter for a real device), (3) drives the request
// through the server — which is authoritative for the outcome and the money effect.
//
// The ONLY concrete adapter is the TEST simulator. A real device (Glory) resolves to
// a PENDING adapter that refuses to run — matching the server, which will not settle
// a real cash-machine request from a browser claim. No path can fake a device success.

// Normalized cashier-facing cash-machine states. READY/SENDING/APPROVED/CANCELLED/
// ERROR/UNKNOWN mirror the server; WAITING_CASH/COUNTING/RETURNING_CHANGE are the
// client-visible timeline (what the cashier sees while the machine works).
export const CMS = {
    READY: "ready",
    SENDING: "sending",
    WAITING_CASH: "waiting_cash",
    COUNTING: "counting",
    RETURNING_CHANGE: "returning_change",
    APPROVED: "approved",
    CANCELLED: "cancelled",
    ERROR: "error",
    UNKNOWN: "unknown",
};

// A charge MAY exist but is unconfirmed → manager Force Done eligible, never auto-retried.
export const CM_UNCERTAIN = [CMS.ERROR, CMS.UNKNOWN];

export function isCashUncertain(state) {
    return CM_UNCERTAIN.includes(state);
}

function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}

// ---- adapters --------------------------------------------------------------
// An adapter drives ONLY the client-side timeline (waiting for cash → counting →
// returning change). It NEVER decides the financial outcome — it calls ctx.complete()
// and the SERVER returns the authoritative result from the request's stored scenario.

/** TEST-ONLY simulator. */
const simulatorAdapter = {
    id: "test",
    pending: false,
    async run(ctx) {
        ctx.setState(CMS.WAITING_CASH);
        if (ctx.scenario === "connection_error") {
            // machine unreachable — no cash movement; ask the server to settle (cancel)
            await sleep(300);
            await ctx.complete();
            return;
        }
        if (ctx.scenario === "delayed_success") {
            await sleep(500);
        } else {
            await sleep(350);
        }
        ctx.setState(CMS.COUNTING);
        await sleep(300);
        if (ctx.scenario === "success_with_change") {
            ctx.setState(CMS.RETURNING_CHANGE);
            await sleep(300);
        }
        await ctx.complete();
        // a misbehaving machine that re-emits SUCCESS must still yield ONE payment
        if (ctx.scenario === "duplicate_success") {
            await ctx.complete();
        }
    },
};

/** Real devices (Glory): supported by Odoo, standalone adapter not yet wired. */
function pendingAdapter(providerId) {
    return {
        id: providerId,
        pending: true,
        async run(ctx) {
            ctx.fail("device_pending");
        },
    };
}

const REGISTRY = { test: simulatorAdapter };

/** Resolve the adapter for a provider id. Unknown/real providers → PENDING. */
export function getCashMachineAdapter(providerId) {
    return REGISTRY[providerId] || pendingAdapter(providerId || "unknown");
}
