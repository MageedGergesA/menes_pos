/** @odoo-module **/
// Root cashier component. Owns the screen phase machine and orchestrates the
// backend contracts (bootstrap → sync → pay → breakdown). It NEVER falls back to
// demo data: any auth/catalog/network failure resolves to an explicit state.
// S2C-2: multi-tender (cash + manual/external) with device/reference/duplicate
// policy, partial + mixed tender, manager approval, and an authoritative receipt.
import { Component, useState, useRef, useEffect, onWillStart, onMounted, onWillUnmount, markup } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ProductGrid } from "./components/product_grid";
import { Cart } from "./components/cart";
import { Workspace } from "./components/workspace";
import { SettingsPanel } from "./components/settings";
import { ManagerGate } from "./components/manager_gate";
import { DeliveryForm } from "./components/delivery_form";
import { ProductConfig } from "./components/product_config";
import { SessionClose } from "./components/session_close";
import { TipPool } from "./components/tip_pool";
import { SplitBill } from "./components/split_bill";
import { RefundScreen } from "./components/refund";
import { EnterCodeScreen } from "./components/enter_code";
import { Numpad } from "./components/numpad";
import { CoursesScreen } from "./components/courses";
import { ProductInfoScreen } from "./components/product_info";

// CONV-3: the canonical product-configuration RULES (design/product-config.js).
// A plain script rather than an ES module, because the drive-thru board is a static
// page and cannot import one — and the whole point is that both surfaces apply the
// SAME rules. Loaded earlier in this bundle, so it is always present.
const PC = window.MezzeProductConfig;
import { WorkspaceRail } from "../shell/rail";
import { applyAppearance, loadAppearance } from "../shell/appearance";
import { PaymentScreen } from "./components/payment_screen";
import { Receipt } from "./components/receipt";
import { CashMachine } from "./components/cash_machine";
import { formatMoney, roundTo, connSemantic, filterProducts, clampIndex,
         feedScan, productForScan } from "./order_store";
import { getTerminalAdapter, TS } from "./terminal_service";
import { getCashMachineAdapter, CMS } from "./cash_machine_service";

function makeUuid() {
    if (window.crypto && window.crypto.randomUUID) {
        return window.crypto.randomUUID();
    }
    return "mz-" + Date.now() + "-" + Math.floor(Math.random() * 1e9);
}

function maskRef(ref) {
    const r = (ref || "").trim();
    if (r.length <= 4) {
        return r;
    }
    return "••••" + (r.length < 10 ? r.slice(-4) : r.slice(-6));
}

export class Root extends Component {
    static template = "mezze_bridge.Root";
    static components = { ProductGrid, Cart, PaymentScreen, Receipt, CashMachine, Workspace, SettingsPanel, WorkspaceRail, ManagerGate, DeliveryForm, ProductConfig, SessionClose, TipPool, SplitBill, RefundScreen, EnterCodeScreen, Numpad, CoursesScreen, ProductInfoScreen };
    static props = {};

    setup() {
        const { boot, api, order } = this.env.mezze;
        this.api = api;
        this.order = order;
        this.boot = boot;
        this.FAV = "__fav__";   // R1B: id of the Favorites pseudo-category
        this.currency = order.currency;
        this.cart = useState(order.state);
        this.searchRef = useRef("search"); // R1B keyboard: the product search input

        // P3F — canonical dialog focus management for the host/confirm modals (move,
        // recall, assign, reservation, walk-in, host-confirm). When one opens, move
        // focus inside it and trap Tab within; when it closes, restore focus to the
        // control that opened it. Deliberately scoped to the .mz-modal-scrim modals —
        // the payment/tender modals keep their own established focus + Escape policy.
        useEffect(
            () => {
                const panel = document.querySelector(".mz-modal-scrim .mz-modal");
                if (!panel) {
                    return;
                }
                const sel = 'button:not([disabled]), [href], input:not([disabled]),'
                    + ' select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
                const visible = () => [...panel.querySelectorAll(sel)].filter(
                    (el) => el.offsetParent !== null);
                this._modalReturnEl = document.activeElement;
                const f = visible();
                // a real form dialog opens on its first field; otherwise the first
                // safe control (never auto-focus a destructive action).
                const fields = [...panel.querySelectorAll(
                    "input:not([disabled]), select:not([disabled]), textarea:not([disabled])")]
                    .filter((el) => el.offsetParent !== null);
                (fields[0] || f[0] || panel).focus();
                const onTrap = (ev) => {
                    if (ev.key !== "Tab") {
                        return;
                    }
                    const els = visible();
                    if (!els.length) {
                        return;
                    }
                    const first = els[0];
                    const last = els[els.length - 1];
                    if (ev.shiftKey && document.activeElement === first) {
                        ev.preventDefault();
                        last.focus();
                    } else if (!ev.shiftKey && document.activeElement === last) {
                        ev.preventDefault();
                        first.focus();
                    }
                };
                panel.addEventListener("keydown", onTrap);
                return () => {
                    panel.removeEventListener("keydown", onTrap);
                    const back = this._modalReturnEl;
                    if (back && back.focus && document.body.contains(back)) {
                        back.focus();
                    }
                };
            },
            () => [this._hostModalKey()]
        );
        this.state = useState({
            splitting: false,
            splitChild: null,
            splitContext: null,
            phase: "booting", // booting|auth_required|error|menu|payment|processing|receipt
            // Prototype IA: which workspace the rail has opened in the modal host, and the
            // standalone URL it mirrors (null when the workspace has no page of its own).
            workspace: null,
            // resolved before first paint by the appearance bootstrap in the page template
            mzMode: (typeof document !== "undefined"
                && document.documentElement.getAttribute("data-mz-mode")) || "light",
            errorMsg: "",
            // A refused rail destination (design v3 `tillBarred`). Held in the
            // shell, not the rail, because the rail is shared by three surfaces
            // and none of them should own a toast.
            railNotice: null,
            categories: [],
            products: [],
            // CONV-3: the open product configurator, or null. { product, groups,
            // selection, lineKey } — lineKey set only when EDITING an existing line.
            config: null,
            methods: [],
            activeCategory: null,
            search: "",        // R1B keyboard: live product filter text
            searchIndex: 0,    // R1B keyboard: highlighted result for ↑/↓ + Enter
            sessionId: null,
            payment: null, // { uuid, total, paid, remaining, tenders: [] }
            warn: null, // { ctx, pending }
            managerGate: null,   // { action, title, detail, reasonRequired, run }
            discount: null,      // { scope, productId, detail, percent, reason, error }
            refunding: false,    // the refund screen is open
            priceControl: false, // branch restricts who may change a price
            pricelists: [],      // lists this branch trades on
            fiscalPositions: [],
            notePresets: [],     // pos.note — the kitchen's own vocabulary
            scanBuffer: "",      // keystrokes since the last scanner delimiter
            noteEdit: null,      // { key, name, text }
            // Dine-in | Takeaway | Delivery. A table-bound order is dine-in by
            // definition and the control says so rather than pretending otherwise.
            serviceMode: "eat_in",
            deliveryForm: false,
            actionError: "",     // comp/void/fire/86 failure, shown on the order panel
            // Neutral confirmations. Kept apart from actionError because a choice
            // that WORKED must not be dressed as a failure — a red bar with a cross
            // teaches the cashier that what they just did went wrong.
            actionNote: "",
            firedOk: false,
            managerReq: null, // { ctx, pending, error }
            customer: null, // S2C-6 selected account customer { id, name, phone, ... }
            creditWarn: null, // S2C-6 over-limit soft warn { ctx, pending }
            creditManager: null, // S2C-6 over-limit manager approval { ctx, pending, error }
            customerPicker: null, // S2C-6 customer search + deposit/settle modal
            terminal: null, // S2C-3 integrated-terminal request state
            cashmachine: null, // S2C-7 automated cash-machine request state
            qr: null, // S2C-4 bank-app QR state
            tenderError: "",
            receipt: null,
            inFlight: false,
            conn: { local: "unknown", wan: "unknown" },
            // R2A CP5 — table-bound Register context resolved by the server:
            //   null                      → counter mode
            //   { error: 'invalid_table' } → stale / cross-branch table id
            //   { id, name, floor, order_uuid, guests }
            table: (boot && boot.table) || null,
            // R2A CP5 — stable order uuid so re-opening/adding to the SAME table never
            // spawns a duplicate draft (resumed order's uuid, or one minted once).
            orderUuid: null,
            // The version of this check the client last saw. Sent back on every
            // write so the server can refuse one based on a bill that has since
            // moved (see controllers/main.py `_assert_revision`).
            orderRevision: null,
            orderRevisionUuid: null,
            // { reason:'tendered'|'settled'|'split', paid } when the server refuses edits
            editLock: null,
            // Set when the server refuses a stale write. Carries what the check
            // looks like NOW, so the banner can name the difference instead of
            // silently redrawing over somebody's work.
            conflict: null,
            conflictReview: false,
            entering_code: false,
            // Which cart line the numpad is editing, by its stable key rather than by
            // object: the cart is rebuilt often and a held reference goes stale.
            padLineKey: null,
            // Batch entry for a tracked line.
            lotLineKey: null,
            // The line whose seat is being set, or null.
            seatLineKey: null,
            // The gratuity on the bill being paid, as the SERVER last reported it.
            tip: 0,
            // Whether this branch has a customer display worth pushing to.
            hasCfd: false,
            // Set when a cart was rebuilt after a crash or a reload, so the cashier
            // is told rather than handed an order that appeared by itself.
            recovered: "",
            lotDraft: "",
            lotError: "",
            // What else this guest might want, from real sales history.
            upsell: [],
            // Payment methods the branch has marked as one-tap.
            fastPayment: [],
            // v19 order types. The till names one; the server decides what it costs.
            presets: [],
            presetId: null,
            // Whether the courses screen is open. Table-only: a course is a table's
            // sequence, and a counter order has no such thing.
            courses: false,
            // The product whose info card is open, or null. Holds the GRID product
            // (name and id) so the card has a heading before the lookup returns.
            infoProduct: null,
            // The branch's automatic promotions currently on this order, and their
            // total, so a reconcile that changes nothing costs no re-read.
            autoPromoDiscount: 0,
            autoPromotions: [],
            // A gift card the cashier has entered but not yet spent. Held here
            // rather than applied to the order because it is a TENDER: it settles at
            // payment, against the balance that exists then.
            giftCard: null,
            // R2A CP6 — table picker (counter order → table). mode 'assign' (CP6) or
            //   'move' (CP7 transfer/merge): null | { mode, floors, activeFloorId, error, busy }
            assignPicker: null,
            // R2A CP7 — transfer/merge confirmation:
            //   null | { kind:'transfer'|'merge', dest, src*, dst*, error, blocked }
            moveConfirm: null,
            // R2A CP9 — Orders workspace (Open|Parked|Completed + search + recall):
            //   { filter, query, rows, loading, error, hasMore, offset }
            orders: null,
            // R2A CP9 — read-only view of a COMPLETED order (never editable):
            //   null | { ...order summary, lines }
            completedView: null,
            // R2A CP9 — "recall would discard the current order" guard:
            //   null | { target }  (target = the order row the cashier wants to open)
            recallConfirm: null,
            // R2A CP10 — Reservations/Waitlist (host) workspace:
            //   { tab:'reservations'|'waitlist', dateOffset:-1|0|1, query,
            //     resRows, wlRows, wlStats, loading, error }
            host: null,
            // R2A CP10 — new-reservation / add-walk-in forms + confirm dialogs:
            resForm: null,      // null | { name, phone, guests, date, time, duration, note, is_vip, table_id, busy, error }
            wlForm: null,       // null | { name, phone, party_size, quoted_wait, note, busy, error }
            hostConfirm: null,  // null | { kind:'no_show'|'cancel', model:'res'|'wl', row, action }
        });

        onWillStart(async () => {
            // Appearance BEFORE the catalogue: density/scale/columns change layout, and
            // repainting the whole till a moment after it appears reads as a glitch.
            // It must never gate selling, so it is not awaited into the failure path.
            await this.applyServerAppearance();
            await this.bootstrap();
        });
        onMounted(() => {
            this.pollConnectivity();
            this._connTimer = window.setInterval(() => this.pollConnectivity(), 20000);
            // R1B keyboard productivity: a single global listener. It only ever DRIVES
            // navigation/search/add — it never confirms a tender, refund, void, or
            // manager override (those stay pointer + explicit input only).
            this._onKey = (ev) => this.handleKey(ev);
            window.addEventListener("keydown", this._onKey);
        });
        onWillUnmount(() => {
            window.clearInterval(this._connTimer);
            if (this._onKey) {
                window.removeEventListener("keydown", this._onKey);
            }
        });
    }

    // ---- helpers -----------------------------------------------------------
    fmt(amount) {
        return formatMoney(amount, this.currency);
    }

    get branchName() {
        return (this.boot.branch && this.boot.branch.name) || "";
    }

    get userName() {
        return (this.boot.user && this.boot.user.name) || "";
    }

    get connLabel() {
        if (this.state.conn.local === "online") {
            return _t("Local server online");
        }
        if (this.state.conn.local === "unavailable") {
            return _t("Local server unavailable");
        }
        return _t("Checking…");
    }

    // V2A: connectivity via canonical .mz-status semantics (UNKNOWN != OFFLINE).
    get connVariant() {
        return connSemantic(this.state.conn.local);
    }
    get wanVariant() {
        return connSemantic(this.state.conn.wan);
    }
    get wanLabel() {
        if (this.state.conn.wan === "online") {
            return _t("Internet online");
        }
        if (this.state.conn.wan === "offline" || this.state.conn.wan === "unavailable") {
            return _t("Internet offline");
        }
        return _t("Internet: checking…");
    }

    get decimals() {
        return this.currency.decimals ?? 2;
    }

    // R1B Favorites: a pinned pseudo-category of the cashier's most-used products.
    // It does NOT replace categories — it sits in front of them for 1-tap repeat.
    get favoriteProducts() {
        const ids = this._stableFavoriteIds();
        if (!ids.length) {
            return [];
        }
        const byId = new Map(this.state.products.map((p) => [p.id, p]));
        return ids.map((id) => byId.get(id)).filter(Boolean);
    }

    /**
     * Favourites ranked by use — but NOT re-ranked while the cashier is looking at
     * them.
     *
     * Adding a product bumps its count, and the ranking is by count, so the live
     * list re-sorts on every tap: the card under the cashier's finger jumps to a
     * new position, its neighbours shuffle, and a product ranked ninth can push
     * another out of the eight entirely. Ordering a round of drinks meant chasing
     * buttons around the screen.
     *
     * A menu is muscle memory. The ranking is refreshed whenever the cashier is
     * somewhere else — any other category, or a fresh load — and held still for as
     * long as the Favourites view is the one on screen.
     */
    _stableFavoriteIds() {
        const live = this.order.favoriteIds(8);
        if (this.state.activeCategory !== this.FAV) {
            this._favOrder = live;
            return live;
        }
        if (!this._favOrder) {
            this._favOrder = live;
        }
        return this._favOrder;
    }

    /** Design v3: the card at the foot of the category rail.
     *
     *  "100% with photos · 0 monogram tiles · Favorites clean". Every figure is
     *  the catalogue in front of the cashier, counted — not a score anyone has to
     *  interpret. A tile with no photo is DRAWN as a monogram (product_grid picks
     *  the <img> on `has_image` and falls back to initials), so "monogram tiles"
     *  is literally what is on the screen rather than a proxy for it.
     */
    get menuHealth() {
        const items = this.state.products || [];
        const total = items.length;
        const withPhotos = items.filter((p) => p.has_image).length;
        // Favourites are remembered by id and resolved against the live catalogue,
        // where an id that no longer sells is dropped by `.filter(Boolean)`.
        // SILENTLY is the problem: the cashier's one-tap row quietly gets shorter
        // and nothing says why. A favourite is stale when its product has gone
        // from the catalogue or is 86'd off it.
        const byId = new Map(items.map((p) => [p.id, p]));
        const stale = this.order.favoriteIds(Infinity).filter((id) => {
            const p = byId.get(id);
            return !p || p.available === false;
        }).length;
        return {
            total,
            withPhotos,
            // a catalogue with nothing in it is not 100% healthy
            pct: total ? Math.round((withPhotos * 100) / total) : 0,
            monograms: total - withPhotos,
            staleFavorites: stale,
        };
    }

    get menuHealthLabel() {
        return _t("Menu health");
    }

    get withPhotosLabel() {
        return _t("with photos");
    }

    get menuHealthPct() {
        return _t("%s%%", this.menuHealth.pct);
    }

    get menuHealthNote() {
        const h = this.menuHealth;
        // The design prints the count even when it is zero ("0 monogram tiles"),
        // which also avoids an English/Arabic plural split for one number.
        return _t("%s monogram tiles", h.monograms) + " · " + (
            h.staleFavorites
                ? _t("%s stale favorites", h.staleFavorites)
                : _t("Favorites clean"));
    }

    get hasFavorites() {
        return this.favoriteProducts.length > 0;
    }

    get favLabel() {
        return _t("Favorites");
    }
    // Translatable copy for the restored category sidebar (C2 keeps staff Arabic at
    // 100%, so new UI strings must go through _t and ship an ar.po entry).
    get categoriesLabel() {
        return _t("Categories");
    }
    get allItemsLabel() {
        return _t("All items");
    }

    /** How many items the current selection actually renders (reference shows this
     *  line above the grid). Derived from filteredProducts, so it stays honest while
     *  a category filter or a search query is narrowing the catalog. */
    get availableLabel() {
        const n = this.filteredProducts.length;
        return n === 1 ? _t("1 item available") : _t("%s items available", n);
    }

    // ---- DESIGN FIDELITY (Register): category sidebar counts -------------------
    // REAL counts, computed from the products the server already sent. Nothing is
    // hardcoded and no new backend call is made: the reference shows a count beside
    // every category, and this is the same catalogue the grid renders.
    categoryCount(catId) {
        return this.state.products.filter(
            (p) => (p.pos_categ_ids || []).includes(catId)
        ).length;
    }
    get allCount() {
        return this.state.products.length;
    }
    get favCount() {
        return this.favoriteProducts.length;
    }

    // ---- DESIGN FIDELITY (Register): left icon rail ---------------------------
    // The reference navigates from a 74px icon rail. Every entry below maps to a
    // REAL production destination — no dead navigation. The reference's "settings"
    // icon has no Mezze workspace behind it and is deliberately omitted rather than
    // rendered as a no-op (documented in the restoration report).
    get railMark() {
        return (this.boot.branch && this.boot.branch.name ? this.boot.branch.name : "Mezze")
            .trim().charAt(0).toUpperCase() || "M";
    }
    // ---- TOPBAR (prototype) -------------------------------------------------------
    /** "#S-<n>" from the REAL open session. The prototype also shows "open 4h 12m";
     *  the bootstrap payload carries no session start time, so no duration is shown
     *  rather than a made-up one. */
    get sessionLabel() {
        const id = this.state.sessionId;
        return id ? ("#S-" + id) : "";
    }

    get themeToggleLabel() {
        return this.state.mzMode === "dark" ? _t("Switch to light mode") : _t("Switch to dark mode");
    }

    /** Drives the appearance contract the page bootstrap already implements
     *  (?mzmode= > localStorage 'mzSettings.v1' > prefers-color-scheme), so this is a
     *  control over shipped styling rather than a second theming mechanism. */
    /** The server is the source of truth for appearance; localStorage is only a
     *  first-paint hint for the page bootstrap, so both are written. */
    toggleTheme() {
        const next = this.state.mzMode === "dark" ? "light" : "dark";
        this.appearance = Object.assign({}, this.appearance, { app_mode: next });
        applyAppearance(this.appearance);
        let o = {};
        try {
            o = JSON.parse(localStorage.getItem("mzSettings.v1") || "{}") || {};
        } catch (e) {
            o = {};
        }
        o.app_mode = next;
        try {
            localStorage.setItem("mzSettings.v1", JSON.stringify(o));
        } catch (e) {
            // a locked-down till may refuse storage; the toggle still works for this session
        }
        this.state.mzMode = next;
        // best effort — the toggle has already taken effect for this session
        this.api.call("/settings/save", { values: { app_mode: next } }).catch(() => {});
    }

    /** A branch-wide settings change needs a supervisor when the till itself may
     *  not make one. Reuses the same gate as a comp — one prompt, one request. */
    elevateSettings({ values, label, apply }) {
        this.state.managerGate = {
            action: "settings",
            title: _t("Apply to the whole branch"),
            detail: label,
            reasonRequired: false,
            run: async ({ managerCode, managerPin }) => {
                await apply({ manager_code: managerCode, manager_pin: managerPin });
                this.onAppearanceChange(values);
            },
        };
    }

    /** Split Bill V2 — a full workspace, not a popup, and nothing is written until
     *  the cashier commits. Split PAYMENT is a different thing and still lives on
     *  the Payment screen; this moves items between checks. */
    async openSplitBill() {
        if (this.order.isEmpty || this.state.inFlight) {
            return;
        }
        // A bill has to EXIST before it can be split. A counter order that has not
        // been synced yet has no uuid, so the workspace would open on nothing and
        // show an empty list — which is exactly what the browser tests found. Save
        // it as a draft first, the same way charging does; the split itself still
        // writes nothing until the cashier commits.
        // ALWAYS sync, never "only when there is no uuid". Reusing a uuid without
        // pushing the cart had two failure modes on the floor, and both looked like a
        // broken Split rather than a stale one:
        //
        //  * the uuid outlived its order — voided, emptied, or from a cycle the
        //    server has since closed — so /split/state answered "unknown_order" and
        //    the cashier saw a dead workspace;
        //  * the uuid was still valid but the cart had moved on, so the workspace
        //    offered yesterday's lines to be split off today's bill.
        //
        // Syncing the SAME uuid updates that order rather than making a second one,
        // so a table keeps one bill; a cart with no uuid yet gets one here.
        this.state.inFlight = true;
        try {
            const uuid = this.state.orderUuid || makeUuid();
            const body = {
                uuid,
                session_id: this.state.sessionId,
                lines: this.order.toSyncLines(),
                draft: true,
            };
            if (this.isTableBound) {
                body.table_id = this.state.table.id;
            }
            body.expected_revision = this._revisionClaimFor(uuid);
            const res = await this.api.call("/orders/sync", body);
            this.state.orderUuid = uuid;
            this._noteFromServer(res, uuid);
        } catch (err) {
            this._failFromError(err);
            this.state.inFlight = false;
            return;
        }
        this.state.inFlight = false;
        this.state.splitting = true;
    }

