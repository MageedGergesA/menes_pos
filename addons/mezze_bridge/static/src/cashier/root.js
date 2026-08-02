/** @odoo-module **/
// Root cashier component. Owns the screen phase machine and orchestrates the
// backend contracts (bootstrap → sync → pay → breakdown). It NEVER falls back to
// demo data: any auth/catalog/network failure resolves to an explicit state.
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { ProductGrid } from "./components/product_grid";
import { Cart } from "./components/cart";
import { PaymentScreen } from "./components/payment_screen";
import { Receipt } from "./components/receipt";
import { formatMoney } from "./order_store";

function makeUuid() {
    if (window.crypto && window.crypto.randomUUID) {
        return window.crypto.randomUUID();
    }
    return "mz-" + Date.now() + "-" + Math.floor(Math.random() * 1e9);
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
            activeCategory: null,
            sessionId: null,
            cashMethod: null,
            payment: null, // { uuid, total, tendered }
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
            return;
        }
        this.state.phase = "error";
        if (err && err.kind === "network") {
            this.state.errorMsg = "Local Mezze server unavailable";
        } else {
            this.state.errorMsg = (err && err.message) || "Unexpected error";
        }
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
            const cash = (data.payment_methods || []).find((m) => m.is_cash_count);
            this.state.cashMethod = cash || null;
            this.state.phase = "menu";
        } catch (err) {
            this._failFromError(err);
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
        if (!this.state.cashMethod) {
            this.state.phase = "error";
            this.state.errorMsg = "No cash payment method is configured for this POS";
            return;
        }
        this.state.inFlight = true;
        try {
            const uuid = makeUuid();
            const res = await this.api.call("/orders/sync", {
                uuid,
                session_id: this.state.sessionId,
                lines: this.order.toSyncLines(),
                draft: true, // persist unpaid; the tender is taken via /orders/pay
            });
            this.state.payment = {
                uuid,
                total: res.amount_total,
                tendered: "",
            };
            this.state.snapshot = this.order.snapshot();
            this.state.phase = "payment";
        } catch (err) {
            this._failFromError(err);
        } finally {
            this.state.inFlight = false;
        }
    }

    backToMenu() {
        this.state.phase = "menu";
        this.state.payment = null;
    }

    setTendered(value) {
        if (this.state.payment) {
            this.state.payment.tendered = value;
        }
    }

    // ---- cash payment ------------------------------------------------------
    async confirmCash(tenderedNumber) {
        if (this.state.inFlight || !this.state.payment) {
            return;
        }
        this.state.inFlight = true;
        this.state.phase = "processing";
        const pay = this.state.payment;
        try {
            const res = await this.api.call("/orders/pay", {
                uuid: pay.uuid,
                payment_method_id: this.state.cashMethod.id,
            });
            // Authoritative receipt breakdown (masked, no secrets).
            let breakdown = null;
            try {
                breakdown = await this.api.call("/payment/breakdown", { uuid: pay.uuid });
            } catch {
                breakdown = null;
            }
            this.state.receipt = {
                pos_reference: res.pos_reference,
                order_id: res.order_id,
                total: breakdown ? breakdown.total : res.amount_total,
                lines: this.state.snapshot || this.order.snapshot(),
                tendered: Number(tenderedNumber) || pay.total,
                change: Math.max(0, (Number(tenderedNumber) || pay.total) - (res.amount_total || pay.total)),
                branch: this.branchName,
                cashier: this.userName,
                datetime: new Date().toLocaleString(),
                method: "Cash",
            };
            this.order.clear();
            this.state.phase = "receipt";
        } catch (err) {
            // Do NOT clear the cart or show a receipt on failure.
            this.state.phase = "payment";
            this.state.errorMsg = (err && err.message) || "Payment failed";
        } finally {
            this.state.inFlight = false;
        }
    }

    // ---- receipt -----------------------------------------------------------
    newOrder() {
        this.order.clear();
        this.state.payment = null;
        this.state.receipt = null;
        this.state.snapshot = null;
        this.state.errorMsg = "";
        this.state.phase = "menu";
    }

    retry() {
        this.state.errorMsg = "";
        this.bootstrap();
    }
}
