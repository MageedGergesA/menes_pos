/** @odoo-module **/
// Reactive cart/order state for the cashier. This is UX state only — the server
// (/orders/sync, /orders/pay) remains the authoritative source of financial
// truth. Pure helpers are exported so they can be unit-tested in isolation.
import { reactive } from "@odoo/owl";

export function roundTo(value, decimals = 2) {
    const f = Math.pow(10, decimals);
    return Math.round((Number(value) + Number.EPSILON) * f) / f;
}

/** Format a money amount with the branch currency (symbol + position). */
export function formatMoney(amount, currency) {
    const dp = currency && Number.isInteger(currency.decimals) ? currency.decimals : 2;
    const sym = (currency && currency.symbol) || "";
    const n = roundTo(amount || 0, dp).toLocaleString("en-US", {
        minimumFractionDigits: dp,
        maximumFractionDigits: dp,
    });
    if (!sym) {
        return n;
    }
    return (currency.position === "before") ? `${sym} ${n}` : `${n} ${sym}`;
}

/** Change owed to the customer. Never negative; rounded to currency precision. */
export function computeChange(total, tendered, decimals = 2) {
    const t = Number(tendered);
    if (!Number.isFinite(t)) {
        return 0;
    }
    return roundTo(Math.max(0, t - Number(total || 0)), decimals);
}

/**
 * Currency-agnostic quick-cash suggestions: the exact amount plus the next few
 * "round" tenders above it. No hardcoded EGP denominations — derived from the
 * bill so it adapts to any currency/amount.
 */
export function quickCashOptions(total, decimals = 2) {
    const t = roundTo(total, decimals);
    if (t <= 0) {
        return [];
    }
    const steps = [5, 10, 20, 50, 100, 500, 1000];
    const out = [t];
    for (const s of steps) {
        const up = Math.ceil(t / s) * s;
        if (up > t && !out.includes(up)) {
            out.push(up);
        }
    }
    return out.slice(0, 5);
}

// ---- S2C-2 tender helpers (pure) ------------------------------------------

/** Modes that have a live cashier UI in this slice. */
export const SUPPORTED_TENDER_MODES = [
    "cash", "manual", "external_terminal", "odoo_terminal", "bank_qr",
];

export function isSupportedMethod(method) {
    return !!method && SUPPORTED_TENDER_MODES.includes(method.mezze_mode);
}

/** The amount actually RECORDED as a pos.payment (never exceeds the balance). */
export function recordedAmount(entered, remaining, decimals = 2) {
    const e = Number(entered);
    if (!Number.isFinite(e) || e <= 0) {
        return 0;
    }
    return roundTo(Math.min(e, Number(remaining || 0)), decimals);
}

/** Cash change = amount tendered beyond the remaining balance (never negative). */
export function changeFor(entered, remaining, decimals = 2) {
    return computeChange(remaining, entered, decimals);
}

/** Which policy-driven fields a manual/external tender dialog must show. */
export function tenderFields(method) {
    const m = method || {};
    return {
        cash: m.mezze_mode === "cash",
        external: m.mezze_mode === "external_terminal",
        devicePolicy: m.device_policy || "disabled", // disabled|optional|required
        referencePolicy: m.reference_policy || "disabled", // disabled|optional|required
        showApproval: m.mezze_mode === "external_terminal",
    };
}

export class OrderStore {
    constructor(boot) {
        this.currency = (boot && boot.currency) || { symbol: "", position: "after", decimals: 2 };
        this.state = reactive({
            lines: [], // { product, qty }
        });
    }

    get lines() {
        return this.state.lines;
    }

    get count() {
        return this.state.lines.reduce((n, l) => n + l.qty, 0);
    }

    get isEmpty() {
        return this.state.lines.length === 0;
    }

    /** Estimated (display) total from list prices — NOT authoritative. */
    get estimatedTotal() {
        const dp = this.currency.decimals ?? 2;
        return roundTo(
            this.state.lines.reduce((s, l) => s + (l.product.list_price || 0) * l.qty, 0),
            dp
        );
    }

    _find(productId) {
        return this.state.lines.find((l) => l.product.id === productId);
    }

    /** Add one unit of an AVAILABLE product; unavailable products are ignored. */
    addProduct(product) {
        if (!product || product.available === false) {
            return false;
        }
        const line = this._find(product.id);
        if (line) {
            line.qty += 1;
        } else {
            this.state.lines.push({ product, qty: 1 });
        }
        return true;
    }

    inc(line) {
        line.qty += 1;
    }

    dec(line) {
        if (line.qty <= 1) {
            this.remove(line);
        } else {
            line.qty -= 1;
        }
    }

    remove(line) {
        const i = this.state.lines.indexOf(line);
        if (i >= 0) {
            this.state.lines.splice(i, 1);
        }
    }

    clear() {
        this.state.lines.splice(0, this.state.lines.length);
    }

    /** Snapshot of the cart for /orders/sync (product_id + qty only). */
    toSyncLines() {
        return this.state.lines.map((l) => ({ product_id: l.product.id, qty: l.qty }));
    }

    /** Immutable snapshot for the receipt (server total is applied separately). */
    snapshot() {
        return this.state.lines.map((l) => ({
            id: l.product.id,
            name: l.product.name,
            qty: l.qty,
            price: l.product.list_price || 0,
        }));
    }
}