    closeSplitBill() {
        this.state.splitting = false;
    }

    /** A signed-out session inside the split workspace is the till's problem, not
     *  the workspace's: close it and take the Register to the same place every
     *  other screen goes, rather than leaving a dead workspace over the order. */
    onSplitAuthRequired(err) {
        this.state.splitting = false;
        this._failFromError(err || { kind: "auth" });
    }

    /** A freshly created child goes straight to Payment — no Save, no Orders, no
     *  hunting for the check that was made two seconds ago.
     *
     *  It does NOT go through goToPayment(): that syncs the cart as a draft, and the
     *  child is already a real order with its own lines and total. Re-syncing the
     *  cart here would pay the wrong thing.
     */
    onSplitChildReady(child) {
        this.state.splitting = false;
        if (!child || !child.uuid) {
            return;
        }
        // Remember where we came from, because a settled child clears the table
        // binding on its way to the receipt — right for an ordinary order, wrong
        // while the rest of the family is still open.
        this.state.splitContext = {
            rootUuid: this.state.orderUuid,
            table: this.state.table,
            seq: child.split_seq || 0,
        };
        this.state.splitChild = child;
        const total = child.amount_total || 0;
        const paid = child.amount_paid || 0;
        this.state.payment = {
            uuid: child.uuid,
            total,
            paid,
            remaining: roundTo(total - paid, this.decimals),
            tenders: [],
        };
        this.state.warn = null;
        this.state.managerReq = null;
        this.state.tenderError = "";
        this.state.phase = "payment";
        // The guest is now being ASKED for money; the screen should say so.
        this.pushCfd("paying");
    }

    /** After a child is settled: back to the family, not to a blank till. */
    get splitFamilyOpen() {
        return !!(this.state.splitContext && this.state.splitContext.rootUuid);
    }

    async resumeSplitRoot({ split = false } = {}) {
        const ctx = this.state.splitContext;
        this.state.splitContext = null;
        this.state.splitChild = null;
        if (!ctx || !ctx.rootUuid) {
            this.newOrder();
            return;
        }
        // ORDER MATTERS. Leaving the receipt phase must happen BEFORE the receipt's
        // data is cleared: there is an await below, Owl renders during it, and a
        // render with phase='receipt' and receipt=null crashes the Receipt template
        // on `receipt.branch` — which destroys the root component and takes the whole
        // till with it. Unmount first, then clear.
        this.state.phase = "menu";
        this.state.receipt = null;
        this.state.payment = null;
        try {
            // Reopen the ORIGINAL against server truth — its quantities changed when
            // the child was carved off, so a cached cart would be a lie.
            const res = await this.api.call("/orders/get", { uuid: ctx.rootUuid });
            if (res && res.ok !== false && res.state === "draft") {
                this._loadOrderLines(res.lines);
                this.state.orderUuid = res.uuid;
                this.state.table = ctx.table || this.state.table;
            } else if (res && res.ok !== false) {
                // The original was settled while this child was being paid — the
                // family is finished, so show it rather than reopening an editable
                // cart over a closed order.
                this._showCompleted(res);
                return;
            }
        } catch (e) {
            // A failed reopen must not strand the cashier on a receipt.
        }
        if (split) {
            this.state.splitting = true;
        }
    }

    /** The close needs a capability the till does not hold, so it borrows one for
     *  a single call through the same manager prompt a comp or a refund uses. */
    /** Signing a tip distribution. Its own action rather than borrowing the
     *  session close's: the gate stamps what was approved, and a tip run signed
     *  under "close" would read as a session close in the trail. */
    elevateTips({ title, detail, run }) {
        this.state.managerGate = {
            action: "tips",
            title: title,
            detail: detail,
            reasonRequired: false,
            run: run,
        };
    }

    elevateClose({ title, detail, run }) {
        this.state.managerGate = {
            action: "close",
            title: title,
            detail: detail,
            reasonRequired: false,
            run: run,
        };
    }

    /** Read the branch's effective settings and stamp the appearance contract. */
    async applyServerAppearance() {
        try {
            const r = await this.api.call("/settings/effective", {});
            this.appearance = (r && r.effective) || {};
        } catch (e) {
            this.appearance = {};   // fall back to the catalogue defaults
        }
        const applied = applyAppearance(this.appearance);
        this.state.mzMode = applied["data-mz-mode"];
        return applied;
    }

    /** Settings marked `live` must show up immediately — that is the whole point of
     *  the badge — so the panel hands changed values straight back to the contract. */
    onAppearanceChange(values) {
        this.appearance = Object.assign({}, this.appearance, values || {});
        const applied = applyAppearance(this.appearance);
        this.state.mzMode = applied["data-mz-mode"];
    }

    // ---- WORKSPACE RAIL --------------------------------------------------------
    /** Which rail destination is current. Register phases (orders / reservations) map
     *  onto their own rail keys so the highlight follows the screen. */
    get railActiveKey() {
        if (this.state.workspace) {
            return this.state.workspace;
        }
        const p = this.state.phase;
        if (p === "orders" || p === "completed") {
            return "orders";
        }
        if (p === "reservations") {
            return "book";
        }
        return "register";
    }

    /** The Register is already mounted, so a workspace switches in place here. */
    onRailSelect(key) {
        if (key === "orders") {
            this.closeWorkspace();
            this.openOrders();
        } else if (key === "book") {
            this.closeWorkspace();
            this.openHost();
        } else {
            this.openWorkspace(key);
        }
    }


    // ---- workspace modal host ----------------------------------------------------
    openWorkspace(key) {
        // The workspace view lives inside the MENU phase, so opening a rail destination
        // from Orders or Reservations left the phase behind and rendered nothing —
        // Settings looked dead when reached from those screens. Leaving the phase is
        // part of switching destination, not an afterthought.
        this.state.phase = "menu";
        this.state.completedView = null;
        this.state.workspace = key;
    }

    /** `/mezze/pos?ws=<key>` — how the rail reaches an in-Register workspace from a
     *  surface that cannot switch in place (Floor, Kitchen). */
    /** `ws_landing` decides where a bare /mezze/pos opens. It only applies when the
     *  URL names no destination, so the rail (which always names one, including
     *  `ws=register`) can still reach the till on a branch that lands elsewhere —
     *  a landing preference must never trap the operator away from the register. */
    _openWorkspaceFromUrl() {
        let key = null;
        try {
            key = new URLSearchParams(window.location.search).get("ws");
        } catch (e) {
            key = null;
        }
        if (!key) {
            const landing = (this.appearance || {}).ws_landing || "pos";
            if (landing === "floor" || landing === "kds") {
                const cfg = this.boot.config_id ? "?config_id=" + this.boot.config_id : "";
                window.location.replace("/mezze/" + landing + cfg);
                return;
            }
            if (landing === "manager" || landing === "reports") {
                this.openWorkspace(landing);
            }
            return;
        }
        if (key === "register") {
            return;   // explicit "the till, please" — overrides ws_landing
        }
        if (key === "orders") {
            this.openOrders();
        } else if (key === "book") {
            this.openHost();
        } else {
            this.openWorkspace(key);
        }
    }

    closeWorkspace() {
        this.state.workspace = null;
    }

    /** "<n> guests · <service>" under the table name, as the prototype shows. The
     *  service word is the order's REAL type; it is a label, not a selector — the
     *  Register has no setter for it, so no segmented control is offered. */
    get tableSubLabel() {
        const n = this.guestsCount;
        const guests = n === 1 ? _t("1 guest") : _t("%s guests", n);
        return guests + " · " + this.orderTypeLabel(this.isTableBound ? "dine_in" : "counter");
    }

    /** The bound customer's name, or null so the chip reads "Add customer". */
    get customerName() {
        const c = this.state.customer;
        return (c && c.name) || null;
    }

    startNewCustomer() {
        const p = this.state.customerPicker;
        if (!p) {
            return;
        }
        p.creating = true;
        p.error = "";
        // a cashier who searched for a guest and found nothing has already typed the
        // name — carry it over instead of making them type it twice
        p.newName = p.newName || p.query || "";
    }

    cancelNewCustomer() {
        const p = this.state.customerPicker;
        if (p) {
            p.creating = false;
            p.error = "";
        }
    }

    setNewCustomer(field, value) {
        const p = this.state.customerPicker;
        if (p) {
            p[field] = value;
        }
    }

