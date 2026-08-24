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
        // Display mode for catalogue prices. The server ships both figures; this only
        // decides which is shown.
        this.taxDisplay = ((boot || {}).config || {}).iface_tax_included || "total";
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
    /** Which of the server's two prices this till is currently showing.
     *
     *  Set from the branch's `iface_tax_included` and flipped by the Tax verb. The
     *  browser never derives one from the other — both came from `compute_all`.
     */
    setTaxDisplay(mode) {
        this.taxDisplay = mode === "subtotal" ? "subtotal" : "total";
    }

    _catalogPrice(product) {
        if (!product) {
            return 0;
        }
        const wanted = this.taxDisplay === "subtotal" ? product.price_excl : product.price_incl;
        // Fall back to list_price for a catalogue that predates both fields rather
        // than showing nothing.
        return typeof wanted === "number" ? wanted : (product.list_price || 0);
    }

    unitPrice(line) {
        // A typed override wins over anything else: it is the price the cashier just
        // told the guest, and showing a different one until the next sync would make
        // the screen argue with the person reading it.
        if (typeof line.price_unit === "number") {
            return line.price_unit + (line.price_extra || 0);
        }
        return typeof line.unit_price === "number"
            ? line.unit_price
            : this._catalogPrice(line.product) + (line.price_extra || 0);
    }

    /** What ONE unit costs after this line's own discount. */
    netUnitPrice(line) {
        const gross = this.unitPrice(line);
        const pct = Number(line.discount || 0);
        return pct > 0 ? gross * (1 - pct / 100) : gross;
    }

    /** Estimated (display) total. Still NOT authoritative — the server prices the
     *  order at pay time — but it now respects server-known line prices. */
    get estimatedTotal() {
        const dp = this.currency.decimals ?? 2;
        return roundTo(
            // netUnitPrice, not unitPrice: a line discount typed on the numpad has to
            // show in the running total, or the cashier quotes one figure and the
            // payment screen asks for another.
            this.state.lines.reduce((s, l) => s + this.netUnitPrice(l) * l.qty, 0),
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
            (l) => !l.seat        // a line someone has claimed is not a bucket to
                                  // grow: the next guest ordering the same dish is
                                  // ordering their own, and quietly adding it to
                                  // seat 1 means seat 1 pays for both
            && this._lineKey(l.product.id, l.attribute_value_ids || [], l.note || "",
                             l.combo || []) === want);
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
            : this._findLine(product.id, note, avids, combo);
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
        this._touch();
        return true;
    }

    inc(line) {
        line.qty += 1;
        this._touch();
    }

    dec(line) {
        if (line.qty <= 1) {
            this.remove(line);
        } else {
            line.qty -= 1;
        }
        this._touch();
    }

    /** Type a quantity instead of pressing + eleven times.
     *
     *  Zero removes the line, which is what a cashier means by typing 0 — the
     *  alternative is a line that is on the order and costs nothing.
     */
    setQty(line, qty) {
        const n = Number(qty);
        if (!Number.isFinite(n) || n < 0) {
            return;
        }
        if (n === 0) {
            this.remove(line);
            return;
        }
        line.qty = n;
        this._touch();
    }

    /** Override the price of ONE line.
     *
     *  Held on the line as `price_unit` and sent to the server, which decides whether
     *  this till is allowed to set it — `restrict_price_control` is a branch switch,
     *  not something the browser gets to assume. A negative price is refused here
     *  because it is a refund wearing a disguise, and refunds have their own path
     *  with their own ceilings and approvals.
     */
    setPrice(line, price) {
        const n = Number(price);
        if (!Number.isFinite(n) || n < 0) {
            return;
        }
        line.price_unit = n;
        this._touch();
    }

    clearPrice(line) {
        delete line.price_unit;
        this._touch();
    }

    /** A percentage off ONE line, 0–100. */
    setLineDiscount(line, percent) {
        const n = Number(percent);
        if (!Number.isFinite(n) || n < 0 || n > 100) {
            return;
        }
        if (n === 0) {
            // Clearing a discount is a change like any other — an early return that
            // skipped the backup would lose exactly the correction a cashier just
            // made under a manager's eye.
            delete line.discount;
            this._touch();
            return;
        }
        line.discount = n;
        this._touch();
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
        this._touch();
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
        this._touch();
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
        this._touch();
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
        this.forgetDraft();
    }

    /** Every mutator ends here.
     *
     *  Deliberately inside the store rather than at the twenty call sites in the
     *  Register: a backup that depends on somebody remembering to call it is a
     *  backup that is missing on exactly the path nobody thought about.
     */
    _touch() {
        this.saveDraft();
        // One hook, one place. The customer display has to see the cart change as
        // the cashier changes it, and hanging that off twenty call sites in the
        // Register is how a screen ends up stale on whichever path nobody thought
        // about — the same reasoning as the draft above.
        if (this.onChanged) {
            try {
                this.onChanged();
            } catch {
                // A display is never allowed to break a sale.
            }
        }
    }

    // ---- crash-safe draft ---------------------------------------------------
    //
    // A cart lives in memory and nowhere else, so a tablet whose OS reclaims the
    // tab, a browser that crashes, or a cashier who hits refresh loses twelve items
    // with a guest standing at the counter. Park exists, but Park is a decision
    // somebody has to make BEFORE the thing they could not predict.
    //
    // This is NOT offline mode and must not be mistaken for it. What is kept is the
    // cashier's INTENT — which products, how many, which modifiers, whose seat —
    // and never money. No total, no tax, no payment is stored or restored: a
    // recovered cart is re-synced and the server prices it exactly as it would have
    // priced it the first time. Storing a total here would create a second source
    // of truth for money on the one device that must never have one.

    /** Namespaced by BRANCH and SESSION. A draft from a session that has since been
     *  closed must never surface in the next one — that is somebody else's shift,
     *  and possibly somebody else's cash drawer. */
    _draftKey() {
        if (!this.draftScope) {
            return null;
        }
        return `mzDraft.v1.${this.draftScope.branch || 0}.${this.draftScope.session || 0}`;
    }

    /** Tell the store which shift it is in. Called once the boot payload is known;
     *  until then nothing is written, because a draft with no scope is a draft that
     *  could reappear in the wrong one. */
    setDraftScope(branchId, sessionId, uuidFn = null) {
        this.draftScope = { branch: branchId || 0, session: sessionId || 0 };
        // The order uuid is read through a hook rather than pushed in. It is
        // assigned in a dozen places in the Register, and a copy kept here would be
        // stale on whichever of them nobody remembered — producing the exact bug
        // this feature exists to avoid, a recovered cart becoming a second bill.
        this.draftUuidFn = uuidFn;
    }

    saveDraft() {
        const key = this._draftKey();
        if (!key) {
            return;
        }
        const uuid = this.draftUuidFn ? this.draftUuidFn() : null;
        try {
            if (!this.state.lines.length) {
                localStorage.removeItem(key);
                return;
            }
            localStorage.setItem(key, JSON.stringify({
                // The uuid travels too, so a recovered cart UPDATES the draft the
                // server already has instead of becoming a second bill for the same
                // guest — which is the failure this feature would otherwise cause.
                uuid: uuid || null,
                lines: this.state.lines.map((l) => ({
                    product_id: l.product.id,
                    qty: l.qty,
                    note: l.note || "",
                    seat: l.seat || 0,
                    lot_names: (l.lot_names || []).slice(),
                    attribute_value_ids: (l.attribute_value_ids || []).slice(),
                    combo: (l.combo || []).slice(),
                    modifiers: (l.modifiers || []).slice(),
                    price_extra: l.price_extra || 0,
                    // Kept because it is the cashier's DECISION (an override they
                    // made and would have to make again), not a computed price.
                    unit_price: typeof l.unit_price === "number" ? l.unit_price : undefined,
                    discount: l.discount || 0,
                    comped: !!l.comped,
                })),
            }));
        } catch {
            // Storage full, private mode, or disabled. A cart that cannot be backed
            // up still sells; it just is not recoverable. Never throws.
        }
    }

    readDraft() {
        const key = this._draftKey();
        if (!key) {
            return null;
        }
        try {
            const raw = localStorage.getItem(key);
            const data = raw ? JSON.parse(raw) : null;
            return (data && Array.isArray(data.lines) && data.lines.length) ? data : null;
        } catch {
            return null;
        }
    }

    forgetDraft() {
        const key = this._draftKey();
        if (!key) {
            return;
        }
        try {
            localStorage.removeItem(key);
        } catch {
            // nothing to do; see saveDraft
        }
    }

    /** Rebuild a cart from a stored draft, against the CURRENT catalogue.
     *
     *  A product that has since been removed or 86'd is dropped rather than
     *  resurrected: the draft is a memory of what a cashier tapped, not a licence to
     *  sell something the branch has withdrawn. Returns how many lines were dropped
     *  so the till can say so instead of silently handing back a shorter order.
     */
    restoreDraft(data, products) {
        let dropped = 0;
        const byId = new Map((products || []).map((p) => [p.id, p]));
        for (const row of (data && data.lines) || []) {
            const product = byId.get(row.product_id);
            if (!product || product.available === false) {
                dropped += 1;
                continue;
            }
            this.addProduct(product, {
                noBump: true, forceNew: true,
                note: row.note || "",
                attributeValueIds: row.attribute_value_ids || [],
                combo: row.combo || [],
                modifiers: row.modifiers || [],
                priceExtra: row.price_extra || 0,
                unitPrice: typeof row.unit_price === "number" ? row.unit_price : undefined,
                comped: !!row.comped,
            });
            const line = this.state.lines[this.state.lines.length - 1];
            if (line) {
                line.qty = row.qty || 1;
                if (row.seat) {
                    line.seat = row.seat;
                }
                if (row.discount) {
                    line.discount = row.discount;
                }
                if ((row.lot_names || []).length) {
                    line.lot_names = row.lot_names.slice();
                }
            }
        }
        this.clearUndo();
        return dropped;
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
            // Price and discount are part of the line's IDENTITY here. Two lines of
            // the same product at different prices are two different things to a
            // guest reading a receipt, and merging them would quietly reprice one of
            // them to whatever the other cost.
            const money = [l.price_unit === undefined ? "" : l.price_unit,
                           l.discount || 0,
                           // Two batches of the same dish are two lines. Merging them
                           // would put both lots on one line and lose which quantity
                           // came from which — the one thing tracking exists for.
                           (l.lot_names || []).join(","),
                           // Two guests who ordered the same dish are two lines.
                           // Merging them would put one plate on the bill and lose
                           // which of them is paying for it.
                           l.seat || 0].join("/");
            const key = this._lineKey(l.product.id, avids, note, combo) + "|" + money;
            const g = groups.get(key);
            if (g) {
                g.qty += l.qty;
            } else {
                groups.set(key, {
                    product_id: l.product.id, qty: l.qty, note,
                    attribute_value_ids: avids.slice(), combo,
                    price_unit: l.price_unit, discount: l.discount || 0,
                    lot_names: (l.lot_names || []).slice(),
                    seat: l.seat || 0,
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
            if (g.price_unit !== undefined) {
                out.price_unit = g.price_unit;
            }
            if (g.discount) {
                out.discount = g.discount;
            }
            if (g.lot_names && g.lot_names.length) {
                out.lot_names = g.lot_names;
            }
            if (g.seat) {
                out.seat = g.seat;
            }
            return out;
        });
    }

    /** Say who ordered this line.
     *
     *  Zero clears it, and clearing is not "seat zero" — it is a SHARED item, which
     *  is what a bottle of wine in the middle of the table is. A split by seat then
     *  leaves it on the table's own check rather than handing it to whoever is
     *  first, which is the kind of thing a guest notices at the card machine.
     */
    setSeat(line, seat) {
        const target = this.state.lines.find((l) => l.key === line.key);
        if (!target) {
            return;
        }
        const n = Number(seat);
        if (!Number.isFinite(n) || n <= 0) {
            delete target.seat;
            this._touch();
            return;
        }
        target.seat = Math.min(99, Math.floor(n));
        this._touch();
    }

    /** Set (or clear) a line's kitchen note. Kept on the LINE, not the product, so
     *  "no onions" applies to the plate the guest asked about and not to every one
     *  of that dish on the ticket. */
    setNote(line, note) {
        const target = this.state.lines.find((l) => l.key === line.key);
        if (target) {
            target.note = (note || "").trim().slice(0, 200);
        }
        this._touch();
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
    // Name, SKU and barcode. Searching the name alone meant a cashier holding a
    // packet could not find it by the number printed on it — and /bootstrap had been
    // sending both codes all along.
    return (products || []).filter((p) =>
        (p.name || "").toLowerCase().includes(q)
        || (p.default_code || "").toLowerCase().includes(q)
        || (p.barcode || "").toLowerCase().includes(q));
}

/** The product a scanned code refers to, or null.
 *
 *  An EXACT match only. A scanner that fell back to a substring match would ring up
 *  the wrong item whenever one barcode happens to contain another, which is exactly
 *  the failure a cashier cannot see happening.
 */
export function productForScan(products, code) {
    const c = (code || "").trim();
    if (!c) {
        return null;
    }
    return (products || []).find((p) => p.barcode && p.barcode === c)
        || (products || []).find((p) => p.default_code && p.default_code === c)
        || null;
}

/** Feed a keystroke to the scanner buffer.
 *
 *  A keyboard-HID scanner types its payload far faster than a person and ends with
 *  Enter. Distinguishing the two by SPEED is what stops a cashier typing "12345"
 *  into a search box from being read as a scan.
 *
 *  Returns `{buffer, code}` — `code` is non-null only when a scan completed.
 */
export function feedScan(buffer, key, gapMs, minLength = 4, maxGapMs = 40) {
    if (key === "Enter") {
        const code = (buffer || "").length >= minLength ? buffer : null;
        return { buffer: "", code };
    }
    if (key.length !== 1) {
        return { buffer, code: null };
    }
    // A slow keystroke means a human is typing, so the buffer starts over.
    const next = (gapMs !== null && gapMs > maxGapMs) ? key : (buffer || "") + key;
    return { buffer: next, code: null };
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
