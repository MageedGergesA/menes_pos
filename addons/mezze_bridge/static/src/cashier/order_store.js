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
    "customer_account", "cash_machine",
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
        // R1B Favorites: per (branch, authenticated user) product-usage frequency.
        // Keyed by the real bootstrap ids (branch = pos.config id, user = res.users id) so
        // two cashiers sharing a terminal never share history, and the same cashier keeps
        // theirs across reloads. DEVICE-LOCAL ONLY: stored in this browser's localStorage —
        // it does NOT roam to other terminals and there is NO server persistence in R1B.
        const branchId = (boot && boot.config_id) || 0;
        const userId = (boot && boot.user && boot.user.id) || 0;
        this.favKey = "mezze:favorites:v1:" + branchId + ":" + userId;
        // R1B: every cart line carries a stable client-side key (_uuid). The store had no
        // existing line identity, so we mint one per line — the SAME product may be several
        // distinct lines (modifiers / notes / courses / additions), so removal + Undo must
        // operate on the LINE key, never on product id.
        this.state = reactive({
            lines: [], // { key, product, qty, note }
            undo: null, // R1B: last removed line { line:{key,product,qty,note}, index, name }
        });
    }

    // ---- R1B Favorites: frequency tracking (local, per branch) -------------
    _favMap() {
        try {
            return JSON.parse(localStorage.getItem(this.favKey) || "{}") || {};
        } catch {
            return {};
        }
    }

    _bumpFavorite(productId) {
        try {
            const m = this._favMap();
            m[productId] = (m[productId] || 0) + 1;
            localStorage.setItem(this.favKey, JSON.stringify(m));
        } catch {
            // localStorage unavailable — favorites simply don't accrue; never throws
        }
    }

    /** Product ids ordered by how often the cashier adds them (most-used first). */
    favoriteIds(limit = 8) {
        const m = this._favMap();
        return Object.keys(m)
            .map((id) => ({ id: parseInt(id, 10), n: m[id] }))
            .filter((e) => e.n > 0)
            .sort((a, b) => b.n - a.n)
            .slice(0, limit)
            .map((e) => e.id);
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

    _uuid() {
        if (window.crypto && window.crypto.randomUUID) {
            return window.crypto.randomUUID();
        }
        return "ln-" + Date.now() + "-" + Math.floor(Math.random() * 1e9);
    }

    /** Find a MERGEABLE line: same product AND same context (note). Different
     *  modifiers/notes/context are legitimately distinct lines and must NOT merge. */
    _findLine(productId, note) {
        return this.state.lines.find(
            (l) => l.product.id === productId && (l.note || "") === (note || ""));
    }

    /** Add one unit of an AVAILABLE product. `opts.note` scopes the line's context;
     *  `opts.forceNew` always creates a fresh distinct line. Every line carries a stable
     *  `key` so removal/undo operate on the EXACT line, never on product id. */
    addProduct(product, opts = {}) {
        if (!product || product.available === false) {
            return false;
        }
        const note = opts.note || "";
        const line = opts.forceNew ? null : this._findLine(product.id, note);
        if (line) {
            line.qty += 1;
        } else {
            this.state.lines.push({ key: this._uuid(), product, qty: 1, note });
        }
        this._bumpFavorite(product.id);
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

    /** Remove the EXACT cart line by its stable key (never by product id — the same
     *  product can legitimately be several distinct lines via modifiers/notes/context).
     *  The Cart passes a reactive proxy that is not === the raw entry, so we resolve by
     *  key (with a same-object fallback). */
    remove(line) {
        let i = -1;
        if (line && line.key != null) {
            i = this.state.lines.findIndex((l) => l.key === line.key);
        }
        if (i < 0) {
            i = this.state.lines.indexOf(line);
        }
        if (i >= 0) {
            const r = this.state.lines[i];
            this.state.lines.splice(i, 1);
            // R1B Undo — the removed line is briefly restorable (speed without fear). CART
            // edit only: payment / refund / void are NEVER undone here (server-authoritative).
            this._setUndo({
                line: { key: r.key, product: r.product, qty: r.qty, note: r.note || "" },
                index: i,
                name: r.product.name,
            });
        }
    }

    _setUndo(payload) {
        this.state.undo = { ...payload };
        if (this._undoTimer) {
            clearTimeout(this._undoTimer);
        }
        this._undoTimer = setTimeout(() => this.clearUndo(), 6000);
    }

    /** Restore the EXACT removed line (same key, qty, note, position). Does NOT re-bump
     *  favorites (a restore is not a fresh add) and touches no payment state. Idempotent:
     *  a second call is a no-op (undo is cleared after the first restore). */
    undoRemove() {
        const u = this.state.undo;
        if (!u || !u.line) {
            return false;
        }
        // guard against a double-restore of the same line key
        if (this.state.lines.some((l) => l.key === u.line.key)) {
            this.clearUndo();
            return false;
        }
        const at = Math.min(u.index, this.state.lines.length);
        this.state.lines.splice(at, 0, {
            key: u.line.key, product: u.line.product, qty: u.line.qty, note: u.line.note || "",
        });
        this.clearUndo();
        return true;
    }

    clearUndo() {
        if (this._undoTimer) {
            clearTimeout(this._undoTimer);
            this._undoTimer = null;
        }
        this.state.undo = null;
    }

    clear() {
        this.state.lines.splice(0, this.state.lines.length);
        this.clearUndo();   // no undo across a new/started order
    }

    /** Snapshot of the cart for /orders/sync (product_id + qty). Distinct display lines of
     *  the same product are AGGREGATED here so the server/payment path is unchanged by the
     *  multi-line display model. */
    toSyncLines() {
        const byProduct = new Map();
        for (const l of this.state.lines) {
            byProduct.set(l.product.id, (byProduct.get(l.product.id) || 0) + l.qty);
        }
        return [...byProduct.entries()].map(([product_id, qty]) => ({ product_id, qty }));
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

// ---- R1B Keyboard productivity (pure, HOOT-tested) ------------------------

/** Case-insensitive substring filter over product names. An empty/whitespace query
 *  returns the list unchanged. Deterministic — preserves the original order, adds no
 *  ranking. Used by the cashier search box so typing narrows the grid instantly. */
export function filterProducts(products, query) {
    const q = (query || "").trim().toLowerCase();
    if (!q) {
        return products || [];
    }
    return (products || []).filter((p) => (p.name || "").toLowerCase().includes(q));
}

/** Move a highlight index by `delta` within [0, len-1], clamped (no wrap-around).
 *  Returns 0 for an empty list. Keeps keyboard navigation on-screen and predictable. */
export function clampIndex(index, len, delta = 0) {
    if (!len || len <= 0) {
        return 0;
    }
    const i = (Number.isFinite(index) ? index : 0) + delta;
    return Math.max(0, Math.min(len - 1, i));
}

// V2A: a connectivity signal state -> canonical .mz-status variant. Pure + HOOT-tested.
// Invariant: UNKNOWN is NOT OFFLINE (unknown -> neutral, offline -> danger).
export function connSemantic(state) {
    if (state === "online") {
        return "success";
    }
    if (state === "unavailable" || state === "offline") {
        return "danger";
    }
    return "neutral"; // "unknown" / "checking" — explicitly not danger
}