    /** Create the guest, then attach them to the order straight away — that is why
     *  the cashier opened this. */
    async createCustomer() {
        const p = this.state.customerPicker;
        if (!p || p.busy || !p.newName.trim()) {
            return;
        }
        p.busy = true;
        p.error = "";
        try {
            const res = await this.api.call("/customer/create", {
                name: p.newName.trim(), phone: p.newPhone.trim(),
                config_id: this.boot.config_id,
            });
            if (res && res.customer) {
                await this.chooseCustomer(res.customer);
                p.creating = false;
                p.newName = "";
                p.newPhone = "";
                p.query = res.customer.name;
                p.results = [res.customer];
            }
        } catch (err) {
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
                return;
            }
            p.error = (err && err.error === "name_required")
                ? _t("A name is required.")
                : _t("Couldn’t create the customer.");
        } finally {
            p.busy = false;
        }
    }

    get noteTitle() {
        return _t("Kitchen note");
    }

    get saveNoteLabel() {
        return _t("Save note");
    }

    get newCustomerLabel() {
        return _t("New customer");
    }

    get custNameLabel() {
        return _t("Name");
    }

    get custPhoneLabel() {
        return _t("Phone (optional)");
    }

    get saveCustomerLabel() {
        return _t("Create & attach");
    }

    get cancelLabel() {
        return _t("Cancel");
    }

    get customerPickerTitle() {
        return _t("Customer");
    }

    get customerSearchLabel() {
        return _t("Search name or phone");
    }

    get searchingLabel() {
        return _t("Searching…");
    }

    get noCustomersLabel() {
        return _t("No customers");
    }

    get clearCustomerLabel() {
        return _t("Remove customer");
    }

    get doneLabel() {
        return _t("Done");
    }

    get closeLabel() {
        return _t("Close");
    }

    get backToRegisterLabel() {
        return _t("Back to Register");
    }

    /** Titles for the workspaces the Register can open. Kept beside the Register
     *  because it owns the heading; the rail owns the destinations. */
    /** Whether this branch keeps its Servers off the till (design v3
     *  `tillBarred`). A STAFFING policy read from settings, never a capability:
     *  the same person signed in as a cashier reaches the till normally. */
    get serversOffTill() {
        // From the cashier page's OWN boot payload (controllers/cashier.py), not
        // the /bootstrap API's config block — the Owl shell is served its own,
        // smaller boot object and never sees that one. A branch policy the
        // server states, not a preference the browser could flip.
        return !!((this.boot.branch || {}).servers_off_till);
    }

    /** The signed-in person's role, for the rail lock. Empty when nobody is
     *  identified — an unknown role is never barred, because locking a person
     *  the server cannot name would strand them with no way to explain it. */
    get myRole() {
        return (this.cart.cashier && this.cart.cashier.role)
            || (this.boot.cashier && this.boot.cashier.role) || "";
    }

    /** How the shell refuses a barred destination. */
    sayBarred(title, detail) {
        this.state.railNotice = { title, detail };
    }

    dismissRailNotice() {
        this.state.railNotice = null;
    }

    get workspaceTitle() {
        return {
            ops: _t("Live Ops"), queue: _t("Beverage Queue"), manager: _t("Manager"),
            reports: _t("Reports"), delivery: _t("Delivery"), hq: _t("HQ"),
            ck: _t("Central Kitchen"), settings: _t("Settings"),
            close: _t("End of day"), tips: _t("Tip pool"),
        }[this.state.workspace] || "";
    }

    /** True when the open workspace reads a real endpoint (see Workspace.SOURCES). */
    get workspaceHasSource() {
        return !!(this.state.workspace && Workspace.SOURCES[this.state.workspace]);
    }

    get workspacePendingLabel() {
        return _t("This workspace has no screen yet. Nothing is shown here rather than "
                  + "showing numbers that are not real.");
    }

    // R1B Undo toast (non-financial cart action only)
    get undoMsg() {
        return this.cart.undo ? _t("Removed %s", this.cart.undo.name) : "";
    }
    get undoLabel() {
        return _t("Undo");
    }
    onUndo() {
        this.order.undoRemove();
    }
    dismissUndo() {
        this.order.clearUndo();
    }

    // R1B Predictive Defaults (deterministic, reversible, never auto-confirms anything).
    // On initial load only: if this cashier has established favorites, open on the
    // Favorites view so their usuals are one tap away with zero navigation. The cashier
    // overrides instantly by tapping All or any category. No effect on a fresh cashier.
    _applyPredictiveDefaults() {
        if (this.state.activeCategory == null && this.hasFavorites) {
            this.state.activeCategory = this.FAV;
        }
    }

    get visibleProducts() {
        const cat = this.state.activeCategory;
        if (cat === this.FAV) {
            return this.favoriteProducts;
        }
        if (!cat) {
            return this.state.products;
        }
        return this.state.products.filter((p) => (p.pos_categ_ids || []).includes(cat));
    }

    // R1B keyboard productivity ---------------------------------------------
    // The grid shows the category selection UNLESS the cashier is searching, in which
    // case the query filters across the WHOLE catalog (a search is a "find it now"
    // action, not scoped to the active chip). Pure filterProducts keeps it deterministic.
    get filteredProducts() {
        if (this.state.search.trim()) {
            return filterProducts(this.state.products, this.state.search);
        }
        return this.visibleProducts;
    }

    get isSearching() {
        return !!this.state.search.trim();
    }

    // The product id currently highlighted for a keyboard Enter/add (search only).
    get highlightId() {
        if (!this.isSearching) {
            return null;
        }
        const list = this.filteredProducts;
        return list.length ? list[clampIndex(this.state.searchIndex, list.length)].id : null;
    }

    get kbdHint() {
        return _t("/ search · ↑↓ move · ↵ add · Ctrl+↵ / F2 charge · Esc back");
    }

    onSearchInput(value) {
        this.state.search = value || "";
        this.state.searchIndex = 0; // any edit re-anchors the highlight to the top match
    }

    clearSearch() {
        this.state.search = "";
        this.state.searchIndex = 0;
        if (this.searchRef.el) {
            this.searchRef.el.value = "";
        }
    }

    focusSearch() {
        if (this.searchRef.el) {
            this.searchRef.el.focus();
            this.searchRef.el.select();
        }
    }

    // Move the highlight within the current results, clamped (no wrap).
    moveHighlight(delta) {
        const len = this.filteredProducts.length;
        this.state.searchIndex = clampIndex(this.state.searchIndex, len, delta);
    }

    // Add the highlighted result to the cart (keeps the search open for rapid multi-add).
    addHighlighted() {
        const list = this.filteredProducts;
        if (!list.length) {
            return false;
        }
        const p = list[clampIndex(this.state.searchIndex, list.length)];
        this.order.addProduct(p);
        return true;
    }

    _isTyping(el) {
        if (!el) {
            return false;
        }
        const tag = el.tagName;
        return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
    }

    // Central keyboard dispatcher. DELIBERATELY NON-FINANCIAL: it can focus/search,
    // move the highlight, add a line, OPEN the payment screen, and go back — nothing
    // here submits a tender, applies a refund/void, or approves a manager override.
    /** A barcode scanner is a keyboard that types very fast and presses Enter.
     *
     *  Nothing here listens for a device — there is no device to listen for. The
     *  only thing separating a scan from a cashier typing is SPEED, so the buffer
     *  resets on any keystroke slower than a scanner can produce. Without that, a
     *  cashier typing a number into the search box would ring up a product. */
    _scanKey(ev) {
        if (this.state.phase !== "menu") {
            return false;
        }
        const now = Date.now();
        const gap = this._lastKeyAt ? now - this._lastKeyAt : null;
        this._lastKeyAt = now;
        const { buffer, code } = feedScan(this.state.scanBuffer, ev.key, gap);
        this.state.scanBuffer = buffer;
        if (!code) {
            return false;
        }
        const product = productForScan(this.state.products, code);
        if (!product) {
            this.state.actionNote = _t("No product matches the code %s.", code);
            return true;
        }
        if (product.available === false) {
            this.state.actionNote = _t("%s is off the menu right now.", product.name);
            return true;
        }
        this.onSelectProduct(product);
        return true;
    }

    handleKey(ev) {
        if (this._scanKey(ev)) {
            ev.preventDefault();
            return;
        }
        if (ev.ctrlKey && ev.key === "Enter") {
            // Open payment from anywhere in the menu (safe navigation only).
            if (this.state.phase === "menu") {
                ev.preventDefault();
                this.goToPayment();
            }
            return;
        }
        if (ev.key === "F2") {
            if (this.state.phase === "menu") {
                ev.preventDefault();
                this.goToPayment();
            }
            return;
        }
        if (ev.key === "Escape") {
            if (this.state.phase === "menu") {
                if (this.isSearching || (this.searchRef.el && document.activeElement === this.searchRef.el)) {
                    ev.preventDefault();
                    this.clearSearch();
                    if (this.searchRef.el) {
                        this.searchRef.el.blur();
                    }
                }
            } else if (this.state.phase === "payment" && this._noPaymentModal()) {
                // Back to the menu ONLY when no sub-modal is open — a modal owns its own
                // Cancel so a global Esc never silently dismisses an approval/tender flow.
                ev.preventDefault();
                this.backToMenu();
            }
            return;
        }
        if (this.state.phase !== "menu") {
            return;
        }
        const searchFocused = this.searchRef.el && document.activeElement === this.searchRef.el;
        if (ev.key === "/") {
            if (!this._isTyping(ev.target)) {
                ev.preventDefault();
                this.focusSearch();
            }
            return;
        }
        // The remaining keys only steer the search results, and only while searching.
        if (!searchFocused || !this.isSearching) {
            return;
        }
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            this.moveHighlight(1);
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            this.moveHighlight(-1);
        } else if (ev.key === "Enter") {
            ev.preventDefault();
            // A HELD Enter must not burst-add: one deliberate press = one line. OS key-repeat
            // (ev.repeat) is ignored, while distinct presses (repeat=false) still add rapidly.
            if (!ev.repeat) {
                this.addHighlighted();
            }
        }
    }

    // True when the payment screen has no blocking sub-flow open (so Esc may go back).
    _noPaymentModal() {
        const s = this.state;
        return !s.warn && !s.managerReq && !s.creditWarn && !s.creditManager
            && !s.customerPicker && !s.terminal && !s.cashmachine && !s.qr;
    }

    // P3F — identity of the currently-open host/confirm modal (or "" if none). Drives
    // the dialog focus effect: a change here means a modal opened or closed.
    _hostModalKey() {
        const s = this.state;
        if (s.moveConfirm) return "move";
        if (s.recallConfirm) return "recall";
        if (s.assignPicker) return "assign";
        if (s.resForm) return "resform";
        if (s.wlForm) return "wlform";
        if (s.hostConfirm) return "hostconfirm";
        return "";
    }

    /** Record the version the server just reported for this check.
     *
     *  Every mutating route now answers with `revision`. Holding it is what lets
     *  the NEXT write say which version it is acting on — without this the
     *  stale-write guard is dormant, because `_assert_revision` treats a missing
     *  `expected` as "this caller does not track revisions" and lets it through.
     *  That is right for the kiosk and for an aggregator push; it is wrong for a
     *  till with the check open on screen.
     */
    _noteFromServer(res, uuid) {
        if (res && res.revision !== undefined && res.revision !== null) {
            this.state.orderRevision = res.revision;
            this.state.orderRevisionUuid = uuid || res.uuid || this.state.orderUuid || null;
        }
        if (res && res.edits_refused !== undefined) {
            // The server kept the check it already had and dropped the cart we
            // sent. It answers ok/duplicate while doing so, so without this the
            // till reports success on a write that was refused and the cashier
            // never learns their edit did not land.
            this.state.editLock = res.edits_refused
                ? { reason: res.edits_refused, paid: res.tendered_amount || 0 }
                : null;
        }
        return res;
    }

    /** The design locks a line that is "covered by a recorded tender" and says so
     *  in the order column. Our refusal is order-wide rather than per line — the
     *  server declines the whole cart, not one row — so the notice belongs to the
     *  check, which is also the more truthful place for it.
     */
    get editLockMessage() {
        const l = this.state.editLock;
        if (!l) {
            return "";
        }
        if (l.reason === "tendered") {
            return _t("Covered by a recorded tender. This check can no longer be edited here.");
        }
        if (l.reason === "settled") {
            return _t("This check is already settled, so it can no longer be edited.");
        }
        return _t("This check has been split, so its items are managed on the split checks.");
    }

    /** The version this terminal believes it holds OF THIS ORDER.
     *
     *  Bound to the uuid it was read from, because a revision is only meaningful
     *  for the order it came from and the till does not always keep one: the
     *  charge path mints a fresh uuid for every counter sale, and mints another
     *  when it finds it has been handed a uuid that is already settled. Carrying
     *  a number across that boundary would make the till claim a version of an
     *  order it has never read — a WRONG claim, which is worse than none: the
     *  server would refuse a write that was in fact perfectly current.
     *
     *  Returns `undefined` (not null) so the key drops out of the JSON body
     *  entirely when there is no claim to make.
     */
    _revisionClaimFor(uuid) {
        if (this.state.orderRevision === null || !uuid) {
            return undefined;
        }
        return this.state.orderRevisionUuid === uuid ? this.state.orderRevision : undefined;
    }

    _failFromError(err) {
        if (err && err.kind === "auth") {
            this.state.phase = "auth_required";
            return true;
        }
        if (err && err.error === "stale_revision") {
            // Another terminal moved this check. NOT an error screen: on a busy
            // floor this is a normal Tuesday, and the cashier needs to see the
            // difference and choose — never a silent redraw over their work.
            this._enterConflict(err.data || {});
            return true;
        }
        return false;
    }

    /** Hold both sides of a collision so the banner can name it.
     *
     *  "theirs" is what the server says the check is now; "mine" is the cart in
     *  front of the cashier. The design states the difference in words — "Kofta
     *  quantity differs (yours 4 · theirs 3)" — so this computes it rather than
     *  leaving the person to spot it.
     */
    _enterConflict(data) {
        const theirs = data.lines || [];
        const mine = this.order.toSyncLines();
        const byProduct = (rows, qtyKey) => {
            const m = new Map();
            for (const r of rows) {
                const id = r.product_id;
                m.set(id, (m.get(id) || 0) + Number(r[qtyKey] || 0));
            }
            return m;
        };
        const t = byProduct(theirs, "qty");
        const y = byProduct(mine, "qty");
        const names = new Map(theirs.map((r) => [r.product_id, r.name]));
        const diffs = [];
        for (const id of new Set([...t.keys(), ...y.keys()])) {
            const mineQty = y.get(id) || 0;
            const theirsQty = t.get(id) || 0;
            if (mineQty !== theirsQty) {
                diffs.push({
                    product_id: id,
                    name: names.get(id) || this._productName(id),
                    mine: mineQty,
                    theirs: theirsQty,
                });
            }
        }
        this.state.conflict = {
            revision: data.revision,
            theirs,
            diffs,
            // The first difference is what the banner reads out; the rest are
            // reachable through Review.
            headline: diffs.length
                ? _t("%(name)s quantity differs (yours %(mine)s · theirs %(theirs)s).",
                     { name: diffs[0].name, mine: diffs[0].mine, theirs: diffs[0].theirs })
                : _t("This check changed on another terminal."),
        };
    }

    get hasConflict() {
        return !!this.state.conflict;
    }

    get conflictTitle() {
        return _t("Order updated on another terminal");
    }

    /** The catalogue name for a product id, from the grid's own product list. */
    _productName(id) {
        const p = (this.state.products || []).find((x) => x.id === id);
        return (p && p.name) || _t("An item");
    }

    /** Keep the cashier's cart: adopt the current revision so the NEXT write is
     *  accepted, and clear the banner. The cart is untouched — the cashier's
     *  quantities are the ones that will be sent, and they retry the action they
     *  were doing (split / send / park) themselves.
     *
     *  Deliberately does not re-send here: there is no background draft loop in
     *  this Register, so re-sending would fire an action the cashier did not ask
     *  for a second time. */
    keepMine() {
        const c = this.state.conflict;
        if (!c) {
            return;
        }
        this.state.orderRevision = c.revision;
        this.state.orderRevisionUuid = this.state.orderUuid;
        this.state.conflict = null;
        this.state.conflictReview = false;
    }

    /** Keep the other terminal's version: rebuild the cart from what the check
     *  now IS. The cashier's own edits are discarded, which is exactly why this
     *  is a deliberate choice and never the default. */
    keepTheirs() {
        const c = this.state.conflict;
        if (!c) {
            return;
        }
        const byId = new Map((this.state.products || []).map((p) => [p.id, p]));
        this.order.clear();
        for (const row of c.theirs) {
            const product = byId.get(row.product_id);
            if (!product) {
                // A line whose product is not on this till's menu (another branch's
                // item, or one withdrawn since). Skipped rather than invented — a
                // cart must not contain something the grid cannot price.
                continue;
            }
            this.order.addProduct(product, { note: row.note || "" });
            const line = this.order.lines[this.order.lines.length - 1];
            if (line && Number(row.qty) !== 1) {
                this.order.setQty(line, Number(row.qty));
            }
        }
        this.state.orderRevision = c.revision;
        this.state.orderRevisionUuid = this.state.orderUuid;
        this.state.conflict = null;
        this.state.conflictReview = false;
    }

    /** Every difference, not just the headline the banner reads out. */
    toggleConflictReview() {
        this.state.conflictReview = !this.state.conflictReview;
    }

    // ---- bootstrap / catalog ----------------------------------------------
    async bootstrap() {
        if (!this.boot || this.boot.ok === false) {
            this.state.phase = "error";
            this.state.errorMsg = this.boot && this.boot.error === "no_pos_config"
                ? _t("POS is not ready for sales")
                : _t("Authentication required");
            if (this.boot && this.boot.error === "boot_missing") {
                this.state.phase = "auth_required";
            }
            return;
        }
        this.state.phase = "booting";
        try {
            const data = await this.api.call("/bootstrap", { config_id: this.boot.config_id });
            this.state.sessionId = data.session_id;
            // Scope the crash-safe draft to THIS branch and THIS shift before
            // anything can be added to the cart.
            this.order.setDraftScope(this.boot.config_id, data.session_id,
                                     () => this.state.orderUuid);
            // Feed the customer display, but only where one has been opened.
            this.state.hasCfd = !!(data.config || {}).has_cfd;
            if (this.state.hasCfd) {
                this.order.onChanged = () => this.pushCfd("building");
            }
            this.state.categories = data.categories || [];
            this.state.products = (data.products || []).map((p) => ({
                id: p.id,
                name: p.name,
                list_price: p.list_price,
                // Both, from the server. The toggle picks; it never computes.
                price_excl: p.price_excl,
                price_incl: p.price_incl,
                tracking: p.tracking || "none",
                available: p.available !== false,
                has_image: !!p.has_image,
                pos_categ_ids: p.pos_categ_ids || [],
                // CONV-3: /bootstrap has always shipped each product's real POS-time
                // attribute groups; this line used to drop them, so the till could not
                // sell a burger without onions at all. Same payload, same shape and the
                // same rules the lane uses — one configurator contract, not two.
                modifiers: p.modifiers || [], combos: p.combos || [], is_combo: !!p.is_combo,
                // /bootstrap has always sent these two and this map used to drop
                // them, which is the whole reason the till could not scan: the data
                // arrived and was thrown away before anything could match on it.
                barcode: p.barcode || "",
                default_code: p.default_code || "",
                to_weight: !!p.to_weight,
                uom_name: p.uom_name || "",
            }));
            // Core switches the branch set that this till must honour.
            this.state.priceControl = !!(data.config || {}).restrict_price_control;
            // Whether this branch has a scale to ask. Told at boot, so a weighed
            // line never offers a button that answers "no scale".
            this.state.hasScale = !!(data.config || {}).has_scale;
            // The branch's own Tax Display setting is the STARTING point, not a
            // permanent one: a cashier quoting a guest may need the other figure for
            // one order, which is exactly what core's Actions → Tax is for.
            this.state.taxDisplay = (data.config || {}).iface_tax_included || "total";
            const cfg = data.config || {};
            this.state.fastPayment = cfg.use_fast_payment
                ? (cfg.fast_payment_method_ids || [])
                : [];
            this.state.presets = cfg.presets || [];
            // Start on the branch's default so an order always HAS an order type,
            // rather than acquiring one only if the cashier remembers to choose.
            const fallback = (cfg.presets || []).find((p) => p.default);
            this.state.presetId = fallback ? fallback.id : null;
            this.order.setTaxDisplay(this.state.taxDisplay);
            this.state.pricelists = data.pricelists || [];
            this.state.fiscalPositions = data.fiscal_positions || [];
            this.state.notePresets = data.note_presets || [];
            this.state.methods = (data.payment_methods || []).map((m) => ({
                id: m.id,
                name: m.name,
                mezze_mode: m.mezze_mode || (m.is_cash_count ? "cash" : "manual"),
                mezze_terminal_provider: m.mezze_terminal_provider || "",
                is_cash_count: !!m.is_cash_count,
                device_policy: m.device_policy || "disabled",
                reference_policy: m.reference_policy || "disabled",
                duplicate_policy: m.duplicate_policy || "warn",
                allow_partial: m.mezze_allow_partial !== false,
                allow_mixed: m.mezze_allow_mixed !== false,
                manager_approval: !!m.mezze_manager_approval,
            }));
            this._applyPredictiveDefaults();
            // R2A CP5 — table-bound Register: resume the authoritative open order (if any)
            // and pin a stable order uuid so re-opening/adding never spawns a duplicate.
            await this._initTableOrder();
            this._recoverDraft();
            this.state.phase = "menu";
            this._applyEntryView();
            this._openWorkspaceFromUrl();
        } catch (err) {
            if (!this._failFromError(err)) {
                this.state.phase = "error";
                this.state.errorMsg = err && err.kind === "network"
                    ? _t("Local Mezze server unavailable") : (err && err.message) || _t("Unable to load menu");
            }
        }
    }

    /** Put back what a crash took.
     *
     *  A cart lives in memory, so a tablet whose OS reclaims the tab, a browser that
     *  falls over, or a cashier who hits refresh loses the order with a guest at the
     *  counter. Park exists, but Park is a decision somebody has to make BEFORE the
     *  thing they could not predict.
     *
     *  This restores INTENT, never money: the recovered lines are re-synced and the
     *  server prices them exactly as it would have the first time. It also refuses to
     *  overwrite a cart that already has something in it — a table's authoritative
     *  order has just been loaded above, and that is the truth, not this.
     */
    _recoverDraft() {
        if (!this.order.isEmpty) {
            return;   // an authoritative order won; the draft is stale by definition
        }
        const draft = this.order.readDraft();
        if (!draft) {
            return;
        }
        const dropped = this.order.restoreDraft(draft, this.state.products);
        if (this.order.isEmpty) {
            this.order.forgetDraft();
            return;
        }
        // The SAME uuid, so the recovered cart updates the draft the server already
        // has instead of becoming a second bill for one guest.
        if (draft.uuid) {
            this.state.orderUuid = draft.uuid;
        }
        // Said out loud. A cart that reappears without explanation is one a cashier
        // has to audit against the guest in front of them, and silently handing back
        // a SHORTER order than was rung up is worse than not recovering it at all.
        this.state.recovered = dropped
            ? _t("Recovered this order after a restart. %s item(s) are no longer on the menu and were left out — check before charging.", dropped)
            : _t("Recovered this order after a restart.");
    }

    dismissRecovered() {
        this.state.recovered = "";
    }

    // ---- R2A CP5: table-bound Register --------------------------------------
    get isTableBound() {
        return !!(this.state.table && !this.state.table.error);
    }
    get tableInvalid() {
        return !!(this.state.table && this.state.table.error);
    }
    get tableLabel() {
        const t = this.state.table;
        if (!this.isTableBound) {
            return "";
        }
        return (t.floor ? t.floor + " · " : "") + _t("T%s", t.name);
    }
    get guestsLabel() {
        const g = this.isTableBound ? (this.state.table.guests || 0) : 0;
        return g > 0 ? _t("%s guests", g) : "";
    }
    get floorUrl() {
        const cfg = this.boot.config_id ? `?config_id=${this.boot.config_id}` : "";
        return "/mezze/floor" + cfg;
    }

    // Resume the authoritative open order for a table-bound Register (or pin a fresh
    // stable uuid). The server is the source of truth for WHICH order sits on the
    // table; the browser only mirrors it. Opening never creates/mutates an order.
    async _initTableOrder() {
        const t = this.state.table;
        if (!this.isTableBound) {
            return; // counter mode, or invalid table (surfaced in the UI)
        }
        if (t.order_uuid) {
            this.state.orderUuid = t.order_uuid;
            const res = await this.api.call("/orders/get", { uuid: t.order_uuid });
            this._loadOrderLines(res.lines);
            if (res.guests) {
                t.guests = res.guests;
            }
        } else {
            // fresh table — ONE stable uuid reused for send/charge (no duplicate drafts)
            this.state.orderUuid = makeUuid();
        }
    }

    // Persist the current cart to the table as a DRAFT order (the existing
    // /orders/sync draft path) so the floor shows it occupied — WITHOUT taking
    // payment. Reuses the stable table uuid, so repeated sends update ONE order.
    async sendToTable() {
        if (!this.isTableBound || this.order.isEmpty || this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        this.state.tenderError = "";
        try {
            const res = await this.api.call("/orders/sync", {
                uuid: this.state.orderUuid,
                session_id: this.state.sessionId,
                lines: this.order.toSyncLines(),
                table_id: this.state.table.id,
                draft: true,
                expected_revision: this._revisionClaimFor(this.state.orderUuid),
            });
            // reflect the authoritative uuid (idempotent) so a second send is the same order
            if (res.uuid) {
                this.state.orderUuid = res.uuid;
                this.state.table.order_uuid = res.uuid;
            }
            this._noteFromServer(res, this.state.orderUuid);
            this.state.sentOk = true;
        } catch (err) {
            if (!this._failFromError(err)) {
                this.state.tenderError = err && err.kind === "network"
                    ? _t("Local Mezze server unavailable — not saved.")
                    : (err && err.message) || _t("Could not save to the table.");
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    // ---- R2A CP9: Orders workspace (Open | Parked | Completed + recall) -----
    // Rebuild the editable cart from an authoritative order's lines. Single seam
    // reused by table resume (CP5) and Orders recall (CP9). Never mutates the order.
    /** Rebuild the cart from an authoritative order, LOSSLESSLY.
     *
     *  This used to restore product, quantity and price only. Because /orders/sync
     *  replaces an order's lines wholesale, the next save then wrote those bare
     *  lines back — so resuming a table silently destroyed its modifiers, notes and
     *  combo structure on the server. A configured line survived being looked at
     *  exactly once. */
    _loadOrderLines(lines) {
        this.order.clear();
        // A reward is money, not an item the cashier can edit — it is re-derived by
        // the server, so it never becomes a cart line.
        const rows = (lines || []).filter((l) => !l.is_reward_line);
        // A combo arrives as a PARENT line plus one child line per pick. The cart
        // holds it as ONE line whose identity carries the picks, so gather the
        // children onto their parent and never add them as lines of their own.
        const picksOf = new Map();
        for (const l of rows) {
            if (l.combo_parent_id) {
                const arr = picksOf.get(l.combo_parent_id) || [];
                if (l.combo_item_id) {
                    arr.push(l.combo_item_id);
                }
                picksOf.set(l.combo_parent_id, arr);
            }
        }
        for (const l of rows) {
            if (l.combo_parent_id) {
                continue;                       // already gathered onto its parent
            }
            const product = this.state.products.find((p) => p.id === l.product_id)
                || { id: l.product_id, name: l.name, list_price: l.price_unit, available: true };
            // A weighed line's quantity is a MEASUREMENT. Rounding it to a whole
            // number turned 0.4 kg into 0 and then into 1 — the line came back from
            // the server heavier than it was sold.
            const weighed = !!product.to_weight;
            const n = weighed ? 1 : Math.max(1, Math.round(l.qty || 1));
            // Carry the server's EFFECTIVE price. A comp is stored as a 100% discount
            // rather than a zeroed price_unit, so reading price_unit alone rebuilt the
            // line at full price and overstated the total.
            const discount = typeof l.discount === "number" ? l.discount : 0;
            const unitPrice = typeof l.price_unit === "number"
                ? l.price_unit * (1 - discount / 100)
                : undefined;
            const comped = discount >= 100;
            // "Burger (no onion, extra cheese)" — the readable choice exactly as the
            // server composed it, so the sub-line reads the same after a resume.
            let modifiers = [];
            const m = /\(([^)]*)\)\s*$/.exec(l.full_name || "");
            if (m) {
                modifiers = m[1].split(",").map((s) => s.trim()).filter(Boolean);
            }
            const opts = {
                noBump: true, unitPrice, comped,
                note: l.note || "",
                attributeValueIds: (l.attribute_value_ids || []).slice(),
                priceExtra: l.price_extra || 0,
                combo: (picksOf.get(l.id) || []).slice(),
                modifiers,
            };
            for (let i = 0; i < n; i++) {
                this.order.addProduct(product, opts);
            }
            if (weighed) {
                // restore the measured quantity the count-based loop cannot express
                const line = this.order.state.lines[this.order.state.lines.length - 1];
                if (line) {
                    line.qty = l.qty;
                }
            }
        }
    }

    get ordersState() {
        return this.state.orders || { filter: "open", query: "", rows: [], loading: false, error: "", hasMore: false, offset: 0 };
    }

    // F3 — NAVIGATION ONLY. The Floor links to the Register's Orders/Reservations
    // phases with ?view=. This runs once, after a SUCCESSFUL boot, and only opens a
    // workspace the nav can already open by click. A table-bound Register always wins
    // (that entry carries an order context and must land on the Register itself), and
    // anything other than the two known values is ignored.
    _applyEntryView() {
        if (this.isTableBound) {
            return;
        }
        let view = "";
        try {
            view = new URLSearchParams(window.location.search).get("view") || "";
        } catch {
            return;
        }
        if (view === "orders") {
            this.openOrders();
        } else if (view === "reservations") {
            this.openHost();
        }
    }

    openOrders() {
        if (!this.state.orders) {
            this.state.orders = { filter: "open", query: "", rows: [], loading: false, error: "", hasMore: false, offset: 0 };
        }
        this.state.phase = "orders";
        this.loadOrders(true);
    }

    backToRegister() {
        this.state.phase = "menu";
    }

    async loadOrders(reset) {
        const o = this.state.orders;
        if (!o) {
            return;
        }
        if (reset) {
            o.offset = 0;
            o.rows = [];
        }
        o.loading = true;
        o.error = "";
        try {
            const res = await this.api.call("/orders/list", {
                filter: o.filter, query: o.query || "", limit: 25, offset: o.offset,
            });
            const rows = res.orders || [];
            o.rows = reset ? rows : o.rows.concat(rows);
            o.hasMore = !!res.hasMore || !!res.has_more;
        } catch (err) {
            o.error = err && err.kind === "network"
                ? _t("Couldn’t load orders — check the connection.")
                : _t("Couldn’t load orders.");
        } finally {
            o.loading = false;
        }
    }

    setOrdersFilter(filter) {
        const o = this.state.orders;
        if (!o || o.filter === filter) {
            return;
        }
        o.filter = filter;
        this.loadOrders(true);
    }

    onOrdersSearch(ev) {
        const o = this.state.orders;
        if (!o) {
            return;
        }
        o.query = (ev && ev.target && ev.target.value) || "";
        if (this._ordersSearchTimer) {
            window.clearTimeout(this._ordersSearchTimer);
        }
        this._ordersSearchTimer = window.setTimeout(() => this.loadOrders(true), 250);
    }

    loadMoreOrders() {
        const o = this.state.orders;
        if (!o || o.loading || !o.hasMore) {
            return;
        }
        o.offset = (o.offset || 0) + 25;
        this.loadOrders(false);
    }

    // Recall dispatch: a completed order opens READ-ONLY; a draft is recalled into
    // the editable Register. A non-empty current order is never silently discarded.
    onRecall(row) {
        if (!row || !row.uuid) {
            return;
        }
        if (row.completed) {
            this.openCompleted(row.uuid);
            return;
        }
        const sameOrder = this.state.orderUuid && this.state.orderUuid === row.uuid;
        if (!this.order.isEmpty && !sameOrder) {
            // guarantee: current work is preserved, not lost — offer Park & open
            this.state.recallConfirm = { target: row };
            return;
        }
        this._doRecall(row);
    }

    cancelRecall() {
        this.state.recallConfirm = null;
    }

    async confirmRecall() {
        const rc = this.state.recallConfirm;
        if (!rc) {
            return;
        }
        this.state.recallConfirm = null;
        const parked = await this.parkCurrent();          // persist + tag current order
        if (parked) {
            await this._doRecall(rc.target);
        }
    }

    async _doRecall(row) {
        if (this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        try {
            const res = await this.api.call("/orders/get", { uuid: row.uuid });
            // server truth wins: a stale row that was completed elsewhere must NEVER
            // reopen as an editable draft — fall through to the read-only view.
            if (!res || res.ok === false) {
                this.state.orders && (this.state.orders.error = _t("That order is no longer available."));
                return;
            }
            if (res.state && res.state !== "draft") {
                this._showCompleted(res);
                this.loadOrders(true);                    // refresh the (stale) list
                return;
            }
            this._loadOrderLines(res.lines);
            this.state.orderUuid = res.uuid;
            // restore table context (CP6/CP7 rules stay authoritative) or counter mode
            if (res.table_id) {
                this.state.table = {
                    id: res.table_id, name: res.table, floor: res.floor,
                    order_uuid: res.uuid, guests: res.guests || 0,
                };
            } else {
                this.state.table = null;
            }
            this.state.customer = res.partner ? { id: res.partner.id, name: res.partner.name } : null;
            // a recalled order is now active work — clear the parked tag (best effort)
            if (row.parked) {
                this.api.call("/orders/park", { uuid: res.uuid, parked: false }).catch(() => {});
            }
            this.state.recallConfirm = null;
            this.state.completedView = null;
            this.state.phase = "menu";
        } catch (err) {
            if (!this._failFromError(err)) {
                this.state.orders && (this.state.orders.error = _t("Couldn’t open that order."));
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    // Park the CURRENT order: persist the latest cart as a draft, TAG it parked, and
    // return the Register to a clean new-order state. Never pays/cancels/unlinks, and
    // a table-bound order keeps its table (the floor stays occupied).
    async parkCurrent() {
        if (this.order.isEmpty) {
            return true;                                   // nothing to park
        }
        this.state.inFlight = true;
        this.state.tenderError = "";
        try {
            const uuid = this.state.orderUuid || makeUuid();
            const body = {
                uuid, session_id: this.state.sessionId,
                lines: this.order.toSyncLines(), draft: true,
                expected_revision: this._revisionClaimFor(uuid),
            };
            if (this.isTableBound) {
                body.table_id = this.state.table.id;
            }
            const res = await this.api.call("/orders/sync", body);
            this._noteFromServer(res, uuid);
            const finalUuid = res.uuid || uuid;
            await this.api.call("/orders/park", { uuid: finalUuid, parked: true });
            // clean slate for the next order (fresh uuid/table/customer)
            this.order.clear();
            this.state.orderUuid = null;
            // the claim belonged to that uuid; it means nothing for the next order
            this.state.orderRevision = null;
            this.state.orderRevisionUuid = null;
            this.state.editLock = null;
            this.state.table = null;
            this.state.customer = null;
            this.state.payment = null;
            this.state.snapshot = null;
            return true;
        } catch (err) {
            if (!this._failFromError(err)) {
                this.state.tenderError = err && err.kind === "network"
                    ? _t("Local Mezze server unavailable — not parked.")
                    : _t("Couldn’t park the order.");
            }
            return false;
        } finally {
            this.state.inFlight = false;
        }
    }

    get canPark() {
        // reactive cart read (see canAssign) so the Park action appears/disappears live.
        return this.cart.lines.length > 0 && this.state.phase === "menu";
    }

    async parkAndNew() {
        const ok = await this.parkCurrent();
        if (ok) {
            this.state.phase = "menu";
        }
    }

    // ---- CP9 completed order — READ-ONLY view (never editable/resurrectable) --
    async openCompleted(uuid) {
        if (this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        try {
            const res = await this.api.call("/orders/get", { uuid });
            if (res && res.ok !== false) {
                this._showCompleted(res);
            }
        } catch (err) {
            this._failFromError(err);
        } finally {
            this.state.inFlight = false;
        }
    }

    _showCompleted(res) {
        this.state.completedView = {
            uuid: res.uuid, pos_reference: res.pos_reference, state: res.state,
            order_type: res.order_type, table: res.table, floor: res.floor,
            guests: res.guests, partner: res.partner,
            amount_total: res.amount_total, amount_paid: res.amount_paid,
            date_order: res.date_order,
            lines: (res.lines || []).map((l) => ({
                name: l.name, qty: l.qty, price_unit: l.price_unit,
            })),
        };
        this.state.phase = "completed";
    }

    closeCompleted() {
        this.state.completedView = null;
        this.state.phase = "orders";
    }

    orderTypeLabel(t) {
        return { dine_in: _t("Dine-in"), takeaway: _t("Takeaway"),
                 delivery: _t("Delivery"), counter: _t("Counter") }[t] || _t("Order");
    }

    // FINAL-C2: these two sentences were split across a t-esc in the template, so the
    // fragments could never be translated grammatically (Arabic word order differs).
    // One string + one placeholder — the pattern already used elsewhere in this file.
    get assignPickerTitle() {
        const mode = this.state.assignPicker && this.state.assignPicker.mode;
        if (mode === "move") {
            // FINAL-C2: was "Move <table> to…" split across a t-esc — untranslatable.
            return _t("Move %s to…", this.tableLabel);
        }
        return mode === "seat" ? _t("Seat at…") : _t("Assign table");
    }

    get recallConfirmSay() {
        return _t("Your current order will be parked so nothing is lost, then %s will open.",
                  this.recallTargetLabel);
    }
    get moveConfirmSay() {
        const c = this.state.moveConfirm;
        const dest = (c && c.dest && c.dest.name) || "";
        return _t("Move this order and its kitchen tickets to T%s.", dest);
    }

    get recallTargetLabel() {
        const t = this.state.recallConfirm && this.state.recallConfirm.target;
        if (!t) {
            return _t("the order");
        }
        return t.table ? _t("T%s", t.table) : (t.pos_reference || this.orderTypeLabel(t.order_type));
    }

    get ordersEmptyLabel() {
        const o = this.state.orders;
        if (o && o.query) {
            return _t("No results for “%s”", o.query);
        }
        const f = o && o.filter;
        if (f === "parked") {
            return _t("No parked orders");
        }
        if (f === "completed") {
            return _t("No completed orders");
        }
        return _t("No open orders");
    }

    // =====================================================================
    // R2A CP10 — Reservations + Waitlist (host) workspace
    //
    // Reuses the canonical backend FSMs (reservations/state, waitlist/state) and the
    // SAME table picker as assign/move. Seating attaches exactly one order via the
    // server; the frontend never creates a second order or a second state machine.
    // =====================================================================
    get hostState() {
        return this.state.host || { tab: "reservations", dateOffset: 0, query: "",
            resRows: [], wlRows: [], wlStats: null, loading: false, error: "" };
    }

    openHost() {
        if (!this.state.host) {
            this.state.host = { tab: "reservations", dateOffset: 0, query: "",
                resRows: [], wlRows: [], wlStats: null, loading: false, error: "" };
        }
        this.state.phase = "reservations";
        this.loadHost();
    }

    setHostTab(tab) {
        const h = this.state.host;
        if (!h || h.tab === tab) {
            return;
        }
        h.tab = tab;
        this.loadHost();
    }

    setHostDate(offset) {
        const h = this.state.host;
        if (!h) {
            return;
        }
        h.dateOffset = offset;
        h.query = "";
        this.loadHost();
    }

    onHostSearch(ev) {
        const h = this.state.host;
        if (!h) {
            return;
        }
        h.query = (ev && ev.target && ev.target.value) || "";
        if (this._hostSearchTimer) {
            window.clearTimeout(this._hostSearchTimer);
        }
        this._hostSearchTimer = window.setTimeout(() => this.loadHost(), 250);
    }

    get hostDateLabel() {
        return { "-1": _t("Yesterday"), "0": _t("Today"), "1": _t("Tomorrow") }[
            String(this.hostState.dateOffset)] || _t("Today");
    }

    _hostDateParam() {
        // server expects a YYYY-MM-DD 'date' (its own tz day); derive from offset.
        const d = new Date();
        d.setDate(d.getDate() + (this.hostState.dateOffset || 0));
        const p = (n) => String(n).padStart(2, "0");
        return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
    }

    async loadHost() {
        const h = this.state.host;
        if (!h) {
            return;
        }
        h.loading = true;
        h.error = "";
        try {
            if (h.tab === "waitlist") {
                const res = await this.api.call("/waitlist/list", {
                    config_id: this.boot.config_id });
                h.wlRows = res.items || [];
                h.wlStats = { waiting: res.waiting || 0, covers: res.covers || 0, quote: res.quote || 0 };
            } else {
                const params = { config_id: this.boot.config_id };
                if (h.query && h.query.trim()) {
                    params.q = h.query.trim();
                } else {
                    params.date = this._hostDateParam();
                }
                const res = await this.api.call("/reservations/list", params);
                h.resRows = res.reservations || [];
            }
        } catch (err) {
            h.error = err && err.kind === "network"
                ? _t("Couldn’t load — check the connection.")
                : (h.tab === "waitlist" ? _t("Couldn’t load waitlist.") : _t("Couldn’t load reservations."));
        } finally {
            h.loading = false;
        }
    }

    get hostEmptyLabel() {
        const h = this.state.host;
        if (h && h.query) {
            return _t("No results for “%s”", h.query);
        }
        return h && h.tab === "waitlist" ? _t("No guests waiting") : _t("No reservations today");
    }

    // Contextually-valid actions for a reservation card, derived from the canonical
    // FSM (mirrors reservation.py RES_TRANSITIONS). Server stays authoritative — an
    // illegal action is still rejected server-side; this only shapes the UI.
    resActions(r) {
        const s = r.state;
        const A = (action, label, kind) => ({ action, label, kind });
        if (s === "booked") {
            return [A("confirm", _t("Confirm"), "primary"), A("arrive", _t("Arrived"), "secondary"),
                    A("no_show", _t("No-show"), "tertiary"), A("cancel", _t("Cancel"), "tertiary")];
        }
        if (s === "confirmed" || s === "late") {
            return [A("arrive", _t("Arrived"), "primary"),
                    A("no_show", _t("No-show"), "tertiary"), A("cancel", _t("Cancel"), "tertiary")];
        }
        if (s === "arrived" || s === "waiting") {
            return [A("seat", _t("Seat"), "primary"),
                    A("no_show", _t("No-show"), "tertiary"), A("cancel", _t("Cancel"), "tertiary")];
        }
        if (s === "seated") {
            return [A("open", _t("Open order"), "secondary")];
        }
        if (s === "no_show" || s === "cancelled") {
            return [A("restore", _t("Restore"), "secondary")];
        }
        return [];   // done -> read-only
    }

    wlActions(w) {
        const s = w.state;
        const A = (action, label, kind) => ({ action, label, kind });
        if (s === "waiting") {
            return [A("notify", _t("Notify"), "primary"), A("seat", _t("Seat"), "secondary"),
                    A("no_response", _t("No response"), "tertiary"), A("cancel", _t("Cancel"), "tertiary")];
        }
        if (s === "notified") {
            return [A("seat", _t("Seat"), "primary"),
                    A("no_response", _t("No response"), "tertiary"), A("cancel", _t("Cancel"), "tertiary")];
        }
        if (s === "seating") {
            return [A("seat", _t("Seat"), "primary"), A("cancel", _t("Cancel"), "tertiary")];
        }
        if (s === "seated") {
            return [A("open", _t("Open order"), "secondary")];
        }
        if (s === "left" || s === "no_response" || s === "cancelled") {
            return [A("restore", _t("Restore"), "secondary")];
        }
        return [];
    }

    resStatusLabel(s) {
        return { booked: _t("Booked"), confirmed: _t("Confirmed"), late: _t("Late"),
                 waiting: _t("Waiting"), arrived: _t("Arrived"), seated: _t("Seated"),
                 done: _t("Done"), no_show: _t("No-show"), cancelled: _t("Cancelled") }[s] || s;
    }

    wlStatusLabel(s) {
        return { waiting: _t("Waiting"), notified: _t("Notified"), seating: _t("Seating"),
                 seated: _t("Seated"), left: _t("Left"), no_response: _t("No response"),
                 cancelled: _t("Cancelled") }[s] || s;
    }

    statusVariant(s) {
        if (["seated", "confirmed", "done"].includes(s)) return "ok";
        if (["late", "no_response", "notified"].includes(s)) return "warn";
        if (["no_show", "cancelled", "left"].includes(s)) return "danger";
        if (["arrived", "seating"].includes(s)) return "info";
        return "info";
    }

    // A reservation/waitlist action: 'seat' + 'open' route through the register/picker;
    // no_show/cancel confirm first; everything else is a direct guarded transition.
    onResAction(r, action) {
        if (action === "seat") {
            this._seatCtx = { model: "res", row: r };
            this.openSeatPicker();
        } else if (action === "open") {
            this.openSeatedOrder(r);
        } else if (action === "no_show" || action === "cancel") {
            this.state.hostConfirm = { kind: action, model: "res", row: r, action };
        } else {
            this._resTransition(r, action);
        }
    }

    onWlAction(w, action) {
        if (action === "seat") {
            this._seatCtx = { model: "wl", row: w };
            this.openSeatPicker();
        } else if (action === "open") {
            this.openSeatedOrder(w);
        } else if (action === "cancel") {
            this.state.hostConfirm = { kind: "cancel", model: "wl", row: w, action };
        } else {
            this._wlTransition(w, action);
        }
    }

    get hostConfirmLabel() {
        const c = this.state.hostConfirm;
        if (!c) {
            return "";
        }
        const who = (c.row && c.row.who) || _t("this guest");
        return c.kind === "no_show"
            ? _t("Mark %s as no-show?", who) : _t("Cancel this for %s?", who);
    }

    cancelHostConfirm() {
        this.state.hostConfirm = null;
    }

    async confirmHostConfirm() {
        const c = this.state.hostConfirm;
        this.state.hostConfirm = null;
        if (!c) {
            return;
        }
        if (c.model === "res") {
            await this._resTransition(c.row, c.action);
        } else {
            await this._wlTransition(c.row, c.action);
        }
    }

    async _resTransition(r, action, extra) {
        if (this.state.inFlight) {
            return null;
        }
        this.state.inFlight = true;
        const h = this.state.host;
        if (h) {
            h.error = "";
        }
        try {
            const res = await this.api.call("/reservations/state", {
                reservation_id: r.id, action, session_id: this.state.sessionId, ...(extra || {}) });
            await this.loadHost();       // refetch — server truth wins over the stale card
            return res;
        } catch (err) {
            // a stale/illegal transition (409) resolves by refetching current state
            await this.loadHost();
            if (h) {
                h.error = _t("That action wasn’t possible — the list has been refreshed.");
            }
            return null;
        } finally {
            this.state.inFlight = false;
        }
    }

    async _wlTransition(w, action, extra) {
        if (this.state.inFlight) {
            return null;
        }
        this.state.inFlight = true;
        const h = this.state.host;
        if (h) {
            h.error = "";
        }
        try {
            const res = await this.api.call("/waitlist/state", {
                waitlist_id: w.id, action, session_id: this.state.sessionId, ...(extra || {}) });
            await this.loadHost();
            return res;
        } catch (err) {
            await this.loadHost();
            if (h) {
                h.error = _t("That action wasn’t possible — the list has been refreshed.");
            }
            return null;
        } finally {
            this.state.inFlight = false;
        }
    }

    // Seat: reuse the canonical table picker in 'seat' mode. Choosing a table posts the
    // seat transition (with table_id) and opens the resulting order in the Register.
    openSeatPicker() {
        this.state.assignPicker = { mode: "seat", floors: [], activeFloorId: null, error: "", busy: true };
        this._loadAssignFloors();
    }

    async seatAtTable(t) {
        const ctx = this._seatCtx;
        if (!ctx) {
            return;
        }
        this.state.assignPicker = null;
        const row = ctx.row;
        const res = ctx.model === "res"
            ? await this._resTransition(row, "seat", { table_id: t.id })
            : await this._wlTransition(row, "seat", { table_id: t.id });
        this._seatCtx = null;
        if (res && res.ok !== false) {
            // open the seated table's order in the Register (exactly one order; may be
            // freshly created by the host on the first line — server back-links it).
            const order = res.order || null;
            const guests = (res.reservation && res.reservation.guests)
                || (row && (row.guests || row.party_size)) || 0;
            await this._openSeatedTable({ id: t.id, name: t.name, floor: t.floor,
                guests, order_uuid: order && order.order_uuid });
        }
    }

    async openSeatedOrder(row) {
        // 'Open order' on a seated card → open that table in the Register.
        const tableName = row.table ? String(row.table).replace(/^T/, "") : null;
        await this._openSeatedTable({
            id: row.table_id || (row.order && row.order.table_id) || null,
            name: tableName, floor: null,
            guests: row.guests || row.party_size || 0,
            order_uuid: row.order_id ? null : null,
        });
    }

    async _openSeatedTable(table) {
        // In-app switch to a table-bound Register (reuses the CP5 resume seam). If the
        // table's id is unknown (seated card with only a label), fall back to the Floor.
        if (!table || !table.id) {
            window.location.href = this.floorUrl;
            return;
        }
        this.state.inFlight = true;
        try {
            let uuid = table.order_uuid || null;
            if (uuid) {
                const got = await this.api.call("/orders/get", { uuid });
                this._loadOrderLines(got.lines);
                if (got.guests) {
                    table.guests = got.guests;
                }
            } else {
                this.order.clear();
                uuid = makeUuid();
            }
            this.state.orderUuid = uuid;
            this.state.table = { id: table.id, name: table.name, floor: table.floor,
                order_uuid: uuid, guests: table.guests || 0 };
            this.state.customer = null;
            this.state.phase = "menu";
        } catch (err) {
            this._failFromError(err);
        } finally {
            this.state.inFlight = false;
        }
    }

    // ---- New reservation --------------------------------------------------
    openResForm() {
        const now = new Date();
        const p = (n) => String(n).padStart(2, "0");
        this.state.resForm = {
            name: "", phone: "", guests: 2,
            date: `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`,
            time: `${p(now.getHours())}:${p(now.getMinutes())}`,
            duration: 1.5, note: "", table_id: null,
            tables: [], busy: false, error: "",
        };
        this._loadResFormTables();
    }

    closeResForm() {
        this.state.resForm = null;
    }

    resFormGuests(delta) {
        const f = this.state.resForm;
        if (f) {
            f.guests = Math.max(1, (f.guests || 1) + delta);
            this._loadResFormTables();
        }
    }

    async _loadResFormTables() {
        const f = this.state.resForm;
        if (!f || !f.date || !f.time) {
            return;
        }
        try {
            const res = await this.api.call("/reservations/availability", {
                config_id: this.boot.config_id, start: `${f.date} ${f.time}:00`,
                duration: f.duration, guests: f.guests });
            f.tables = res.tables || [];
            if (f.table_id && !f.tables.some((t) => t.id === f.table_id)) {
                f.table_id = null;
            }
        } catch (err) {
            f.tables = [];
        }
    }

    async saveReservation() {
        const f = this.state.resForm;
        if (!f || f.busy) {
            return;
        }
        if (!f.name || !f.name.trim()) {
            f.error = _t("Guest name is required.");
            return;
        }
        if (!f.table_id) {
            f.error = _t("Choose an available table.");
            return;
        }
        f.busy = true;
        f.error = "";
        try {
            const res = await this.api.call("/reservations/create", {
                config_id: this.boot.config_id, table_id: f.table_id,
                start: `${f.date} ${f.time}:00`, duration: f.duration,
                guests: f.guests, name: f.name.trim(), phone: (f.phone || "").trim(),
                note: (f.note || "").trim() });
            if (res && res.ok === false) {
                f.error = res.error === "table_unavailable"
                    ? _t("That table is already booked for this time.") : _t("Couldn’t save the reservation.");
                return;
            }
            this.state.resForm = null;
            await this.loadHost();
        } catch (err) {
            f.error = err && err.kind === "network"
                ? _t("Local Mezze server unavailable.") : _t("Couldn’t save the reservation.");
        } finally {
            f.busy = false;
        }
    }

    // ---- Add walk-in ------------------------------------------------------
    openWlForm() {
        this.state.wlForm = { name: "", phone: "", party_size: 2, quoted_wait: "",
            note: "", busy: false, error: "" };
    }

    closeWlForm() {
        this.state.wlForm = null;
    }

    wlFormSize(delta) {
        const f = this.state.wlForm;
        if (f) {
            f.party_size = Math.max(1, (f.party_size || 1) + delta);
        }
    }

    async saveWalkIn() {
        const f = this.state.wlForm;
        if (!f || f.busy) {
            return;
        }
        if (!f.name || !f.name.trim()) {
            f.error = _t("Guest name is required.");
            return;
        }
        f.busy = true;
        f.error = "";
        try {
            const body = { config_id: this.boot.config_id, name: f.name.trim(),
                party_size: f.party_size, phone: (f.phone || "").trim(),
                note: (f.note || "").trim() };
            if (f.quoted_wait !== "" && !isNaN(parseInt(f.quoted_wait, 10))) {
                body.quoted_wait = parseInt(f.quoted_wait, 10);
            }
            const res = await this.api.call("/waitlist/add", body);
            if (res && res.ok === false) {
                f.error = _t("Couldn’t add to the waitlist.");
                return;
            }
            this.state.wlForm = null;
            if (this.state.host) {
                this.state.host.tab = "waitlist";
            }
            await this.loadHost();
        } catch (err) {
            f.error = err && err.kind === "network"
                ? _t("Local Mezze server unavailable.") : _t("Couldn’t add to the waitlist.");
        } finally {
            f.busy = false;
        }
    }

    // ---- R2A CP6: assign a counter order to a table + guest count -----------
    get canAssign() {
        // read the REACTIVE cart (this.cart), not the raw store, so Root re-renders
        // and recomputes this the moment a line is added/removed.
        return !this.isTableBound && this.cart.lines.length > 0;
    }
    get guestsCount() {
        return this.isTableBound ? (this.state.table.guests || 0) : 0;
    }
    get assignFloor() {
        const p = this.state.assignPicker;
        if (!p || !p.floors.length) {
            return null;
        }
        return p.floors.find((f) => f.id === p.activeFloorId) || p.floors[0];
    }
    get assignTables() {
        const f = this.assignFloor;
        return (f && f.tables) || [];
    }

    openAssignPicker() {
        if (this.order.isEmpty) {
            return;
        }
        this.state.assignPicker = { mode: "assign", floors: [], activeFloorId: null, error: "", busy: true };
        this._loadAssignFloors();
    }

    // CP7 — a table-bound order can be MOVED (transfer to a free table, or merge into
    // an occupied one). Reuses the same destination picker in 'move' mode.
    get canMove() {
        return this.isTableBound && !!this.state.orderUuid;
    }
    openMovePicker() {
        if (!this.canMove) {
            return;
        }
        this.state.assignPicker = { mode: "move", floors: [], activeFloorId: null, error: "", busy: true };
        this._loadAssignFloors();
    }
    // Picker tap dispatches by mode (CP6 assign vs CP7 move) so CP6 behaviour is unchanged.
    onPickTable(t) {
        const p = this.state.assignPicker;
        if (!p) {
            return;
        }
        if (p.mode === "move") {
            this.onMoveTarget(t);
        } else if (p.mode === "seat") {          // CP10 — seat a reservation/waitlist party
            this.seatAtTable(t);
        } else {
            this.onAssignTable(t);
        }
    }
    // In move mode occupied tables ARE selectable (merge); reserved + the source are not.
    // In assign/seat mode only free tables are selectable (occupied/reserved disabled).
    pickerTableDisabled(t) {
        const p = this.state.assignPicker;
        if (p && p.mode === "move") {
            return t.status === "reserved" || this.isSourceTable(t);
        }
        return t.status !== "available";
    }
    // The order's own (current) table while moving — never a merge destination.
    isSourceTable(t) {
        const p = this.state.assignPicker;
        return !!(p && p.mode === "move" && this.isTableBound && t.id === this.state.table.id);
    }
    closeAssignPicker() {
        this.state.assignPicker = null;
    }
    selectAssignFloor(id) {
        if (this.state.assignPicker) {
            this.state.assignPicker.activeFloorId = id;
        }
    }
    async _loadAssignFloors() {
        try {
            const data = await this.api.call("/floors", { config_id: this.boot.config_id });
            const p = this.state.assignPicker;
            if (!p) {
                return;
            }
            p.floors = data.floors || [];
            p.activeFloorId = p.floors.length ? p.floors[0].id : null;
            p.busy = false;
        } catch (err) {
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
                return;
            }
            if (this.state.assignPicker) {
                this.state.assignPicker.error = _t("Could not load the floor.");
                this.state.assignPicker.busy = false;
            }
        }
    }

    // Assign the counter order to a chosen table. The order is first persisted as a
    // draft under its STABLE uuid (no duplicate), then the GUARDED assign endpoint
    // binds the table — the server blocks occupied / reserved / invalid / cross-branch.
    async onAssignTable(t) {
        const p = this.state.assignPicker;
        if (!p || this.state.inFlight) {
            return;
        }
        if (t.status !== "available") {
            p.error = t.status === "reserved"
                ? _t("T%s is reserved — check in the reservation first.", t.name)
                : _t("T%s is occupied — use Transfer / Merge.", t.name);
            return;
        }
        this.state.inFlight = true;
        p.error = "";
        try {
            const uuid = this.state.orderUuid || (this.state.orderUuid = makeUuid());
            this._noteFromServer(await this.api.call("/orders/sync", {
                uuid, session_id: this.state.sessionId,
                lines: this.order.toSyncLines(), draft: true,
                expected_revision: this._revisionClaimFor(uuid),
            }), uuid);
            const res = await this.api.call("/orders/assign_table", {
                uuid, table_id: t.id, config_id: this.boot.config_id,
            });
            this.state.table = res.table;
            this.state.assignPicker = null;
        } catch (err) {
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
                return;
            }
            const map = {
                table_occupied: _t("That table is occupied — use Transfer / Merge (later)."),
                table_reserved: _t("That table is reserved — check in the reservation first."),
                invalid_table: _t("That table isn’t available on this branch."),
                forbidden: _t("Not allowed for this branch."),
            };
            if (this.state.assignPicker) {
                this.state.assignPicker.error =
                    map[err && err.error] || (err && err.message) || _t("Could not assign the table.");
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    // Authoritative guest count on the table-bound draft (customer_count). +/- only;
    // never below 1; never client-only.
    async setGuests(delta) {
        if (!this.isTableBound || this.state.inFlight || !this.state.orderUuid) {
            return;
        }
        const cur = this.state.table.guests || 0;
        const next = Math.max(1, cur + delta);
        if (next === cur && cur >= 1) {
            return;
        }
        this.state.inFlight = true;
        try {
            const res = await this.api.call("/orders/set_guests", {
                uuid: this.state.orderUuid, guests: next, config_id: this.boot.config_id,
            });
            this.state.table.guests = res.guests;
        } catch (err) {
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    // CP7 — a destination was chosen for a move: free → transfer confirm; occupied →
    // merge confirm; reserved/same-table → refused in the picker (never silently).
    onMoveTarget(t) {
        const src = this.state.table;
        const p = this.state.assignPicker;
        if (t.id === src.id) {
            p.error = _t("That's the current table.");
            return;
        }
        if (t.status === "reserved") {
            p.error = _t("T%s is reserved — check in the reservation first.", t.name);
            return;
        }
        this.state.moveConfirm = {
            kind: (t.status === "available") ? "transfer" : "merge",
            dest: { id: t.id, name: t.name, floor: t.floor },
            srcName: src.name, srcFloor: src.floor,
            srcGuests: src.guests || 0, srcTotal: this.order.estimatedTotal,
            dstGuests: t.guests || 0, dstTotal: t.total || 0,
            error: "", blocked: false,
        };
        this.state.assignPicker = null;
    }
    cancelMove() {
        this.state.moveConfirm = null;
    }
    get combinedGuests() {
        const m = this.state.moveConfirm;
        return m ? ((m.srcGuests || 0) + (m.dstGuests || 0)) : 0;
    }
    get combinedTotal() {
        const m = this.state.moveConfirm;
        return m ? ((m.srcTotal || 0) + (m.dstTotal || 0)) : 0;
    }

    async confirmMove() {
        const m = this.state.moveConfirm;
        if (!m || this.state.inFlight || m.blocked) {
            return;
        }
        this.state.inFlight = true;
        m.error = "";
        try {
            if (m.kind === "transfer") {
                await this.api.call("/tables/transfer", {
                    session_id: this.state.sessionId,
                    from_table_id: this.state.table.id,
                    to_table_id: m.dest.id,
                    order_uuid: this.state.orderUuid,
                });
                // the SAME order moved — rebind the Register to its new seat
                this.state.table = {
                    id: m.dest.id, name: m.dest.name, floor: m.dest.floor,
                    order_uuid: this.state.orderUuid, guests: m.srcGuests,
                };
                this.state.moveConfirm = null;
            } else {
                // merge: NO combine_confirm — the server's financial safeguard is authoritative
                await this.api.call("/tables/merge", {
                    session_id: this.state.sessionId,
                    from_table_id: this.state.table.id,
                    to_table_id: m.dest.id,
                    expected_revision: this._revisionClaimFor(this.state.orderUuid),
                });
                // the source order was consumed into the destination — return to the Floor
                // where the combined result (source free, dest occupied) is visible.
                window.location.assign(this.floorUrl);
                return;
            }
        } catch (err) {
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
                return;
            }
            if (err && err.error === "merge_blocked_payments") {
                const d = (err && err.data) || {};
                m.blocked = true;
                m.error = _t(
                    "Can't merge — one or both tables have payments or reversals "
                    + "(T%s paid %s, T%s paid %s). Settle or resolve the table first; "
                    + "the orders were left unchanged.",
                    m.srcName, this.fmt(d.src_paid || 0), m.dest.name, this.fmt(d.dst_paid || 0));
            } else {
                m.error = (err && err.data && err.data.message) || (err && err.message)
                    || _t("Could not complete the move.");
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    async pollConnectivity() {
        try {
            const d = await this.api.call("/edge/status", {});
            this.state.conn = { local: "online", wan: d.wan || "unknown" };
        } catch {
            this.state.conn = { local: "unavailable", wan: "unknown" };
        }
    }

    // ---- menu interactions -------------------------------------------------
    onSelectCategory(catId) {
        this.state.activeCategory = this.state.activeCategory === catId ? null : catId;
    }

    /** Complexity decides what a tap does. A product with no choices goes straight
     *  into the order — one tap, nothing opens. A product that HAS choices asks,
     *  because guessing on the guest's behalf is how the wrong plate is made. */
    onSelectProduct(product) {
        if (product && product.available !== false && PC.isConfigurable(product)) {
            this.openConfigurator(product);
            return;
        }
        this.order.addProduct(product);
        this._refreshUpsell();
        // A product sold BY WEIGHT has no sensible default quantity. Adding it and
        // leaving 1 behind does not mean "one of them" — it means one kilogram, at
        // whatever a kilogram costs, and a cashier who does not notice has charged
        // the guest for a kilo of saffron. So the weight is asked for at the moment
        // the item is added, rather than being a step somebody has to remember.
        if (product && product.to_weight) {
            const line = this.order.state.lines[this.order.state.lines.length - 1];
            if (line) {
                this.openNumpad(line);
            }
        }
    }

    /** Open the canonical configurator for a product, or to EDIT an existing line —
     *  correcting a choice must not mean deleting the line and starting again. */
    openConfigurator(product, line = null) {
        const groups = PC.groups(product);
        this.state.config = {
            product,
            groups,
            lineKey: line ? line.key : null,
            selection: line
                ? Object.assign(
                    PC.selectionFrom(groups, line.attribute_value_ids || []),
                    PC.comboSelectionFrom(groups, line.combo || []))
                : PC.defaultSelection(groups),
        };
    }

    closeConfigurator() {
        this.state.config = null;
    }

    onConfigToggle(group, valueId) {
        const c = this.state.config;
        if (c) {
            c.selection = PC.toggle(group, valueId, c.selection);
        }
    }

    /** Commit the configuration. The chosen VALUES are what travels to the server —
     *  it re-derives every figure from them at sync, and that remains the authority.
     *  The panel's previewed extra comes along as DISPLAY only, so the line, the order
     *  total and the Charge button quote the same number the guest will be asked for
     *  instead of the bare list price. */
    onConfigConfirm() {
        const c = this.state.config;
        if (!c || !PC.isComplete(c.groups, c.selection)) {
            return;
        }
        const chosen = PC.chosen(c.groups, c.selection);
        if (c.lineKey) {
            this.order.removeByKey(c.lineKey);
        }
        this._refreshUpsell();
        this.order.addProduct(c.product, {
            attributeValueIds: chosen.ids,
            combo: chosen.combo,
            modifiers: chosen.names,
            priceExtra: PC.extraPrice(c.groups, c.selection),
        });
        this.closeConfigurator();
    }

    // ---- payment navigation ------------------------------------------------
    async goToPayment() {
        if (this.order.isEmpty || this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        try {
            // R2A CP5: a table-bound Register reuses its STABLE order uuid + binds the
            // table, so charging never creates a duplicate of the table's draft.
            let uuid = this.isTableBound
                ? (this.state.orderUuid || makeUuid())
                : makeUuid();
            const sync = (orderUuid) => {
                const body = {
                    uuid: orderUuid,
                    session_id: this.state.sessionId,
                    lines: this.order.toSyncLines(),
                    draft: true,
                    // Charge is the write that matters most: settling a check
                    // another terminal has moved bills the guest a total they were
                    // never shown. The claim is resolved against THIS uuid, so a
                    // freshly minted one carries none.
                    expected_revision: this._revisionClaimFor(orderUuid),
                };
                if (this.isTableBound) {
                    body.table_id = this.state.table.id;
                }
                return this.api.call("/orders/sync", body).then((r) => this._noteFromServer(r, orderUuid));
            };
            let res = await sync(uuid);
            // A SPENT uuid must never become the bill in front of the cashier.
            //
            // /orders/sync is idempotent by uuid: hand it one that has already been
            // settled and it answers with that order's figures — total 83.15, paid
            // 83.15 — rather than pricing the cart in hand. The payment screen then
            // seeds itself from those numbers, computes nothing left to collect, and
            // disables every tender: a live sale facing a screen that says "Paid" and
            // "No tenders yet" at the same time, with no way forward.
            //
            // Rather than enumerate the routes that can leave a settled uuid behind
            // (a resumed table, a split family that was paid off, a receipt left by
            // Back rather than New order), treat the server's own answer as the test:
            // if what came back is already paid for, this cart is a NEW sale and needs
            // its own order. One retry, then trust it.
            const settled = (r) => {
                const t = Number(r && r.amount_total);
                const paidUp = Number(r && r.amount_paid);
                return Number.isFinite(t) && t > 0 && Number.isFinite(paidUp)
                    && paidUp >= t - 0.0001;
            };
            if (settled(res)) {
                uuid = makeUuid();
                this.state.orderUuid = uuid;
                // a NEW order: nothing is held about it yet, so no claim is made
                this.state.orderRevision = null;
                this.state.orderRevisionUuid = null;
                this.state.editLock = null;
                res = await sync(uuid);
            }
            // The payment screen is driven entirely by this figure: every tender
            // button disables itself once there is nothing left to collect. So an
            // answer that carries no total does not produce an error — it produces a
            // Payment screen with a remaining of zero and every method greyed out,
            // which reads to a cashier as "the buttons are broken" and gives them
            // nothing to act on. Refuse to enter the screen instead of drawing a dead
            // one; the till already knows how to report a failure.
            const serverTotal = Number(res && res.amount_total);
            if (!Number.isFinite(serverTotal) || serverTotal <= 0) {
                throw {
                    kind: "server",
                    message: _t("The server did not price this order, so there is " +
                                "nothing to charge yet. Reopen the order and try again."),
                };
            }
            this.state.orderUuid = uuid;
            this.state.snapshot = this.order.snapshot();
            // CP9 partial recall: a resumed order may already carry tenders — seed the
            // payment screen from the AUTHORITATIVE already-paid amount so the cashier
            // sees the correct remaining and never re-tenders what is already paid.
            const paid = roundTo(res.amount_paid || 0, this.decimals);
            this.state.payment = {
                uuid,
                total: serverTotal,
                paid,
                remaining: roundTo(res.amount_total - paid, this.decimals),
                tenders: [],
            };
            this.state.warn = null;
            this.state.managerReq = null;
            this.state.tenderError = "";
            this.state.phase = "payment";
            this.pushCfd("paying");
        } catch (err) {
            if (!this._failFromError(err)) {
                this.state.phase = "error";
                this.state.errorMsg = err && err.kind === "network"
                    ? _t("Local Mezze server unavailable") : (err && err.message) || _t("Could not open payment");
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    backToMenu() {
        this.state.phase = "menu";
        this.state.payment = null;
        this.state.warn = null;
        this.state.managerReq = null;
        this.state.creditWarn = null;
        this.state.creditManager = null;
        this.state.customerPicker = null;
        this.state.customer = null;
        this.state.terminal = null;
        this.state.cashmachine = null;
        this.state.qr = null;
        this.state.tenderError = "";
        // R1B: never return to the menu with a stale, invisible search filter. The search
        // input is uncontrolled and re-mounts empty, so the persisted query would silently
        // filter the grid with no visible cause — reset the query + highlight on the way back.
        this.state.search = "";
        this.state.searchIndex = 0;
    }

    // ---- tender submission -------------------------------------------------
    // payload: { method, amount, device_id, reference, approval_code, change,
    //            allow_duplicate?, approval_token?, approval_reason?, tender_key? }
    async submitTender(payload) {
        if (this.state.inFlight || !this.state.payment) {
            return;
        }
        this.state.inFlight = true;
        this.state.tenderError = "";
        const pay = this.state.payment;
        const tenderKey = payload.tender_key || makeUuid();
        const body = {
            uuid: pay.uuid,
            payment_method_id: payload.method.id,
            amount: payload.amount,
            tender_key: tenderKey,
        };
        if (payload.device_id) {
            body.device_id = payload.device_id;
        }
        if (payload.reference) {
            body.payment_ref = payload.reference;
        }
        if (payload.approval_code) {
            body.approval_code = payload.approval_code;
        }
        if (payload.allow_duplicate) {
            body.allow_duplicate = true;
        }
        if (payload.manager_code && payload.manager_pin) {
            body.manager_code = payload.manager_code;
            body.manager_pin = payload.manager_pin;
            body.manager_reason = payload.manager_reason || "";
        }
        // S2C-6: a Customer Account tender carries the selected customer + (when the
        // cashier explicitly continued past a soft warn) the credit override flag.
        if (this.state.customer) {
            body.partner_id = this.state.customer.id;
        }
        if (payload.allow_credit) {
            body.allow_credit = true;
        }
        // A gift card entered earlier settles HERE, not when it was typed. The server
        // caps it at the live balance and at what is still owed, so a card that
        // covers only part of the bill leaves the rest on another tender.
        if (payload.gift_card_code || (payload.useGiftCard && this.state.giftCard)) {
            body.gift_card_code =
                payload.gift_card_code || this.state.giftCard.code;
        }
        // The check must still be the one the cashier was shown when they
        // pressed Charge.
        body.expected_revision = this._revisionClaimFor(body.uuid || this.state.orderUuid);
        try {
            const res = await this.api.call("/orders/pay", body);
            this._noteFromServer(res, body.uuid || this.state.orderUuid);
            // success — record the tender from authoritative response
            if (res.pos_reference) {
                pay.pos_reference = res.pos_reference;
            }
            pay.tenders.push({
                method: payload.method.name,
                mode: payload.method.mezze_mode,
                amount: roundTo(payload.amount, this.decimals),
                device: payload.device_name || "",
                reference: maskRef(payload.reference),
                // The SERVER's change, not the screen's preview of it. Those agreed
                // only by accident before: the till capped the tender, so nothing was
                // ever booked back and `res.change` did not exist.
                change: res.change ?? payload.change ?? 0,
            });
            pay.change = res.change ?? pay.change ?? 0;
            if (pay.evenParts && pay.evenParts.length) {
                // One share settled. Counting them here rather than inferring from
                // the balance keeps a part-payment made for some other reason from
                // being mistaken for somebody's share.
                pay.evenPaid = (pay.evenPaid || 0) + 1;
                if (pay.evenPaid >= pay.evenParts.length) {
                    this.clearEvenSplit();
                }
            }
            if (body.gift_card_code && res.gift_card_balance !== undefined) {
                // What the guest asks next. A card with nothing left stops being
                // offered rather than failing on the following order.
                if (this.state.giftCard
                        && this.state.giftCard.code === body.gift_card_code) {
                    this.state.giftCard = res.gift_card_balance > 0
                        ? { ...this.state.giftCard, balance: res.gift_card_balance }
                        : null;
                }
            }
            pay.paid = res.amount_paid ?? pay.paid + payload.amount;
            pay.remaining = res.remaining ?? roundTo(pay.total - pay.paid, this.decimals);
            this.state.warn = null;
            this.state.managerReq = null;
            this.state.creditWarn = null;
            this.state.creditManager = null;
            if (res.remaining !== undefined ? res.remaining <= 0 : pay.remaining <= 0) {
                await this.finalize();
            }
            return { ok: true };
        } catch (err) {
            return this._handleTenderError(err, payload, tenderKey);
        } finally {
            this.state.inFlight = false;
        }
    }

    _handleTenderError(err, payload, tenderKey) {
        const data = (err && err.data) || {};
        // strip manager creds + credit override from the retained pending so a retry
        // re-collects them
        const {
            manager_code, manager_pin, manager_reason, allow_duplicate, allow_credit, ...clean
        } = payload;
        const pending = { ...clean, tender_key: tenderKey };
        if (data.error === "duplicate_reference_warn") {
            this.state.warn = { ctx: data.duplicate || [], pending };
            return { ok: false, warn: true };
        }
        if (data.error === "duplicate_reference_needs_manager") {
            this.state.managerReq = { ctx: data.duplicate || [], pending, error: "" };
            return { ok: false, manager: true };
        }
        // S2C-6 credit governance outcomes
        if (data.error === "customer_required") {
            this.state.tenderError = _t("Select a customer before charging to a Customer Account.");
            return { ok: false };
        }
        if (data.error === "credit_warn") {
            this.state.creditWarn = { ctx: data.credit || {}, pending };
            return { ok: false, credit: true };
        }
        if (data.error === "credit_needs_manager") {
            this.state.creditManager = { ctx: data.credit || {}, pending, error: "" };
            return { ok: false, credit: true };
        }
        if (data.error === "credit_blocked") {
            const c = data.credit || {};
            this.state.tenderError = _t(
                "Customer Account blocked: this sale exceeds %s's credit limit.", c.name || _t("the customer"));
            return { ok: false };
        }
        if (data.error === "insufficient_role" || data.error === "bad_credentials") {
            const reason = data.error === "insufficient_role"
                ? _t("That user is not authorized to approve (manager required).")
                : _t("Invalid manager code or PIN.");
            // a credit manager-approval failure keeps the CREDIT modal open
            if (this.state.creditManager) {
                this.state.creditManager = {
                    ctx: data.credit || this.state.creditManager.ctx, pending, error: reason };
                return { ok: false, credit: true };
            }
            // otherwise it is the duplicate-reference manager modal
            const ctx = data.duplicate || (this.state.managerReq ? this.state.managerReq.ctx : []);
            this.state.managerReq = { ctx, pending, error: reason };
            return { ok: false, manager: true };
        }
        if (err && err.kind === "auth") {
            this.state.phase = "auth_required";
            return { ok: false };
        }
        if (err && err.kind === "network") {
            this.state.tenderError = _t("Local Mezze server unavailable — payment not taken.");
            return { ok: false };
        }
        // payment_rejected covers BLOCK duplicate + required device/reference. Show a
        // translated cashier message (the raw backend text is not localized); the
        // BLOCK case is inferred from the method's own duplicate policy.
        if (data.error === "payment_rejected" && payload.method && payload.method.duplicate_policy === "block") {
            this.state.tenderError = _t("This reference cannot be reused.");
            return { ok: false };
        }
        this.state.tenderError = (err && err.message) || _t("Payment was rejected.");
        return { ok: false };
    }

    // WARN modal → cashier explicitly continues (backend-authorized override)
    async warnContinue() {
        const w = this.state.warn;
        if (!w) {
            return;
        }
        this.state.warn = null;
        await this.submitTender({ ...w.pending, allow_duplicate: true });
    }

    warnCancel() {
        this.state.warn = null;
    }

    // Manager approval → resubmit the pending tender WITH the manager's PIN. The
    // backend verifies the PIN + role (same mezze.cashier model as /w1/approve);
    // a cashier can never self-approve. submitTender re-opens this modal with an
    // error on a bad/insufficient credential, or records the tender on success.
    async managerApprove({ code, pin, reason }) {
        const m = this.state.managerReq;
        if (!m || this.state.inFlight) {
            return;
        }
        await this.submitTender({
            ...m.pending,
            manager_code: code,
            manager_pin: pin,
            manager_reason: reason || "",
        });
    }

    managerCancel() {
        this.state.managerReq = null;
    }

    // ---- Order actions: comp / void / fire / 86 ----------------------------
    // These are the verbs a cashier needs on a LIVE order, and every one of them is
    // a real backend contract with its own policy:
    //   comp  — line-level, 100%-off giveaway, manager-approved BY DEFAULT, audited
    //           separately from a discount because comps are a shrinkage vector
    //   void  — order-level, item never made, cascades a KDS cancellation
    //   fire  — send the order's lines to the kitchen now
    //   86    — mark a product unavailable across the branch
    // comp and void both need the order to exist SERVER-side, so the draft is
    // persisted first; nothing is approved or sent for an order the server has
    // never seen.

    /** What this terminal may do, straight from the boot payload. Advisory only —
     *  the server checks every route regardless; this just stops the UI offering a
     *  button that can only ever fail. */
    can(capability) {
        const caps = this.boot.capabilities;
        return Array.isArray(caps) ? caps.includes(capability) : true;
    }

    /** A verb is offered when the terminal holds the capability, OR when a manager
     *  could authorise it in person. Where neither is true it is not shown at all,
     *  because a dead control is worse than an absent one. */
    offers(capability) {
        return this.can(capability) || !!this.boot.manager_elevation;
    }

    /** Prompt only when the terminal cannot do it alone. A supervisor already signed
     *  in should not be asked to type their own PIN to use their own permission. */
    _needsApproval(capability) {
        return !this.can(capability);
    }

    /** Persist the working cart as a draft so a server-side action has a target. */
    async _ensurePersisted() {
        if (!this.state.orderUuid) {
            this.state.orderUuid = makeUuid();
        }
        const res = await this.api.call("/orders/sync", {
            uuid: this.state.orderUuid,
            session_id: this.state.sessionId,
            lines: this.order.toSyncLines(),
            table_id: this.state.table && this.state.table.id,
            // The ORDER TYPE, not its pricelist. What a preset costs is the branch's
            // configuration; a till that could name a pricelist could name a cheaper
            // one.
            preset_id: this.state.presetId || undefined,
            draft: true,
            expected_revision: this._revisionClaimFor(this.state.orderUuid),
        });
        if (res && res.uuid) {
            this.state.orderUuid = res.uuid;
        }
        this._noteFromServer(res, this.state.orderUuid);
        await this._refreshAutoPromotions();
        return this.state.orderUuid;
    }

    /** Bring the branch's own published promotions up to date with the cart.
     *
     *  They were applied on the storefront and nowhere on the till, so a guest
     *  ordering online got a promotion the same guest at the counter did not.
     *
     *  Hooked here because every server operation that needs an order goes through
     *  _ensurePersisted, and the endpoint RECONCILES — it takes the old automatic
     *  lines off and puts the current ones back — so calling it repeatedly is safe.
     *  An endpoint that merely added would discount the order again on every ring-up.
     */
    async _refreshAutoPromotions() {
        if (!this.state.orderUuid) {
            return;
        }
        try {
            const r = await this.api.call("/promo/auto", {
                order_uuid: this.state.orderUuid,
                session_id: this.state.sessionId,
            });
            if (!r || !r.ok) {
                return;
            }
            const now = r.discount || 0;
            if (now !== this.state.autoPromoDiscount) {
                // The order moved. Re-read it rather than patching the total here:
                // the discount line is the server's.
                this.state.autoPromoDiscount = now;
                this.state.autoPromotions = r.promotions || [];
                await this._reloadOrder();
            }
        } catch {
            // A promotion that cannot be refreshed must never block the sale. The
            // order is already persisted; the price simply stays as last computed.
        }
    }

    /** Re-read the authoritative order so comped prices replace the client's. */
    async _reloadOrder() {
        try {
            const res = await this.api.call("/orders/get", { uuid: this.state.orderUuid });
            if (res && res.lines) {
                this._loadOrderLines(res.lines);
            }
        } catch (e) {
            // the action already succeeded server-side; a failed refresh must not
            // undo it, so the cashier is told to reopen rather than shown a lie
            this.state.actionError = _t("Done, but the order could not be refreshed.");
        }
    }

    // ---- Discounts -----------------------------------------------------------
    //
    // A discount is NOT a comp. A comp is a 100% giveaway that always records an
    // approver because it is a shrinkage vector; a discount is routine service
    // recovery a cashier does several times a shift. So this asks for a percentage
    // first and only escalates to a manager when the SERVER says the number is
    // above the operator's own ceiling. The ceiling is never evaluated here — a
    // client-side limit is a hint, and this one is a control.

    /** The percentages a till actually uses, so the common case is one tap. The
     *  custom field stays for everything else. */
    get discountPresets() {
        return [5, 10, 15, 20, 25, 50];
    }

    get discountTitle() {
        const d = this.state.discount;
        if (!d) {
            return "";
        }
        return d.scope === "line" ? _t("Discount this item") : _t("Discount the order");
    }

    get discountApplyLabel() {
        const d = this.state.discount;
        return _t("Take %s off", (d ? d.percent : 0) + "%");
    }

    get discountPercentLabel() {
        return _t("Percentage off");
    }

    get discountReasonLabel() {
        return _t("Reason (optional)");
    }

    openDiscount(line) {
        if (!this.state.sessionId || !this.order.lines.length) {
            return;
        }
        this.state.discount = {
            scope: line ? "line" : "order",
            productId: line ? line.product.id : null,
            detail: line ? line.product.name : _t("%s items", this.order.count),
            percent: 10,
            reason: "",
            error: "",
        };
    }

    setDiscountPercent(value) {
        const d = this.state.discount;
        if (!d) {
            return;
        }
        const n = Number(String(value).replace(",", "."));
        d.percent = Number.isFinite(n) ? n : 0;
        d.error = "";
    }

    setDiscountReason(value) {
        if (this.state.discount) {
            this.state.discount.reason = value;
            this.state.discount.error = "";
        }
    }

    cancelDiscount() {
        this.state.discount = null;
    }

    /** One request shape, used for both the operator's own attempt and the manager's
     *  escalated one. `credential` is empty on the first try: the server answers
     *  whether that authority was enough. */
    async _postDiscount(d, credential) {
        await this._ensurePersisted();
        return this.api.call("/orders/discount", {
            session_id: this.state.sessionId,
            order_uuid: this.state.orderUuid,
            scope: d.scope,
            product_id: d.scope === "line" ? d.productId : undefined,
            percent: d.percent,
            reason: d.reason,
            ...(credential || {}),
        });
    }

    async submitDiscount() {
        const d = this.state.discount;
        if (!d || this.state.inFlight) {
            return;
        }
        if (!(d.percent > 0 && d.percent <= 100)) {
            d.error = _t("Enter a percentage between 1 and 100.");
            return;
        }
        this.state.inFlight = true;
        try {
            await this._postDiscount(d, {});
            this.state.discount = null;
            await this._reloadOrder();
        } catch (err) {
            const code = (err && err.error) || "";
            if (code === "approval_required") {
                // Over this operator's ceiling. A manager may still authorise it, so
                // hand the SAME request to the approval gate rather than telling the
                // cashier no and making them start over — the percentage they chose
                // is carried through, and the reason with it.
                const carried = { ...d };
                this.state.discount = null;
                this.state.managerGate = {
                    action: "discount",
                    title: _t("Approve %s off", carried.percent + "%"),
                    detail: (err && err.message) || carried.detail,
                    reasonRequired: true,
                    run: async ({ managerCode, managerPin, reason }) => {
                        await this._postDiscount(
                            { ...carried, reason: reason || carried.reason },
                            { manager_code: managerCode, manager_pin: managerPin });
                        await this._reloadOrder();
                    },
                };
            } else if (!this._failFromError(err)) {
                d.error = (err && err.message) || _t("That discount did not go through.");
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    // ---- Refund ---------------------------------------------------------------
    //
    // The endpoint has always been there and nothing could reach it. Everything
    // that decides whether a refund is legal — the per-line quantity ceiling, the
    // order-level money ceiling in integer minor units, the advisory lock — stays
    // on the server; this only asks which items are coming back and why.

    /** Enter Code — a gift card, a coupon or a promotion.
     *
     *  Mezze's loyalty back end was complete and the register called none of it.
     *  This is the door.
     */
    /** Print what the table owes, before any of it is paid.
     *
     *  Mezze could print a receipt for a settled order and nothing at all for an open
     *  one, so on a restaurant floor there was no way to hand a guest their bill.
     */
    /** Print a second copy of a receipt for an order that is already settled.
     *
     *  ``/print/receipt`` took a uuid all along; nothing on the till ever passed one,
     *  so a guest who lost their receipt could not be given another.
     */
    async reprintReceipt(row) {
        if (!row || !row.uuid || this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        try {
            const r = await this.api.call("/print/receipt", { uuid: row.uuid },
                                          { base: "/mezze/hardware" });
            if (!r || !r.ok) {
                this.state.actionError = (r && r.message)
                    || _t("The printer could not be reached.");
            }
        } catch (e) {
            this.state.actionError = _t("The printer could not be reached.");
        } finally {
            this.state.inFlight = false;
        }
    }

    get reprintLabel() {
        return _t("Reprint");
    }

    /** "Four people, one bill" — ask the server for the shares.
     *
     *  Splitting evenly does NOT restructure the order: four people paying a quarter
     *  each still ate one meal, so the items stay put and each share is tendered
     *  through the ordinary payment route. The amounts come from the server because
     *  they have to provably sum back to the bill — 100 into 3 is 33.34/33.33/33.33,
     *  and a browser doing that arithmetic is a browser that eventually collects
     *  99.99.
     */
    async splitEvenly(ways) {
        const pay = this.state.payment;
        if (!pay || !this.state.orderUuid) {
            return;
        }
        this.state.inFlight = true;
        try {
            const r = await this.api.call("/split/even", {
                uuid: this.state.orderUuid, ways,
            });
            if (r && r.ok) {
                pay.evenParts = r.parts || [];
                pay.evenWays = r.ways;
                pay.evenPaid = 0;
            } else {
                this.state.tenderError = (r && r.message)
                    || _t("That bill could not be split evenly.");
            }
        } catch (err) {
            this.state.tenderError = (err && err.message)
                || _t("That bill could not be split evenly.");
        } finally {
            this.state.inFlight = false;
        }
    }

    clearEvenSplit() {
        const pay = this.state.payment;
        if (pay) {
            pay.evenParts = null;
            pay.evenWays = 0;
            pay.evenPaid = 0;
        }
    }

    /** Suggestions for what else this guest might want.
     *
     *  `/ai/upsell` is a real market-basket miner — confidence and lift over paid
     *  baskets, falling back to popularity when the signal is thin, and every
     *  suggestion explainable. The guest-facing table page has called it since it was
     *  written; the cashier, who is the person actually in a position to ask, never
     *  did.
     *
     *  Refreshed on a debounce as the cart changes, and only while the cart HAS
     *  something — suggesting add-ons for an empty order is guessing, and the
     *  endpoint's popularity fallback would happily oblige.
     */
    _refreshUpsell() {
        window.clearTimeout(this._upsellTimer);
        const ids = this.order.state.lines.map((l) => l.product.id);
        if (!ids.length) {
            this.state.upsell = [];
            return;
        }
        this._upsellTimer = window.setTimeout(async () => {
            try {
                const r = await this.api.call("/ai/upsell", { cart: ids, limit: 3 });
                // Drop anything already in the cart client-side too: the request was
                // sent before the last tap and a suggestion for what the guest just
                // ordered reads as the till not paying attention.
                const inCart = new Set(this.order.state.lines.map((l) => l.product.id));
                this.state.upsell = ((r && r.suggestions) || [])
                    .filter((s) => !inCart.has(s.product_id));
            } catch {
                // A suggestion is a nicety. It must never interrupt a sale.
                this.state.upsell = [];
            }
        }, 400);
    }

    /** Why this was suggested, in the cashier's words rather than the miner's. */
    upsellReason(s) {
        if (s.kind === "affinity" && s.with) {
            return _t("Goes with %s", s.with);
        }
        return _t("Popular");
    }

    /** Take a suggestion. Routed through the ordinary tap so a product WITH choices
     *  opens its configurator instead of landing in the cart unconfigured. */
    acceptUpsell(s) {
        const product = (this.state.products || []).find((p) => p.id === s.product_id);
        if (!product) {
            return;
        }
        this.onSelectProduct(product);
    }

    /** One tap, from the product screen, for a whole order.
     *
     *  Core's fast payment. The branch chooses which methods qualify and the server
     *  narrows that to ones that can complete without a device or a reference — a
     *  one-tap button that is always refused is worse than no button.
     *
     *  It goes through the SAME tender path as every other payment, so the ceilings,
     *  the duplicate policy, the credit gate and the audit trail all still apply. A
     *  shortcut around them would be a shortcut around the controls.
     */
    get fastMethods() {
        const ids = this.state.fastPayment || [];
        if (!ids.length || !this.order.lines.length) {
            return [];
        }
        return (this.state.methods || []).filter((m) => ids.includes(m.id));
    }

    async fastPay(method) {
        if (this.state.inFlight || !this.order.lines.length) {
            return;
        }
        // Opening the payment screen first is not a detour: it is what establishes
        // the authoritative total this tender is against.
        await this.goToPayment();
        const pay = this.state.payment;
        if (!pay) {
            return;
        }
        await this.submitTender({ method, amount: pay.remaining });
    }

    /** Choose the order type. Re-syncs, because the preset may reprice the order —
     *  a takeaway VAT rate or a delivery pricelist is not a label. */
    async choosePreset(presetId) {
        if (this.state.presetId === presetId) {
            return;
        }
        this.state.presetId = presetId;
        if (this.state.orderUuid && this.order.lines.length) {
            await this._ensurePersisted();
            await this._reloadOrder().catch(() => {});
        }
    }

    /** Show prices with or without tax.
     *
     *  `iface_tax_included` was shipped in the boot payload and nothing read it, so
     *  a branch that sets "Tax-Excluded Price" got tax-included prices anyway and had
     *  no way to say otherwise. Toggling affects DISPLAY only — the server prices
     *  every order regardless, and both figures came from it.
     */
    toggleTaxDisplay() {
        this.state.taxDisplay = this.state.taxDisplay === "total" ? "subtotal" : "total";
        // The store owns display pricing, so it has to be told too — otherwise the
        // grid flips and the cart does not.
        this.order.setTaxDisplay(this.state.taxDisplay);
    }

    get taxDisplayLabel() {
        return this.state.taxDisplay === "total"
            ? _t("Prices with tax")
            : _t("Prices without tax");
    }

    /** Courses, for a table. Starters now, mains held until the table is ready.
     *
     *  The endpoints have always worked; the only surface that reached them was a
     *  static page no route serves, which read the API token out of the URL.
     */
    openCourses() {
        if (!this.state.table) {
            return;
        }
        this.state.courses = true;
        this.state.actionError = "";
    }

    /** Answer a question about a product without leaving the order.
     *
     *  Not a screen change: the cart stays where it is and the cashier goes back to
     *  what they were ringing up. Anything that unwinds an in-progress order to
     *  answer "how many left?" will not be used twice. */
    openProductInfo(product) {
        this.state.infoProduct = product || null;
    }

    closeProductInfo() {
        this.state.infoProduct = null;
    }

    closeCourses() {
        this.state.courses = false;
    }

    /** A held course went to the kitchen. Those items are now the kitchen's, so the
     *  cart they were staged from must not still be sitting there waiting to be
     *  fired a second time. */
    async onCourseFired() {
        this.order.clear();
        await this._reloadOrder().catch(() => {});
    }

    /** Record which batch a tracked line came from.
     *
     *  The server has recorded lots since the traceability work; nothing on the till
     *  could collect one, so in practice every sale still went out unrecorded. A
     *  recall needs the answer and it exists only at the moment of sale.
     */
    openLots(line) {
        if (!line || !this.lotsNeeded(line)) {
            return;
        }
        this.state.lotLineKey = line.key;
        this.state.lotDraft = (line.lot_names || []).join("\n");
        this.state.lotError = "";
    }

    closeLots() {
        this.state.lotLineKey = null;
        this.state.lotDraft = "";
        this.state.lotError = "";
    }

    /** Assign a line to a seat. Only meaningful for a seated order: a takeaway
     *  counter has nobody to ask, which is why the control is not offered there. */
    openSeat(line) {
        this.state.seatLineKey = line ? line.key : null;
    }

    closeSeat() {
        this.state.seatLineKey = null;
    }

    get seatLine() {
        const key = this.state.seatLineKey;
        return key ? this.order.state.lines.find((l) => l.key === key) || null : null;
    }

    /** The seats to offer. The table's own capacity where it is known, because a
     *  four-top does not need a keypad — and a floor plan that already records seats
     *  should not make a cashier retype them. */
    get seatChoices() {
        const table = this.state.table;
        const n = Math.max(2, Math.min(24, Number(table && table.seats) || 8));
        return Array.from({ length: n }, (_, i) => i + 1);
    }

    /** Assign, then get out of the way: the panel closes on the tap. Assigning
     *  seats is done down a list of lines while a table calls them out, and a modal
     *  that has to be dismissed each time turns a fast job into a slow one. */
    chooseSeat(seat) {
        const line = this.seatLine;
        if (line) {
            // Travels on the next sync, exactly like a lot or a note: assigning a
            // seat is an annotation on a cart that has not been committed yet.
            this.order.setSeat(line, seat);
        }
        this.closeSeat();
    }

    lotsNeeded(line) {
        const t = line && line.product && line.product.tracking;
        return t === "lot" || t === "serial";
    }

    get lotLine() {
        const key = this.state.lotLineKey;
        return key ? this.order.state.lines.find((l) => l.key === key) || null : null;
    }

    setLotDraft(value) {
        this.state.lotDraft = value;
        this.state.lotError = "";
    }

    /** Apply the typed numbers, refusing here what the server would refuse anyway.
     *
     *  Checking the serial count in the browser is not the server trusting it — the
     *  server enforces the same rule regardless. It is so the cashier finds out while
     *  the numbers are still on screen rather than when the sale is rejected.
     */
    applyLots() {
        const line = this.lotLine;
        if (!line) {
            return;
        }
        const names = (this.state.lotDraft || "")
            .split(/[\n,]/).map((n) => n.trim()).filter(Boolean);
        const unique = [...new Set(names)];
        if (line.product.tracking === "serial") {
            if (unique.length !== names.length) {
                this.state.lotError = _t("The same serial number is listed twice.");
                return;
            }
            if (names.length && names.length !== line.qty) {
                this.state.lotError = _t(
                    "%s serial number(s) for a quantity of %s.", names.length, line.qty);
                return;
            }
        }
        line.lot_names = unique;
        this.closeLots();
    }

    get lotHint() {
        const l = this.lotLine;
        return l && l.product.tracking === "serial"
            ? _t("One serial number per item, one per line.")
            : _t("One batch number per line.");
    }

    get lotFieldLabel() {
        const l = this.lotLine;
        return l && l.product.tracking === "serial"
            ? _t("Serial numbers")
            : _t("Batch numbers");
    }

    /** Open the numpad on ONE line. */
    /** Ask the branch's scale what is on the pan.
     *
     *  Returns the weight for the pad to show. Errors are TRANSLATED here rather
     *  than passed through: "unstable" is not a fault a cashier should read as one —
     *  the pan settles in a second and they tap again — and "unit_mismatch" needs to
     *  name both units or it is not actionable.
     */
    async weighLine(line) {
        const product = (line && line.product) || {};
        try {
            const r = await this.api.call("/hardware/scale/read", {
                config_id: this.boot.config_id,
                uom: product.uom_name || undefined,
            });
            if (r && r.ok) {
                return r.weight;
            }
            throw new Error(this.scaleReason((r && r.error) || "", r || {}));
        } catch (err) {
            if (err && err.error) {
                throw new Error(this.scaleReason(err.error, err));
            }
            throw err;
        }
    }

    scaleReason(code, data) {
        const known = {
            unstable: _t("Still settling — try again in a moment."),
            not_positive: _t("Nothing on the scale."),
            out_of_range: _t("Too heavy for this scale."),
            unit_mismatch: _t("The scale reads in %s but this is priced per %s.",
                              data.scale_uom || "?", data.product_uom || "?"),
            scale_unreachable: _t("The scale did not answer."),
            scale_unconfigured: _t("This scale has no address set."),
            no_scale: _t("No scale is set up for this branch."),
            unreadable: _t("The scale sent something unreadable."),
            no_reply: _t("The scale did not answer."),
        };
        return known[code] || _t("The scale did not answer.");
    }

    /** Put a gratuity on the bill in front of the cashier.
     *
     *  Applied on the SERVER, which re-reads the order, refuses a figure larger than
     *  the bill, and — on an order already settled at a payment terminal — refuses
     *  outright, because the amount the provider captured is the one that has to
     *  match the settlement file.
     *
     *  The payment screen is re-seeded from the server's own totals rather than
     *  adjusted locally: a tip changes what is owed, and the one number a guest
     *  checks must not be arithmetic this browser did.
     */
    async applyTip(amount) {
        const uuid = this.state.payment && this.state.payment.uuid;
        if (!uuid) {
            return;
        }
        this.state.inFlight = true;
        this.state.tenderError = "";
        try {
            const r = await this.api.call("/orders/tip", {
                uuid, amount, expected_revision: this._revisionClaimFor(uuid),
            });
            this._noteFromServer(r, uuid);
            if (r && r.ok) {
                this.state.tip = r.tip;
                const total = r.amount_total;
                const paid = r.amount_paid;
                Object.assign(this.state.payment, {
                    total, paid,
                    remaining: roundTo(total - paid, this.decimals),
                });
            } else {
                this.state.tenderError = this.tipReason((r && r.error) || "", r || {});
            }
        } catch (err) {
            if (!this._failFromError(err)) {
                this.state.tenderError = err && err.error
                    ? this.tipReason(err.error, err)
                    : _t("The tip could not be applied.");
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    tipReason(code) {
        // Each sentence is ONE string literal. Two adjacent literals across a line
        // break is Python's concatenation, not JavaScript's — it is also a syntax
        // error that `node --check` reported as clean here, and the only symptom was
        // the whole Register silently failing to mount.
        const known = {
            tip_implausible: _t("That is more than the bill. Check the amount."),
            negative_tip: _t("A tip cannot be negative."),
            bad_amount: _t("That is not an amount."),
            already_tipped: _t("This order already has a tip."),
            tip_needs_provider_capture: _t("This was paid on a card terminal — add the tip there so the captured amount matches."),
            no_payment_to_adjust: _t("There is no payment to add a tip to."),
            unknown_order: _t("That order could not be found any more."),
        };
        return known[code] || _t("The tip could not be applied.");
    }

    /** Show the guest what the cashier is ringing up.
     *
     *  ``/cfd/push`` has existed since the display was built and nothing ever called
     *  it, so a counter screen showed whatever the prototype last put there. This is
     *  the missing half.
     *
     *  Debounced, because the hook fires on every mutation and a snapshot per
     *  keystroke is noise on a busy counter — a display that lags a third of a
     *  second is invisible to a guest, and one that floods the server is not.
     *
     *  It carries LINES AND MONEY ONLY. No customer, no cashier, no order id: the
     *  screen faces the public and everything on it is readable by whoever is
     *  standing there, so nothing goes on it that would matter if a stranger read it.
     *
     *  A failure is swallowed on purpose. A display is never allowed to break a sale.
     */
    pushCfd(state) {
        if (!this.state.hasCfd) {
            return;
        }
        clearTimeout(this._cfdTimer);
        this._cfdTimer = setTimeout(() => this._pushCfdNow(state), 350);
    }

    async _pushCfdNow(state) {
        try {
            const lines = this.order.state.lines.map((l) => ({
                name: l.product.name,
                qty: l.qty,
                // netUnitPrice, so a line discount the cashier typed shows on the
                // guest's screen too — the two must never quote different figures.
                price: this.order.netUnitPrice(l) * l.qty,
            }));
            // While a bill is being paid the SERVER's total is authoritative and is
            // what the guest is being asked for; before that, the till's running
            // estimate is the only number there is, and it is the same one the
            // cashier is looking at.
            const pay = this.state.payment;
            const estimate = this.order.estimatedTotal;
            await this.api.call("/cfd/push", {
                config_id: this.boot.config_id,
                lines,
                subtotal: estimate,
                tax: 0,
                total: pay ? pay.total : estimate,
                change: (pay && pay.change) || 0,
                state,
            });
        } catch {
            // never breaks a sale
        }
    }

    openNumpad(line) {
        this.state.padLineKey = line && line.key ? line.key : null;
    }

    closeNumpad() {
        this.state.padLineKey = null;
    }

    /** The line the pad is editing, resolved from the store by its stable key.
     *  Holding the object itself would go stale the moment the cart is rebuilt. */
    get padLine() {
        const key = this.state.padLineKey;
        if (!key) {
            return null;
        }
        return this.order.state.lines.find((l) => l.key === key) || null;
    }

    /** Whether this till may set a price at all.
     *
     *  `restrict_price_control` is the branch's switch and the SERVER enforces it;
     *  this only decides whether to offer the control. Showing a Price key that the
     *  server then refuses teaches a cashier to distrust the screen.
     */
    get allowPriceEntry() {
        // The branch switch the boot payload already reports. When the branch does
        // NOT restrict price control anybody may type a price; when it does, the
        // control is offered only where a manager could authorise it in person —
        // which is the same rule every other elevated verb uses.
        if (!this.state.priceControl) {
            return true;
        }
        return this.offers("orders.price_override");
    }

    padSetQty(qty) {
        const line = this.padLine;
        if (line) {
            this.order.setQty(line, qty);
            if (!this.padLine) {
                // qty 0 removed it; the pad has nothing left to edit
                this.closeNumpad();
            }
        }
    }

    padSetPrice(price) {
        const line = this.padLine;
        if (line) {
            this.order.setPrice(line, price);
        }
    }

    padSetDiscount(percent) {
        const line = this.padLine;
        if (line) {
            this.order.setLineDiscount(line, percent);
        }
    }

    /** Open the till without a sale.
     *
     *  The endpoint, its capability and its branch scoping have all existed; nothing
     *  on the register called it, so a cashier who needed to make change had to sell
     *  something to get the drawer open. It is audited server-side, because a drawer
     *  that opens with no money changing hands is both routine and the shape of the
     *  commonest till theft.
     */
    async openDrawer() {
        if (this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        this.state.actionError = "";
        try {
            const r = await this.api.call("/drawer/open", {}, { base: "/mezze/hardware" });
            if (!r || !r.ok) {
                this.state.actionError = (r && r.message)
                    || _t("The drawer could not be opened.");
            }
        } catch (e) {
            this.state.actionError = _t("The drawer could not be opened.");
        } finally {
            this.state.inFlight = false;
        }
    }

    async printBill() {
        if (!this.order.lines.length || this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        this.state.actionError = "";
        try {
            await this._ensurePersisted();
            const r = await this.api.call("/print/bill",
                                          { uuid: this.state.orderUuid },
                                          { base: "/mezze/hardware" });
            if (!r || !r.ok) {
                // A printer that is not there is worth saying out loud: the waiter is
                // standing at the table waiting for paper.
                this.state.actionError = (r && r.message)
                    || _t("The printer could not be reached.");
            }
        } catch (e) {
            this.state.actionError = _t("The printer could not be reached.");
        } finally {
            this.state.inFlight = false;
        }
    }

    async openCode() {
        if (!this.order.lines.length) {
            return;
        }
        // A code is attached to an ORDER, so one has to exist server-side first —
        // the same reason /orders/discount persists before it asks. Without this the
        // screen opens on a cart the server has never heard of and every code comes
        // back "order_not_found", which reads to the cashier as a bad code.
        try {
            await this._ensurePersisted();
        } catch {
            this.state.actionError = _t("Could not reach the server. Try again in a moment.");
            return;
        }
        this.state.entering_code = true;
        this.state.actionError = "";
    }

    closeCode() {
        this.state.entering_code = false;
    }

    /** A promo landed on the server, so the ORDER moved. Re-read it rather than
     *  patching the local total: the discount line is the server's, and guessing it
     *  here is how a till starts disagreeing with the receipt. */
    async onCodeApplied() {
        const uuid = this.state.orderUuid;
        if (!uuid) {
            return;
        }
        try {
            const res = await this.api.call("/orders/get", { uuid });
            if (res && res.lines) {
                this._loadOrderLines(res.lines);
            }
        } catch {
            // The promo IS applied — the server said so. Failing to re-read is a
            // display problem, and the payment screen reads the server's total
            // anyway, so it must not look like the code was rejected.
            this.state.actionError = _t("The code was applied. Refreshing the order failed.");
        }
    }

    /** A gift card is held, not spent. It settles at payment against the balance
     *  that exists then — another till may spend it in between. */
    onGiftCard(card) {
        this.state.giftCard = card;
    }

    openRefund() {
        if (!this.state.sessionId) {
            return;
        }
        this.state.refunding = true;
        this.state.actionError = "";
    }

    closeRefund() {
        this.state.refunding = false;
    }

    /** Post the refund. Re-thrown on failure so the screen can explain itself and
     *  stay open — closing it would make the cashier re-pick every line. */
    async submitRefund({ orderId, lines, reason, amount }, credential) {
        const res = await this.api.call("/orders/refund", {
            session_id: this.state.sessionId,
            original_order_id: orderId,
            uuid: makeUuid(),
            lines,
            reason,
            ...(credential || {}),
        });
        this.state.refunding = false;
        this.state.actionNote = _t("Refunded %s on %s.",
                                   this.fmt(amount), res.pos_reference || "");
        return res;
    }

    /** Called by the screen. On an approval refusal the SAME refund is handed to the
     *  manager gate rather than being lost — the cashier already chose the lines. */
    async onRefundDone(payload) {
        try {
            await this.submitRefund(payload, {});
        } catch (err) {
            const code = (err && err.error) || "";
            // BOTH refusals escalate, and for the same reason: a till does not hold
            // orders.refund on its own.
            //
            //   permission_denied  — the principal lacks the capability outright.
            //     A manager's PIN grants it for this ONE request through the gate's
            //     own elevation path, which is precisely what that path is for.
            //   approval_required  — the branch additionally requires a signed
            //     approval for refunds.
            //
            // Treating only the second as escalatable left the first looking like a
            // broken button: the cashier saw a raw error code and had no way forward,
            // on the most common configuration there is.
            if (code !== "approval_required" && code !== "permission_denied") {
                throw err;
            }
            this.state.refunding = false;
            this.state.managerGate = {
                action: "refund",
                title: _t("Approve this refund"),
                detail: _t("%s — %s", this.fmt(payload.amount), payload.reason),
                reasonRequired: false,
                run: async ({ managerCode, managerPin }) => {
                    await this.submitRefund(payload, {
                        manager_code: managerCode, manager_pin: managerPin,
                    });
                },
            };
        }
    }

    openCompGate(line) {
        if (!line || !this.state.sessionId) {
            return;
        }
        // A comp ALWAYS records an approver — that is the point of the audit trail —
        // so unlike a void it prompts even for a supervisor-capable terminal.
        this.state.managerGate = {
            action: "comp",
            title: _t("Comp this item"),
            detail: line.product.name,
            reasonRequired: true,
            run: async ({ managerCode, managerPin, reason }) => {
                await this._ensurePersisted();
                this._noteFromServer(await this.api.call("/orders/comp", {
                    session_id: this.state.sessionId,
                    order_uuid: this.state.orderUuid,
                    product_id: line.product.id,
                    reason: reason,
                    manager_code: managerCode,
                    manager_pin: managerPin,
                    expected_revision: this._revisionClaimFor(this.state.orderUuid),
                }), this.state.orderUuid);
                await this._reloadOrder();
            },
        };
    }

    async openVoidGate() {
        if (!this.order.lines.length || !this.state.sessionId) {
            return;
        }
        const gate = {
            action: "void",
            title: _t("Void this order"),
            detail: _t("The kitchen will be told to stop."),
            reasonRequired: true,
            run: async ({ managerCode, managerPin, reason }) => {
                await this._ensurePersisted();
                await this.api.call("/orders/void", {
                    session_id: this.state.sessionId,
                    order_uuid: this.state.orderUuid,
                    reason: reason,
                    manager_code: managerCode,
                    manager_pin: managerPin,
                });
                this.order.clear();
                this.state.orderUuid = null;
                // the claim belonged to that uuid; it means nothing for the next order
                this.state.orderRevision = null;
                this.state.orderRevisionUuid = null;
                this.state.editLock = null;
                this.state.sentOk = false;
            },
        };
        this.state.managerGate = gate;
        if (!this._needsApproval("orders.void")) {
            // the operator already holds the permission — running it is not a
            // "manager override", so do not stage one
            try {
                await this.runManagerGate({ reason: "" });
            } catch (err) {
                this.state.managerGate = null;
                this.state.actionError = (err && err.message)
                    || _t("That action did not go through.");
            }
        }
    }

    /** Runs the gated action. A refusal is RETHROWN so the gate can explain it and
     *  stay open — closing on a wrong PIN would make the manager start over. */
    async runManagerGate(credential) {
        const g = this.state.managerGate;
        if (!g || this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        this.state.actionError = "";
        try {
            await g.run(credential);
            this.state.managerGate = null;
        } catch (err) {
            if (this._failFromError(err)) {
                this.state.managerGate = null;
                return;
            }
            throw err;
        } finally {
            this.state.inFlight = false;
        }
    }

    cancelManagerGate() {
        this.state.managerGate = null;
    }

    /** Fire needs no approval — sending food to the kitchen is the normal job. */
    async fireOrder() {
        if (!this.order.lines.length || this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        this.state.actionError = "";
        try {
            await this._ensurePersisted();
            // RECONCILE, not append. This till holds the whole cart and has just
            // written all of it to the draft, so it cannot say which items are new —
            // the server works that out from what it has already fired. Sending the
            // cart into the append path (which is what this did) put every line on
            // the order a second time and doubled the total.
            await this.api.call("/orders/fire", {
                uuid: this.state.orderUuid,
                session_id: this.state.sessionId,
                table_id: this.state.table && this.state.table.id,
                lines: this.order.toSyncLines(),
                reconcile: true,
            });
            this.state.firedOk = true;
        } catch (err) {
            if (!this._failFromError(err)) {
                this.state.actionError = (err && err.message) || _t("Could not send to the kitchen.");
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    /** The order's class. Dine-in and Takeaway are the same order with a different
     *  service mode; Delivery is a different KIND of order (it needs a person, an
     *  address, a zone and a fee the branch decides), so it opens its own form
     *  instead of silently relabelling the ticket. */
    /**
     * The three ways an order can leave the counter.
     *
     * A table-bound order IS dine-in — saying otherwise would contradict the floor
     * plan the whole restaurant is working from. That rule is fine; what was not is
     * that it was enforced by ignoring the tap. The buttons looked live, took the
     * press and did nothing, which is indistinguishable from a broken till. They now
     * carry the constraint on the control itself, so the answer is on screen before
     * the cashier presses anything.
     */
    get orderTypes() {
        const onTable = this.isTableBound;
        const why = onTable
            ? _t("This order is seated at a table, so it is dine-in. Move or release the table to change that.")
            : "";
        return [
            { key: "eat_in", label: _t("Dine-in"),
              active: onTable || this.state.serviceMode === "eat_in",
              disabled: false, reason: "" },
            { key: "takeaway", label: _t("Takeaway"),
              active: !onTable && this.state.serviceMode === "takeaway",
              disabled: onTable, reason: why },
            { key: "delivery", label: _t("Delivery"),
              // Was hardcoded false, so choosing Delivery never looked chosen.
              active: !onTable && this.state.serviceMode === "delivery",
              disabled: onTable, reason: why },
        ];
    }

    async setOrderType(key) {
        // Say it rather than swallow it. A control that answers a press with nothing
        // teaches the cashier the till is unreliable.
        if (this.isTableBound && key !== "eat_in") {
            this.state.actionError = _t(
                "This order is seated at a table, so it is dine-in. Move or release the table to change that.");
            return;
        }
        if (key === "delivery") {
            // Choosing HOW an order leaves is something the cashier knows before the
            // first item — a phone order is a delivery from the first word. Refusing
            // the choice until the basket had something in it forced them to ring the
            // food in and only then discover the address was out of range. The choice
            // lands immediately; the address step needs a basket to quote a fee
            // against, so it waits for one and says so.
            this.state.serviceMode = "delivery";
            if (!this.order.lines.length) {
                this.state.actionNote = _t(
                    "Delivery selected. Add the items, then enter the address to get the fee.");
                return;
            }
            this.state.actionNote = "";
            this.state.deliveryForm = true;
            return;
        }
        this.state.serviceMode = key;
        if (this.state.orderUuid) {
            // already persisted — tell the server, do not wait for the next sync
            try {
                this._noteFromServer(await this.api.call("/orders/sync", {
                    uuid: this.state.orderUuid,
                    session_id: this.state.sessionId,
                    lines: this.order.toSyncLines(),
                    service_mode: key,
                    draft: true,
                    expected_revision: this._revisionClaimFor(this.state.orderUuid),
                }), this.state.orderUuid);
            } catch (e) {
                // the choice still stands for this order; it syncs again at charge
            }
        }
    }

    closeDeliveryForm() {
        this.state.deliveryForm = false;
    }

    /** Hand the working order to /delivery/create. The server prices the fee, fires
     *  the kitchen and creates the tracking record; the till does none of that.
     *
     *  delivery.manage is a supervisor capability — a plain till holds delivery.read
     *  only. Rather than widen what every terminal may do, a till that lacks it asks
     *  a supervisor to authorise the one order, through the same gate as a comp. A
     *  branch that takes phone orders all day should grant the capability instead of
     *  making someone type a PIN every time; this is the safe default, not the
     *  intended workflow for a delivery-heavy branch. */
    async createDelivery(details) {
        if (!this.can("delivery.manage")) {
            this.state.managerGate = {
                action: "delivery",
                title: _t("Authorise this delivery"),
                detail: details.address,
                reasonRequired: false,
                run: ({ managerCode, managerPin }) =>
                    this._postDelivery(details, managerCode, managerPin),
            };
            return { ok: true, gated: true };
        }
        return this._postDelivery(details);
    }

    async _postDelivery({ zoneId, fee, customer, phone, address, note },
                        managerCode, managerPin) {
        const uuid = this.state.orderUuid || makeUuid();
        const res = await this.api.call("/delivery/create", {
            uuid,
            session_id: this.state.sessionId,
            lines: this.order.toSyncLines(),
            fee,
            zone_id: zoneId,
            customer,
            phone,
            address,
            note,
            partner_id: this.state.customer ? this.state.customer.id : null,
            manager_code: managerCode,
            manager_pin: managerPin,
        });
        if (res && res.ok) {
            this.state.deliveryForm = false;
            this.order.clear();
            this.state.orderUuid = null;
            // the claim belonged to that uuid; it means nothing for the next order
            this.state.orderRevision = null;
            this.state.orderRevisionUuid = null;
            this.state.editLock = null;
            this.state.sentOk = false;
            this.state.lastDelivery = (res.delivery && res.delivery.tracking) || "";
        }
        return res;
    }

    /** Kitchen note on ONE line. Prompted inline rather than in a modal — it is a
     *  short, frequent, reversible edit, not a decision that needs ceremony. */
    openNote(line) {
        this.state.noteEdit = { key: line.key, name: line.product.name,
                                text: line.note || "" };
    }

    setNoteText(text) {
        if (this.state.noteEdit) {
            this.state.noteEdit.text = text;
        }
    }

    saveNote() {
        const n = this.state.noteEdit;
        if (!n) {
            return;
        }
        const line = this.order.state.lines.find((l) => l.key === n.key);
        if (line) {
            this.order.setNote(line, n.text);
        }
        this.state.noteEdit = null;
    }

    cancelNote() {
        this.state.noteEdit = null;
    }

    /** 86 a product: it stops being sellable across the branch, immediately. */
    async toggleEightySix(product, available) {
        if (!product || this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        this.state.actionError = "";
        try {
            await this.api.call("/menu/eightysix", {
                config_id: this.boot.config_id,
                product_id: product.id,
                available: !!available,
            });
            const p = this.state.products.find((x) => x.id === product.id);
            if (p) {
                p.available = !!available;
            }
        } catch (err) {
            if (!this._failFromError(err)) {
                this.state.actionError = (err && err.message) || _t("Could not change availability.");
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    // ---- S2C-6 customer account / credit ----------------------------------
    // A Customer Account (pay_later) sale is booked against the customer's native
    // receivable. It NEVER works anonymously and the credit CHECK is Odoo's
    // (partner.credit vs credit_limit) — the cashier UI only surfaces the policy
    // outcome the server returns; it never decides credit itself.
    /** Points as the design labels them on a result row. Whole numbers: a
     *  cashier scanning a list does not need two decimals of loyalty. */
    ptsLabel(points) {
        return _t("%s pts", Math.round(Number(points) || 0));
    }

    openCustomerPicker() {
        this.state.customerPicker = {
            query: "", results: [], busy: false, error: "", note: "",
            action: null, amount: "", methodId: this._defaultCashMethodId(),
            summary: null,
            // create-a-walk-in fields
            creating: false, newName: "", newPhone: "",
        };
    }

    closeCustomerPicker() {
        this.state.customerPicker = null;
    }

    _defaultCashMethodId() {
        const cash = this.state.methods.find((m) => m.mezze_mode === "cash" || m.is_cash_count);
        return cash ? cash.id : (this.state.methods[0] && this.state.methods[0].id) || null;
    }

    async searchCustomers(query) {
        const p = this.state.customerPicker;
        if (!p) {
            return;
        }
        p.query = query;
        p.busy = true;
        p.error = "";
        try {
            const res = await this.api.call("/customer/search", {
                query, config_id: this.boot.config_id,
            });
            p.results = res.customers || [];
        } catch (err) {
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
                return;
            }
            p.error = _t("Customer lookup failed.");
        } finally {
            p.busy = false;
        }
    }

    // Choose this customer for the current sale (does not close the picker so the
    // cashier can still deposit / settle). The account tender then reads the summary.
    async chooseCustomer(c) {
        this.state.customer = { ...c };
        const p = this.state.customerPicker;
        if (p) {
            await this._refreshPickerSummary();
        }
    }

    clearCustomer() {
        this.state.customer = null;
    }

    async _refreshPickerSummary() {
        const p = this.state.customerPicker;
        if (!p || !this.state.customer) {
            return;
        }
        try {
            p.summary = await this.api.call("/customer/summary", {
                partner_id: this.state.customer.id, config_id: this.boot.config_id,
            });
        } catch {
            p.summary = null;
        }
    }

    // Deposit money to / settle the due of the selected account customer, via a REAL
    // cash/bank tender. Records a native inbound account.payment server-side — no
    // sales revenue, no Mezze balance. `kind` = 'deposit' | 'settle'.
    async accountService(kind) {
        const p = this.state.customerPicker;
        if (!p || !this.state.customer || this.state.inFlight) {
            return;
        }
        const amount = parseFloat(p.amount);
        if (!Number.isFinite(amount) || amount <= 0) {
            p.error = _t("Enter a positive amount.");
            return;
        }
        this.state.inFlight = true;
        p.error = "";
        p.note = "";
        try {
            const res = await this.api.call("/customer/" + kind, {
                partner_id: this.state.customer.id,
                amount,
                payment_method_id: p.methodId,
                config_id: this.boot.config_id,
            });
            p.summary = res.summary || p.summary;
            p.amount = "";
            p.note = kind === "deposit"
                ? _t("Deposit recorded.") : _t("Settlement recorded.");
        } catch (err) {
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
                return;
            }
            const data = (err && err.data) || {};
            p.error = data.error === "invalid_tender"
                ? _t("Choose a cash or bank method for deposits/settlements.")
                : (data.message || _t("Could not record the payment."));
        } finally {
            this.state.inFlight = false;
        }
    }

    // Over-limit soft warn → cashier explicitly authorizes the credit sale.
    async creditWarnContinue() {
        const w = this.state.creditWarn;
        if (!w) {
            return;
        }
        this.state.creditWarn = null;
        await this.submitTender({ ...w.pending, allow_credit: true });
    }

    creditWarnCancel() {
        this.state.creditWarn = null;
    }

    // Over-limit manager approval → resubmit WITH the manager PIN (server verifies
    // role rank; a cashier can never self-approve its own credit override).
    async creditManagerApprove({ code, pin, reason }) {
        const m = this.state.creditManager;
        if (!m || this.state.inFlight) {
            return;
        }
        await this.submitTender({
            ...m.pending, manager_code: code, manager_pin: pin, manager_reason: reason || "",
        });
    }

    creditManagerCancel() {
        this.state.creditManager = null;
    }

    // ---- S2C-3 integrated terminal ----------------------------------------
    // The debug/test simulator scenario (TEST-ONLY). Real providers ignore it and
    // are refused server-side. Set via the debug handle in acceptance tests.
    _terminalScenario() {
        return (this.env.mezze && this.env.mezze.simScenario) || "success";
    }

    // Cashier picked an integrated method → open the reader UI in READY. Root owns
    // the full request lifecycle (start → waiting → authoritative result).
    onTerminalSelect({ method, deviceId, deviceName, remaining }) {
        this.state.terminal = {
            state: TS.READY,
            methodName: method.name,
            method,
            provider: method.mezze_terminal_provider || "",
            deviceId: deviceId || null,
            device: deviceName || "",
            amount: remaining,
            requestId: null,
            error_code: "",
            uncertain: false,
            referenceMasked: "",
            forceError: "",
            scenario: this._terminalScenario(),
            aborted: false,
            _recorded: false,
        };
    }

    // Send the amount to the terminal, then run the adapter timeline. The adapter
    // NEVER decides the outcome — it calls complete() and the server settles.
    async startTerminal({ amount } = {}) {
        const t = this.state.terminal;
        if (!t || t.state !== TS.READY || this.state.inFlight) {
            return;
        }
        if (amount != null) {
            t.amount = amount;
        }
        t.aborted = false;
        t.error_code = "";
        t.forceError = "";
        t.state = TS.SENDING;
        this.state.tenderError = "";
        this.state.inFlight = true;
        let res;
        try {
            res = await this.api.call("/terminal/start", {
                uuid: this.state.payment.uuid,
                payment_method_id: t.method.id,
                device_id: t.deviceId || undefined,
                amount: t.amount,
                scenario: t.scenario,
            });
        } catch (err) {
            this._terminalCatch(err, t);
            this.state.inFlight = false;
            return;
        }
        this.state.inFlight = false;
        t.requestId = res.request_id;
        t.amount = res.amount;
        t.state = res.state; // waiting_customer
        const adapter = getTerminalAdapter(t.provider);
        try {
            await adapter.run({
                requestId: res.request_id,
                scenario: t.scenario,
                setState: (s) => {
                    if (!t.aborted) {
                        t.state = s;
                    }
                },
                complete: () => this._terminalComplete(),
                fail: (code) => {
                    t.state = TS.ERROR;
                    t.error_code = code;
                    t.uncertain = true;
                },
            });
        } catch (err) {
            this._terminalCatch(err, t);
        }
    }

    async _terminalComplete() {
        const t = this.state.terminal;
        if (!t || t.aborted || t.state === TS.CANCELLED || t.state === TS.APPROVED) {
            return;
        }
        this.state.inFlight = true;
        try {
            const res = await this.api.call("/terminal/complete", {
                request_id: t.requestId,
                outcome: "approved",
            });
            this._applyTerminalResult(res, t);
        } catch (err) {
            const data = (err && err.data) || {};
            if (err && err.kind === "network") {
                // lost response — recover the authoritative state, never re-charge
                await this._terminalRecover(t);
            } else if (data.state) {
                // controller returns the txn payload alongside a 409 (e.g. provider pending)
                this._applyTerminalResult(data, t);
            } else {
                t.state = TS.ERROR;
                t.uncertain = true;
                t.error_code = data.error || "error";
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    _applyTerminalResult(res, t) {
        t.state = res.state;
        t.uncertain = !!res.uncertain;
        t.error_code = res.error_code || "";
        t.referenceMasked = res.reference_masked || "";
        if (res.state === TS.APPROVED) {
            this._recordTerminalTender(res, t);
        }
    }

    _recordTerminalTender(res, t) {
        const pay = this.state.payment;
        if (res.pos_reference) {
            pay.pos_reference = res.pos_reference;
        }
        if (!t._recorded) {
            t._recorded = true;
            pay.tenders.push({
                method: t.methodName,
                mode: "odoo_terminal",
                amount: roundTo(t.amount, this.decimals),
                device: t.device || "",
                reference: t.referenceMasked || "",
                change: 0,
            });
        }
        pay.paid = res.paid ?? pay.paid + t.amount;
        pay.remaining = res.remaining ?? roundTo(pay.total - pay.paid, this.decimals);
        if ((res.remaining !== undefined ? res.remaining : pay.remaining) <= 0) {
            this.finalize();
        }
    }

    async _terminalRecover(t) {
        if (!t.requestId) {
            t.state = TS.UNKNOWN;
            t.uncertain = true;
            return;
        }
        try {
            const res = await this.api.call("/terminal/status", { request_id: t.requestId });
            this._applyTerminalResult(res, t);
        } catch {
            t.state = TS.UNKNOWN;
            t.uncertain = true;
        }
    }

    _terminalCatch(err, t) {
        if (err && err.kind === "auth") {
            this.state.phase = "auth_required";
            return;
        }
        if (err && err.kind === "network") {
            t.state = TS.ERROR;
            t.uncertain = true;
            t.error_code = "network";
            return;
        }
        const data = (err && err.data) || {};
        if (["terminal_start_rejected", "simulator_disabled", "not_integrated",
             "order_not_payable"].includes(data.error)) {
            // start never opened a live request → no charge risk; allow re-select
            t.state = TS.ERROR;
            t.uncertain = false;
            t.error_code = data.error;
            this.state.tenderError = data.message || _t("The terminal could not start.");
        } else {
            t.state = TS.ERROR;
            t.uncertain = true;
            t.error_code = data.error || "error";
        }
    }

    // Cancel a live request (native cancel path). No payment. Distinct from Force
    // Done. `silent` just clears the terminal state (e.g. leaving the method).
    async terminalCancel(opts = {}) {
        const t = this.state.terminal;
        if (!t) {
            return;
        }
        t.aborted = true;
        if (t.requestId && [TS.SENDING, TS.WAITING, TS.PROCESSING].includes(t.state)) {
            this.state.inFlight = true;
            try {
                const res = await this.api.call("/terminal/cancel", { request_id: t.requestId });
                t.state = res.state;
            } catch {
                t.state = TS.CANCELLED;
            } finally {
                this.state.inFlight = false;
            }
        } else if (!opts.silent) {
            t.state = TS.CANCELLED;
        }
        if (opts.silent) {
            this.state.terminal = null;
        }
    }

    // Fresh attempt on the same method for the CURRENT remaining balance.
    terminalRetry() {
        const t = this.state.terminal;
        if (!t) {
            return;
        }
        this.state.terminal = {
            ...t,
            state: TS.READY,
            requestId: null,
            error_code: "",
            uncertain: false,
            referenceMasked: "",
            forceError: "",
            aborted: false,
            _recorded: false,
            amount: this.state.payment.remaining,
            scenario: this._terminalScenario(),
        };
    }

    // Manager-gated Force Done over an uncertain/failed result. Cashier can never
    // self-force (server enforces role rank). One payment, force-done provenance.
    async terminalForceDone({ code, pin, reason }) {
        const t = this.state.terminal;
        if (!t || !t.requestId || this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        t.forceError = "";
        try {
            const res = await this.api.call("/terminal/force_done", {
                request_id: t.requestId,
                manager_code: code,
                manager_pin: pin,
                manager_reason: reason || "",
            });
            this._applyTerminalResult(res, t);
        } catch (err) {
            const data = (err && err.data) || {};
            if (data.error === "insufficient_role") {
                t.forceError = _t("That user is not authorized to approve (manager required).");
            } else if (data.error === "bad_credentials") {
                t.forceError = _t("Invalid manager code or PIN.");
            } else if (data.error === "manager_required") {
                t.forceError = _t("Manager authorization is required.");
            } else {
                t.forceError = data.message || _t("Force Done was rejected.");
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    // ---- S2C-7 automated cash machine -------------------------------------
    // The debug/test simulator scenario (TEST-ONLY). Real devices ignore it and are
    // refused server-side.
    _cashMachineScenario() {
        return (this.env.mezze && this.env.mezze.cashSimScenario) || "success_exact";
    }

    _cashMachineInserted() {
        // TEST-ONLY: a simulated inserted amount for the success_with_change scenario.
        return (this.env.mezze && this.env.mezze.cashSimInserted) || 0;
    }

    // Cashier picked a cash-machine method → open the machine UI in READY. Root owns
    // the full request lifecycle (start → waiting_cash → counting → authoritative result).
    onCashMachineSelect({ method, deviceId, deviceName, remaining }) {
        this.state.cashmachine = {
            state: CMS.READY,
            methodName: method.name,
            method,
            provider: method.mezze_terminal_provider || "",
            deviceId: deviceId || null,
            device: deviceName || "",
            amount: remaining,
            inserted: 0,
            change: 0,
            requestId: null,
            error_code: "",
            uncertain: false,
            forceError: "",
            scenario: this._cashMachineScenario(),
            aborted: false,
            _recorded: false,
        };
    }

    // Send the amount to the machine, then run the adapter timeline. The adapter NEVER
    // decides the outcome — it calls complete() and the server settles.
    async startCashMachine() {
        const m = this.state.cashmachine;
        if (!m || m.state !== CMS.READY || this.state.inFlight) {
            return;
        }
        m.aborted = false;
        m.error_code = "";
        m.forceError = "";
        m.state = CMS.SENDING;
        this.state.tenderError = "";
        this.state.inFlight = true;
        let res;
        try {
            res = await this.api.call("/cashmachine/start", {
                uuid: this.state.payment.uuid,
                payment_method_id: m.method.id,
                device_id: m.deviceId || undefined,
                scenario: m.scenario,
                sim_inserted: this._cashMachineInserted() || undefined,
            });
        } catch (err) {
            this._cashMachineCatch(err, m);
            this.state.inFlight = false;
            return;
        }
        this.state.inFlight = false;
        m.requestId = res.request_id;
        m.amount = res.amount;
        const adapter = getCashMachineAdapter(m.provider);
        try {
            await adapter.run({
                scenario: m.scenario,
                setState: (s) => {
                    if (!m.aborted) {
                        m.state = s;
                    }
                },
                complete: () => this._cashMachineComplete(),
                fail: (code) => {
                    m.state = CMS.ERROR;
                    m.error_code = code;
                    m.uncertain = code === "device_pending" ? false : true;
                },
            });
        } catch (err) {
            this._cashMachineCatch(err, m);
        }
    }

    async _cashMachineComplete() {
        const m = this.state.cashmachine;
        if (!m || m.aborted || [CMS.CANCELLED, CMS.APPROVED].includes(m.state)) {
            return;
        }
        this.state.inFlight = true;
        try {
            const res = await this.api.call("/cashmachine/complete", { request_id: m.requestId });
            this._applyCashMachineResult(res, m);
        } catch (err) {
            const data = (err && err.data) || {};
            if (err && err.kind === "network") {
                await this._cashMachineRecover(m);
            } else if (data.state) {
                this._applyCashMachineResult(data, m);
            } else {
                m.state = CMS.ERROR;
                m.uncertain = true;
                m.error_code = data.error || "error";
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    _applyCashMachineResult(res, m) {
        // server canonical → cash UI state
        const map = { approved: CMS.APPROVED, cancelled: CMS.CANCELLED,
                      error: CMS.ERROR, unknown: CMS.UNKNOWN };
        m.state = map[res.state] || m.state;
        m.uncertain = !!res.uncertain;
        m.error_code = res.error_code || "";
        m.inserted = res.inserted || 0;
        m.change = res.change || 0;
        if (res.state === "approved") {
            this._recordCashMachineTender(res, m);
        }
    }

    _recordCashMachineTender(res, m) {
        const pay = this.state.payment;
        if (res.pos_reference) {
            pay.pos_reference = res.pos_reference;
        }
        if (!m._recorded) {
            m._recorded = true;
            pay.tenders.push({
                method: m.methodName,
                mode: "cash_machine",
                amount: roundTo(res.amount ?? m.amount, this.decimals),
                device: m.device || "",
                reference: "",
                change: res.change || 0,   // physical change returned by the machine
            });
        }
        pay.paid = res.paid ?? pay.paid + m.amount;
        pay.remaining = res.remaining ?? roundTo(pay.total - pay.paid, this.decimals);
        if ((res.remaining !== undefined ? res.remaining : pay.remaining) <= 0) {
            this.finalize();
        }
    }

    async _cashMachineRecover(m) {
        if (!m.requestId) {
            m.state = CMS.UNKNOWN;
            m.uncertain = true;
            return;
        }
        try {
            const res = await this.api.call("/cashmachine/status", { request_id: m.requestId });
            this._applyCashMachineResult(res, m);
        } catch {
            m.state = CMS.UNKNOWN;
            m.uncertain = true;
        }
    }

    _cashMachineCatch(err, m) {
        if (err && err.kind === "auth") {
            this.state.phase = "auth_required";
            return;
        }
        if (err && err.kind === "network") {
            m.state = CMS.ERROR;
            m.uncertain = true;
            m.error_code = "network";
            return;
        }
        const data = (err && err.data) || {};
        if (["cashmachine_start_rejected", "simulator_disabled", "not_cash_machine",
             "order_not_payable"].includes(data.error)) {
            // start never opened a live request → no charge risk; allow re-select
            m.state = CMS.ERROR;
            m.uncertain = false;
            m.error_code = data.error;
            this.state.tenderError = data.message || _t("The cash machine could not start.");
        } else {
            m.state = CMS.ERROR;
            m.uncertain = true;
            m.error_code = data.error || "error";
        }
    }

    async cashMachineCancel(opts = {}) {
        const m = this.state.cashmachine;
        if (!m) {
            return;
        }
        m.aborted = true;
        if (m.requestId && [CMS.SENDING, CMS.WAITING_CASH, CMS.COUNTING, CMS.RETURNING_CHANGE].includes(m.state)) {
            this.state.inFlight = true;
            try {
                const res = await this.api.call("/cashmachine/cancel", { request_id: m.requestId });
                m.state = CMS.CANCELLED;
                m.error_code = res.error_code || "";
            } catch {
                m.state = CMS.CANCELLED;
            } finally {
                this.state.inFlight = false;
            }
        } else if (!opts.silent) {
            m.state = CMS.CANCELLED;
        }
        if (opts.silent) {
            this.state.cashmachine = null;
        }
    }

    cashMachineRetry() {
        const m = this.state.cashmachine;
        if (!m) {
            return;
        }
        this.state.cashmachine = {
            ...m,
            state: CMS.READY,
            requestId: null,
            error_code: "",
            uncertain: false,
            forceError: "",
            aborted: false,
            _recorded: false,
            inserted: 0,
            change: 0,
            amount: this.state.payment.remaining,
            scenario: this._cashMachineScenario(),
        };
    }

    async cashMachineForceDone({ code, pin, reason }) {
        const m = this.state.cashmachine;
        if (!m || !m.requestId || this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        m.forceError = "";
        try {
            const res = await this.api.call("/cashmachine/force_done", {
                request_id: m.requestId, manager_code: code, manager_pin: pin,
                manager_reason: reason || "",
            });
            this._applyCashMachineResult(res, m);
        } catch (err) {
            const data = (err && err.data) || {};
            if (data.error === "insufficient_role") {
                m.forceError = _t("That user is not authorized to approve (manager required).");
            } else if (data.error === "bad_credentials") {
                m.forceError = _t("Invalid manager code or PIN.");
            } else if (data.error === "manager_required") {
                m.forceError = _t("Manager authorization is required.");
            } else {
                m.forceError = data.message || _t("Force Done was rejected.");
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    // ---- S2C-4 bank-app QR ------------------------------------------------
    // Cashier picked a QR method → generate the native QR for the current remaining.
    async onQrSelect({ method, amount }) {
        this.state.qr = {
            method,
            token: null,
            state: "pending",
            amount,
            reference: "",
            image: "",
            payload: "",
            error: "",
            generating: true,
        };
        await this._qrGenerate(method, amount);
    }

    async _qrGenerate(method, amount) {
        const q = this.state.qr;
        if (!q) {
            return;
        }
        q.generating = true;
        q.error = "";
        q.image = "";
        try {
            const res = await this.api.call("/payment/qr/generate", {
                uuid: this.state.payment.uuid,
                payment_method_id: method.id,
                amount,
            });
            q.token = res.qr_token;
            q.amount = res.amount;
            q.reference = res.reference || "";
            q.image = res.image || "";
            q.payload = res.payload || "";
            q.state = res.state;
        } catch (err) {
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
                return;
            }
            const data = (err && err.data) || {};
            q.error = data.message || (err && err.message) || _t("Could not generate the QR code.");
        } finally {
            q.generating = false;
        }
    }

    // Manual cashier confirmation → records ONE payment (server-authoritative,
    // stale-guarded, idempotent). Provenance is manual (bank not auto-verified).
    async qrConfirm() {
        const q = this.state.qr;
        if (!q || !q.token || this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        q.error = "";
        try {
            const res = await this.api.call("/payment/qr/confirm", { qr_token: q.token });
            const pay = this.state.payment;
            if (res.pos_reference) {
                pay.pos_reference = res.pos_reference;
            }
            pay.tenders.push({
                method: q.method.name,
                mode: "bank_qr",
                amount: roundTo(q.amount, this.decimals),
                device: "",
                reference: maskRef(q.reference),
                change: 0,
            });
            pay.paid = res.paid ?? pay.paid + q.amount;
            pay.remaining = res.remaining ?? roundTo(pay.total - pay.paid, this.decimals);
            this.state.qr = null;
            if ((res.remaining !== undefined ? res.remaining : pay.remaining) <= 0) {
                await this.finalize();
            }
        } catch (err) {
            const data = (err && err.data) || {};
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
            } else if (data.error === "qr_confirm_rejected") {
                // stale QR (order changed) — regenerate for the new remaining
                q.error = _t("The order changed — a new QR was generated for the updated amount.");
                await this._qrGenerate(q.method, this.state.payment.remaining);
            } else if (err && err.kind === "network") {
                q.error = _t("Local Mezze server unavailable — payment not taken.");
            } else {
                q.error = data.message || _t("Payment could not be confirmed.");
            }
        } finally {
            this.state.inFlight = false;
        }
    }

    async qrCancel(opts = {}) {
        const q = this.state.qr;
        if (!q) {
            return;
        }
        if (q.token && q.state !== "confirmed") {
            try {
                await this.api.call("/payment/qr/cancel", { qr_token: q.token });
            } catch {
                // best-effort; no payment was created regardless
            }
        }
        if (opts.silent) {
            this.state.qr = null;
        } else {
            q.state = "cancelled";
        }
    }

    async qrRetry() {
        const q = this.state.qr;
        if (!q) {
            return;
        }
        await this._qrGenerate(q.method, this.state.payment.remaining);
    }

    // ---- finalization / receipt -------------------------------------------
    async finalize() {
        this.state.phase = "processing";
        const pay = this.state.payment;
        let breakdown = null;
        try {
            breakdown = await this.api.call("/payment/breakdown", { uuid: pay.uuid });
        } catch {
            breakdown = null;
        }
        const lines = breakdown && breakdown.payments
            ? breakdown.payments.map((p) => ({
                method: p.method,
                amount: p.amount,
                reference: p.ref_masked || "",
                device: p.device || "",
            }))
            : pay.tenders.map((t) => ({
                method: t.method, amount: t.amount, reference: t.reference, device: t.device,
            }));
        // Cash change is physical money returned (UI-tracked), not part of the
        // recorded pos.payment rows, so /payment/breakdown reports 0; surface the
        // larger of the two so the receipt shows any change actually given.
        const totalChange = pay.tenders.reduce((s, t) => s + (t.change || 0), 0);
        this.state.receipt = {
            pos_reference: (breakdown && breakdown.pos_reference) || pay.pos_reference || "",
            total: breakdown ? breakdown.total : pay.total,
            paid: breakdown ? breakdown.paid : pay.paid,
            // Tax comes from the ORDER, computed by Odoo's own engine. There is no
            // till-side arithmetic here on purpose: a receipt that derived its own
            // tax could disagree with the accounting entry behind it, and the guest's
            // copy is the one a tax authority reads.
            subtotal: breakdown ? breakdown.subtotal : null,
            tax: breakdown ? breakdown.tax : null,
            tax_lines: (breakdown && breakdown.tax_lines) || [],
            order_uuid: pay.uuid || null,
            change: roundTo(Math.max((breakdown && breakdown.change) || 0, totalChange), this.decimals),
            payments: lines,
            // The server's own lines when it answered, so the printed copy matches the
            // order that was actually recorded rather than the cart that was typed.
            items: (breakdown && breakdown.items && breakdown.items.length)
                ? breakdown.items.map((l, i) => ({
                    id: i, name: l.name, qty: l.qty, price: l.price, total: l.total,
                }))
                : (this.state.snapshot || []),
            branch: this.branchName,
            cashier: this.userName,
            datetime: new Date().toLocaleString(),
        };
        this.order.clear();
        // R2A CP8: a full settlement releases the table on the backend (the order
        // left 'draft', so /floors reports it available). Drop the now-stale table
        // binding here — the ONE payment-authoritative point (finalize runs only when
        // remaining <= 0) — so the Register doesn't stay attached to a freed table and
        // the next order can't reuse the paid order's uuid or re-occupy that table.
        this.state.table = null;
        this.state.orderUuid = null;
        // the claim belonged to that uuid; it means nothing for the next order
        this.state.orderRevision = null;
        this.state.orderRevisionUuid = null;
        this.state.editLock = null;
        this.state.phase = "receipt";
    }

    /**
     * Send the receipt to the station printer, if this branch has one.
     *
     * Returns a falsy result when there is nothing to print to, which is the
     * signal for the Receipt component to fall back to the browser's own print
     * dialog. Every failure is treated the same way — a cashier holding a guest
     * who wants a copy is not helped by an error message about a printer.
     */
    async printReceipt() {
        const uuid = this.state.receipt && this.state.receipt.order_uuid;
        if (!uuid) {
            return null;
        }
        try {
            // The hardware endpoints live outside the versioned API prefix.
            return await this.api.call("/print/receipt", { uuid },
                                       { base: "/mezze/hardware" });
        } catch {
            return null;
        }
    }

    // ---- receipt -----------------------------------------------------------
    newOrder() {
        this.order.clear();
        this.state.payment = null;
        this.state.receipt = null;
        this.state.snapshot = null;
        this.state.warn = null;
        this.state.managerReq = null;
        this.state.creditWarn = null;
        this.state.creditManager = null;
        this.state.customerPicker = null;
        this.state.customer = null;
        this.state.terminal = null;
        this.state.cashmachine = null;
        this.state.qr = null;
        this.state.tenderError = "";
        this.state.errorMsg = "";
        // R1B: a brand-new order starts on a clean, unfiltered menu (see backToMenu).
        this.state.search = "";
        this.state.searchIndex = 0;
        this.state.phase = "menu";
    }

    retry() {
        this.state.errorMsg = "";
        this.bootstrap();
    }
}
