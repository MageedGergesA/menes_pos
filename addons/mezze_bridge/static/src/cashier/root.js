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
import { SplitBill } from "./components/split_bill";

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
import { formatMoney, roundTo, connSemantic, filterProducts, clampIndex } from "./order_store";
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
    static components = { ProductGrid, Cart, PaymentScreen, Receipt, CashMachine, Workspace, SettingsPanel, WorkspaceRail, ManagerGate, DeliveryForm, ProductConfig, SessionClose, SplitBill };
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
            phase: "booting", // booting|auth_required|error|menu|payment|processing|receipt
            // Prototype IA: which workspace the rail has opened in the modal host, and the
            // standalone URL it mirrors (null when the workspace has no page of its own).
            workspace: null,
            // resolved before first paint by the appearance bootstrap in the page template
            mzMode: (typeof document !== "undefined"
                && document.documentElement.getAttribute("data-mz-mode")) || "light",
            errorMsg: "",
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
            noteEdit: null,      // { key, name, text }
            // Dine-in | Takeaway | Delivery. A table-bound order is dine-in by
            // definition and the control says so rather than pretending otherwise.
            serviceMode: "eat_in",
            deliveryForm: false,
            actionError: "",     // comp/void/fire/86 failure, shown on the order panel
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
        const ids = this.order.favoriteIds(8);
        if (!ids.length) {
            return [];
        }
        const byId = new Map(this.state.products.map((p) => [p.id, p]));
        return ids.map((id) => byId.get(id)).filter(Boolean);
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
    openSplitBill() {
        if (this.order.isEmpty || this.state.inFlight) {
            return;
        }
        this.state.splitting = true;
    }

    closeSplitBill() {
        this.state.splitting = false;
    }

    /** A freshly created child goes straight to Payment — no Save, no Orders, no
     *  hunting for the check that was made two seconds ago. */
    onSplitChildReady(child) {
        this.state.splitting = false;
        this.state.splitChild = child || null;
        this.goToPayment();
    }

    /** The close needs a capability the till does not hold, so it borrows one for
     *  a single call through the same manager prompt a comp or a refund uses. */
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
    get workspaceTitle() {
        return {
            ops: _t("Live Ops"), queue: _t("Beverage Queue"), manager: _t("Manager"),
            reports: _t("Reports"), delivery: _t("Delivery"), hq: _t("HQ"),
            ck: _t("Central Kitchen"), settings: _t("Settings"),
            close: _t("End of day"),
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
    handleKey(ev) {
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

    _failFromError(err) {
        if (err && err.kind === "auth") {
            this.state.phase = "auth_required";
            return true;
        }
        return false;
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
            this.state.categories = data.categories || [];
            this.state.products = (data.products || []).map((p) => ({
                id: p.id,
                name: p.name,
                list_price: p.list_price,
                available: p.available !== false,
                has_image: !!p.has_image,
                pos_categ_ids: p.pos_categ_ids || [],
                // CONV-3: /bootstrap has always shipped each product's real POS-time
                // attribute groups; this line used to drop them, so the till could not
                // sell a burger without onions at all. Same payload, same shape and the
                // same rules the lane uses — one configurator contract, not two.
                modifiers: p.modifiers || [], combos: p.combos || [], is_combo: !!p.is_combo,
            }));
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
            });
            // reflect the authoritative uuid (idempotent) so a second send is the same order
            if (res.uuid) {
                this.state.orderUuid = res.uuid;
                this.state.table.order_uuid = res.uuid;
            }
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
    _loadOrderLines(lines) {
        this.order.clear();
        for (const l of (lines || [])) {
            const product = this.state.products.find((p) => p.id === l.product_id)
                || { id: l.product_id, name: l.name, list_price: l.price_unit, available: true };
            const n = Math.max(1, Math.round(l.qty || 1));
            // Carry the server's EFFECTIVE price. A comp is stored as a 100% discount
            // rather than a zeroed price_unit, so reading price_unit alone rebuilt the
            // line at full price and overstated the total.
            const discount = typeof l.discount === "number" ? l.discount : 0;
            const unitPrice = typeof l.price_unit === "number"
                ? l.price_unit * (1 - discount / 100)
                : undefined;
            const comped = discount >= 100;
            for (let i = 0; i < n; i++) {
                this.order.addProduct(product, { noBump: true, unitPrice, comped });
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
            };
            if (this.isTableBound) {
                body.table_id = this.state.table.id;
            }
            const res = await this.api.call("/orders/sync", body);
            const finalUuid = res.uuid || uuid;
            await this.api.call("/orders/park", { uuid: finalUuid, parked: true });
            // clean slate for the next order (fresh uuid/table/customer)
            this.order.clear();
            this.state.orderUuid = null;
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
            await this.api.call("/orders/sync", {
                uuid, session_id: this.state.sessionId,
                lines: this.order.toSyncLines(), draft: true,
            });
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
            const uuid = this.isTableBound
                ? (this.state.orderUuid || makeUuid())
                : makeUuid();
            const syncBody = {
                uuid,
                session_id: this.state.sessionId,
                lines: this.order.toSyncLines(),
                draft: true,
            };
            if (this.isTableBound) {
                syncBody.table_id = this.state.table.id;
            }
            const res = await this.api.call("/orders/sync", syncBody);
            this.state.orderUuid = uuid;
            this.state.snapshot = this.order.snapshot();
            // CP9 partial recall: a resumed order may already carry tenders — seed the
            // payment screen from the AUTHORITATIVE already-paid amount so the cashier
            // sees the correct remaining and never re-tenders what is already paid.
            const paid = roundTo(res.amount_paid || 0, this.decimals);
            this.state.payment = {
                uuid,
                total: res.amount_total,
                paid,
                remaining: roundTo(res.amount_total - paid, this.decimals),
                tenders: [],
            };
            this.state.warn = null;
            this.state.managerReq = null;
            this.state.tenderError = "";
            this.state.phase = "payment";
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
        try {
            const res = await this.api.call("/orders/pay", body);
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
                change: payload.change || 0,
            });
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
            draft: true,
        });
        if (res && res.uuid) {
            this.state.orderUuid = res.uuid;
        }
        return this.state.orderUuid;
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
                await this.api.call("/orders/comp", {
                    session_id: this.state.sessionId,
                    order_uuid: this.state.orderUuid,
                    product_id: line.product.id,
                    reason: reason,
                    manager_code: managerCode,
                    manager_pin: managerPin,
                });
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
            await this.api.call("/orders/fire", {
                uuid: this.state.orderUuid,
                session_id: this.state.sessionId,
                table_id: this.state.table && this.state.table.id,
                lines: this.order.toSyncLines(),
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
    get orderTypes() {
        return [
            { key: "eat_in", label: _t("Dine-in"),
              active: this.isTableBound || this.state.serviceMode === "eat_in" },
            { key: "takeaway", label: _t("Takeaway"),
              active: !this.isTableBound && this.state.serviceMode === "takeaway" },
            { key: "delivery", label: _t("Delivery"), active: false },
        ];
    }

    async setOrderType(key) {
        if (key === "delivery") {
            if (!this.order.lines.length) {
                this.state.actionError = _t("Add items before starting a delivery.");
                return;
            }
            this.state.deliveryForm = true;
            return;
        }
        // A table-bound order IS dine-in; changing it would contradict the floor.
        if (this.isTableBound) {
            return;
        }
        this.state.serviceMode = key;
        if (this.state.orderUuid) {
            // already persisted — tell the server, do not wait for the next sync
            try {
                await this.api.call("/orders/sync", {
                    uuid: this.state.orderUuid,
                    session_id: this.state.sessionId,
                    lines: this.order.toSyncLines(),
                    service_mode: key,
                    draft: true,
                });
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
            change: roundTo(Math.max((breakdown && breakdown.change) || 0, totalChange), this.decimals),
            payments: lines,
            items: this.state.snapshot || [],
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
        this.state.phase = "receipt";
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
