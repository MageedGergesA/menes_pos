/** @odoo-module **/
// Root cashier component. Owns the screen phase machine and orchestrates the
// backend contracts (bootstrap → sync → pay → breakdown). It NEVER falls back to
// demo data: any auth/catalog/network failure resolves to an explicit state.
// S2C-2: multi-tender (cash + manual/external) with device/reference/duplicate
// policy, partial + mixed tender, manager approval, and an authoritative receipt.
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { ProductGrid } from "./components/product_grid";
import { Cart } from "./components/cart";
import { PaymentScreen } from "./components/payment_screen";
import { Receipt } from "./components/receipt";
import { formatMoney, roundTo } from "./order_store";

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
                ? "POS is not ready for sales"
                : "Authentication required";
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
                    ? "Local Mezze server unavailable" : (err && err.message) || "Unable to load menu";
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
                    ? "Local Mezze server unavailable" : (err && err.message) || "Could not open payment";
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
                    ? "That user is not authorized to approve (manager required)."
                    : "Invalid manager code or PIN.",
            };
            return { ok: false, manager: true };
        }
        if (err && err.kind === "auth") {
            this.state.phase = "auth_required";
            return { ok: false };
        }
        if (err && err.kind === "network") {
            this.state.tenderError = "Local Mezze server unavailable — payment not taken.";
            return { ok: false };
        }
        // payment_rejected (required device/reference, BLOCK), invalid_amount, overpay
        this.state.tenderError = (err && err.message) || "Payment was rejected.";
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
        this.state.tenderError = "";
        this.state.errorMsg = "";
        this.state.phase = "menu";
    }

    retry() {
        this.state.errorMsg = "";
        this.bootstrap();
    }
}
