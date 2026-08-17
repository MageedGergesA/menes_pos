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

    /** The unit price to CHARGE for a line.
     *
     *  Normally the product's list price, but a line restored from an authoritative
     *  order carries the price the server actually holds — which is not the same
     *  number once the line has been comped (0.00) or otherwise adjusted. Rebuilding
     *  every line at list_price made a comped line reappear at full price, so the
     *  till showed a total it was not going to charge.
     *
     *  A CONFIGURED line adds its chosen values' price_extra. The server has always
     *  added it at sync (so the amount tendered was right), but the till showed the
     *  bare list price until payment — the cashier read "$12.00" to the guest for a
     *  large stuffed-crust pizza and the payment screen then said $21.00. The figure
     *  quoted and the figure charged have to be the same number. A restored line
     *  still wins: the server's price_unit already includes the extra. */
    unitPrice(line) {
        return typeof line.unit_price === "number"
            ? line.unit_price
            : (line.product.list_price || 0) + (line.price_extra || 0);
    }

    /** Estimated (display) total. Still NOT authoritative — the server prices the
     *  order at pay time — but it now respects server-known line prices. */
    get estimatedTotal() {
        const dp = this.currency.decimals ?? 2;
        return roundTo(
            this.state.lines.reduce((s, l) => s + this.unitPrice(l) * l.qty, 0),
            dp
        );
    }

    _uuid() {
        if (window.crypto && window.crypto.randomUUID) {
            return window.crypto.randomUUID();
        }
        return "ln-" + Date.now() + "-" + Math.floor(Math.random() * 1e9);
    }

    /** Find a MERGEABLE line: same product AND same context.
     *
     *  "Context" is the note AND the chosen configuration. This comment used to say
     *  modifiers made lines distinct while the code compared only product and note —
     *  so a burger with no onions and a plain one were the same line, and one of the
     *  two guests got the wrong plate. The identity is now the canonical
     *  MezzeProductConfig.lineKey, the same one the lane uses. */
    _lineKey(productId, valueIds, note, comboItemIds) {
        const PC = (typeof window !== "undefined") && window.MezzeProductConfig;
        if (PC) {
            return PC.lineKey(productId, valueIds, note, comboItemIds);
        }
        // the rules module is always present in this bundle; this keeps the store
        // unit-testable in isolation without silently changing the identity
        const ids = (valueIds || []).slice().sort((a, b) => a - b);
        const key = productId + "@" + ids.join("-");
        return note ? key + " " + note : key;
    }

    _findLine(productId, note, valueIds, comboItemIds) {
        const want = this._lineKey(productId, valueIds, note || "", comboItemIds);
        return this.state.lines.find(
            (l) => this._lineKey(l.product.id, l.attribute_value_ids || [], l.note || "",
                                 (l.combo || []).map((c) => c.item_id)) === want);
    }

    /** Add one unit of an AVAILABLE product. `opts.note` scopes the line's context;
     *  `opts.forceNew` always creates a fresh distinct line. Every line carries a stable
     *  `key` so removal/undo operate on the EXACT line, never on product id. */
    addProduct(product, opts = {}) {
        if (!product || product.available === false) {
            return false;
        }
        const note = opts.note || "";
        // The chosen POS-time attribute values, if the product was configured. They
        // are part of the line's IDENTITY, they travel to the server on sync, and
        // they are never a price — the server re-derives that from the values.
        const avids = (opts.attributeValueIds || []).slice();
        // What that configuration adds to the unit price. DISPLAY only — it is never
        // sent (the server re-derives it from the values themselves) — but the till
        // must quote the price it is about to charge, not the bare list price.
        const priceExtra = typeof opts.priceExtra === "number" ? opts.priceExtra : 0;
        // The combo picks, if this product is one. They are part of the line's
        // IDENTITY exactly as the attribute values are, they travel to the server as
        // product.combo.item ids, and they are never a price.
        const combo = (opts.combo || []).slice();
        const line = opts.forceNew ? null
            : this._findLine(product.id, note, avids, combo.map((c) => c.item_id));
        if (line) {
            line.qty += 1;
        } else {
            const fresh = { key: this._uuid(), product, qty: 1, note };
            if (combo.length) {
                fresh.combo = combo;
            }
            if (avids.length || combo.length) {
                fresh.attribute_value_ids = avids;
                // the human-readable choice, for the cart line's own sub-line
                fresh.modifiers = (opts.modifiers || []).slice();
                if (priceExtra) {
                    fresh.price_extra = priceExtra;
                }
            }
            // a line restored from an authoritative order keeps the server's price
            // and comp flag; a freshly tapped product carries neither
            if (typeof opts.unitPrice === "number") {
                fresh.unit_price = opts.unitPrice;
            }
            if (opts.comped) {
                fresh.comped = true;
            }
            this.state.lines.push(fresh);
        }
        // R2A CP5: resuming a table's existing order must NOT inflate Favorites
        // (a restore is not a fresh cashier choice).
        if (!opts.noBump) {
            this._bumpFavorite(product.id);
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

    /** Remove the EXACT cart line by its stable key (never by product id — the same
     *  product can legitimately be several distinct lines via modifiers/notes/context).
     *  The Cart passes a reactive proxy that is not === the raw entry, so we resolve by
     *  key (with a same-object fallback). */
    /** Remove by the stable line key. Used when a configuration is EDITED: the old
     *  line goes and the corrected one is added, without an undo toast offering to
     *  bring the superseded version back. */
    removeByKey(key) {
        const i = this.state.lines.findIndex((l) => l.key === key);
        if (i >= 0) {
            this.state.lines.splice(i, 1);
        }
    }

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
    /** Lines as the server wants them.
     *
     *  This used to merge purely by product id and drop `note` on the floor — so a
     *  cashier could type "no onions", the cart would show it, and the kitchen would
     *  never hear about it. /orders/sync reads a per-line note and puts it on the
     *  kitchen ticket, so the grouping key has to be product AND note: two units of
     *  the same dish with different instructions are two different things to cook.
     */
    toSyncLines() {
        const groups = new Map();
        for (const l of this.state.lines) {
            const note = l.note || "";
            const avids = l.attribute_value_ids || [];
            // group by the same identity the cart displays, so what the kitchen is
            // told matches what the cashier is looking at
            const combo = (l.combo || []).slice();
            const key = this._lineKey(l.product.id, avids, note, combo.map((c) => c.item_id));
            const g = groups.get(key);
            if (g) {
                g.qty += l.qty;
            } else {
                groups.set(key, {
                    product_id: l.product.id, qty: l.qty, note,
                    attribute_value_ids: avids.slice(), combo,
                });
            }
        }
        // omit what is empty rather than sending "" and [] for every ordinary line
        return [...groups.values()].map((g) => {
            const out = { product_id: g.product_id, qty: g.qty };
            if (g.note) {
                out.note = g.note;
            }
            if (g.combo.length) {
                // product.combo.item ids — the server re-resolves and re-prices them
                out.combo = g.combo;
            }
            if (g.attribute_value_ids.length) {
                out.attribute_value_ids = g.attribute_value_ids;
            }
            return out;
        });
    }

    /** Set (or clear) a line's kitchen note. Kept on the LINE, not the product, so
     *  "no onions" applies to the plate the guest asked about and not to every one
     *  of that dish on the ticket. */
    setNote(line, note) {
        const target = this.state.lines.find((l) => l.key === line.key);
        if (target) {
            target.note = (note || "").trim().slice(0, 200);
        }
    }

    /** Immutable snapshot for the receipt (server total is applied separately). */
    snapshot() {
        return this.state.lines.map((l) => ({
            id: l.product.id,
            name: l.product.name,
            qty: l.qty,
            price: this.unitPrice(l),
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
