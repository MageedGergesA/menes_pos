/** @odoo-module **/
// S2C-3 — client-side integrated-terminal ORCHESTRATION. Mezze reimplements NO
// provider protocol (see docs/sell-ready/payments/integrated-terminal-audit.md).
// This layer only: (1) exposes normalized states, (2) resolves an ADAPTER from a
// registry keyed by the native use_payment_terminal id, (3) drives the request
// through the server (which is authoritative for the outcome and the money).
//
// The ONLY concrete adapter is the TEST simulator. Real providers resolve to a
// PENDING adapter that refuses to run — matching the server, which will not accept
// a completion for a provider that is not wired to the standalone cashier. So no
// path can fake a real-provider success.

// Normalized cashier-facing states (mirror the server STATE_* constants).
export const TS = {
    READY: "ready",
    SENDING: "sending",
    WAITING: "waiting_customer",
    PROCESSING: "processing",
    APPROVED: "approved",
    DECLINED: "declined",
    CANCELLED: "cancelled",
    ERROR: "error",
    TIMEOUT: "timeout",
    UNKNOWN: "unknown",
};

// States where a charge MAY exist but is unconfirmed → Force Done eligible,
// never auto-retried.
export const UNCERTAIN_STATES = [TS.ERROR, TS.TIMEOUT, TS.UNKNOWN];

export function isUncertain(state) {
    return UNCERTAIN_STATES.includes(state);
}

function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}

// ---- adapters --------------------------------------------------------------
// An adapter's job is ONLY the client-side timeline (what the cashier sees while
// the customer interacts). It never decides the financial outcome — it calls
// ctx.complete(), and the SERVER returns the authoritative result.

/** TEST-ONLY simulator. Drives the visible timeline, then asks the server to
 *  settle. The server maps the request's stored scenario to the real outcome. */
const simulatorAdapter = {
    id: "test",
    pending: false,
    async run(ctx) {
        // customer is presented the prompt
        ctx.setState(TS.WAITING);
        if (ctx.scenario === "delayed_success") {
            await sleep(500);
            ctx.setState(TS.PROCESSING);
            await sleep(700);
        } else {
            await sleep(350);
            ctx.setState(TS.PROCESSING);
            await sleep(150);
        }
        await ctx.complete();
        // a misbehaving terminal that re-emits SUCCESS must still yield ONE payment
        if (ctx.scenario === "duplicate_success") {
            await ctx.complete();
        }
    },
};

/** Real providers: supported by Odoo, not yet wired to the standalone cashier. */
function pendingAdapter(providerId) {
    return {
        id: providerId,
        pending: true,
        async run(ctx) {
            ctx.fail("provider_pending");
        },
    };
}

const REGISTRY = { test: simulatorAdapter };

/** Resolve the adapter for a provider id. Unknown/real providers → PENDING. */
export function getTerminalAdapter(providerId) {
    return REGISTRY[providerId] || pendingAdapter(providerId || "unknown");
}
