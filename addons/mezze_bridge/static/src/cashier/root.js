/** @odoo-module **/
// Root cashier component. Owns the screen phase machine and orchestrates the
// backend contracts (bootstrap → sync → pay → breakdown). It NEVER falls back to
// demo data: any auth/catalog/network failure resolves to an explicit state.
// S2C-2: multi-tender (cash + manual/external) with device/reference/duplicate
// policy, partial + mixed tender, manager approval, and an authoritative receipt.
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ProductGrid } from "./components/product_grid";
import { Cart } from "./components/cart";
import { PaymentScreen } from "./components/payment_screen";
import { Receipt } from "./components/receipt";
import { formatMoney, roundTo } from "./order_store";
import { getTerminalAdapter, TS } from "./terminal_service";

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
    static components = { ProductGrid, Cart, PaymentScreen, Receipt };
    static props = {};

    setup() {
        const { boot, api, order } = this.env.mezze;
        this.api = api;
        this.order = order;
        this.boot = boot;
        this.currency = order.currency;
        this.cart = useState(order.state);
        this.state = useState({
            phase: "booting", // booting|auth_required|error|menu|payment|processing|receipt
            errorMsg: "",
            categories: [],
            products: [],
            methods: [],
            activeCategory: null,
            sessionId: null,
            payment: null, // { uuid, total, paid, remaining, tenders: [] }
            warn: null, // { ctx, pending }
            managerReq: null, // { ctx, pending, error }
            terminal: null, // S2C-3 integrated-terminal request state
            tenderError: "",
            receipt: null,
            inFlight: false,
            conn: { local: "unknown", wan: "unknown" },
        });

        onWillStart(async () => {
            await this.bootstrap();
        });
        onMounted(() => {
            this.pollConnectivity();
            this._connTimer = window.setInterval(() => this.pollConnectivity(), 20000);
        });
        onWillUnmount(() => window.clearInterval(this._connTimer));
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

    get decimals() {
        return this.currency.decimals ?? 2;
    }

    get visibleProducts() {
        const cat = this.state.activeCategory;
        if (!cat) {
            return this.state.products;
        }
        return this.state.products.filter((p) => (p.pos_categ_ids || []).includes(cat));
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
            this.state.phase = "menu";
        } catch (err) {
            if (!this._failFromError(err)) {
                this.state.phase = "error";
                this.state.errorMsg = err && err.kind === "network"
                    ? _t("Local Mezze server unavailable") : (err && err.message) || _t("Unable to load menu");
            }
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

    onSelectProduct(product) {
        this.order.addProduct(product);
    }

    // ---- payment navigation ------------------------------------------------
    async goToPayment() {
        if (this.order.isEmpty || this.state.inFlight) {
            return;
        }
        this.state.inFlight = true;
        try {
            const uuid = makeUuid();
            const res = await this.api.call("/orders/sync", {
                uuid,
                session_id: this.state.sessionId,
                lines: this.order.toSyncLines(),
                draft: true,
            });
            this.state.snapshot = this.order.snapshot();
            this.state.payment = {
                uuid,
                total: res.amount_total,
                paid: 0,
                remaining: res.amount_total,
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
        this.state.terminal = null;
        this.state.tenderError = "";
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
        // strip manager creds from the retained pending so a retry re-collects them
        const { manager_code, manager_pin, manager_reason, allow_duplicate, ...clean } = payload;
        const pending = { ...clean, tender_key: tenderKey };
        if (data.error === "duplicate_reference_warn") {
            this.state.warn = { ctx: data.duplicate || [], pending };
            return { ok: false, warn: true };
        }
        if (data.error === "duplicate_reference_needs_manager") {
            this.state.managerReq = { ctx: data.duplicate || [], pending, error: "" };
            return { ok: false, manager: true };
        }
        if (data.error === "insufficient_role" || data.error === "bad_credentials") {
            // manager-approval failure — keep the modal open with the reason
            const ctx = data.duplicate || (this.state.managerReq ? this.state.managerReq.ctx : []);
            this.state.managerReq = {
                ctx, pending,
                error: data.error === "insufficient_role"
                    ? _t("That user is not authorized to approve (manager required).")
                    : _t("Invalid manager code or PIN."),
            };
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
        this.state.terminal = null;
        this.state.tenderError = "";
        this.state.errorMsg = "";
        this.state.phase = "menu";
    }

    retry() {
        this.state.errorMsg = "";
        this.bootstrap();
    }
}
