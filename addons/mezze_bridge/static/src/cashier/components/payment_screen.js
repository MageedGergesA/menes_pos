/** @odoo-module **/
// S2C-2 payment hub: real configured methods, partial + mixed tender, cash change,
// duplicate WARN + manager approval. Cash is inline; manual/external use the
// reusable ManualTender dialog. Devices come from /payment/devices. The server is
// authoritative for paid/remaining (from each /orders/pay response).
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ManualTender } from "./manual_tender";
import { IntegratedTerminal } from "./integrated_terminal";
import { QrPay } from "./qr_pay";
import {
    changeFor,
    formatMoney,
    isSupportedMethod,
    quickCashOptions,
    recordedAmount,
    roundTo,
} from "../order_store";

export class PaymentScreen extends Component {
    static template = "mezze_bridge.PaymentScreen";
    static components = { ManualTender, IntegratedTerminal, QrPay };
    static props = {
        payment: Object,
        currency: Object,
        methods: Array,
        inFlight: { type: Boolean, optional: true },
        tenderError: { type: String, optional: true },
        warn: { optional: true },
        managerReq: { optional: true },
        terminal: { optional: true }, // active integrated-terminal state (owned by root)
        qr: { optional: true }, // active bank-QR state (owned by root)
        onTender: Function,
        onWarnContinue: Function,
        onWarnCancel: Function,
        onManagerApprove: Function,
        onManagerCancel: Function,
        onTerminalSelect: Function,
        onTerminalSend: Function,
        onTerminalCancel: Function,
        onTerminalRetry: Function,
        onTerminalForceDone: Function,
        onQrSelect: Function,
        onQrConfirm: Function,
        onQrCancel: Function,
        onQrRetry: Function,
        onBack: Function,
    };

    setup() {
        this.api = this.env.mezze.api;
        this.boot = this.env.mezze.boot;
        this.state = useState({
            selected: null, // active method
            devices: [],
            cashTendered: "",
            mgr: { code: "", pin: "", reason: "" },
        });
    }

    get decimals() {
        return this.props.currency.decimals ?? 2;
    }

    fmt(amount) {
        return formatMoney(amount, this.props.currency);
    }

    get remaining() {
        return this.props.payment.remaining;
    }

    isSupported(m) {
        return isSupportedMethod(m);
    }

    // ---- method selection --------------------------------------------------
    async selectMethod(m) {
        if (!this.isSupported(m) || this.props.inFlight) {
            return;
        }
        this.state.selected = m;
        this.state.cashTendered = String(roundTo(this.remaining, this.decimals));
        this.state.devices = [];
        if (m.mezze_mode !== "cash") {
            try {
                const res = await this.api.call("/payment/devices", {
                    config_id: this.boot.config_id,
                    payment_method_id: m.id,
                });
                this.state.devices = (res.devices || []).map((d) => ({
                    id: d.id, name: d.name, acquirer: d.acquirer || "",
                }));
            } catch {
                this.state.devices = [];
            }
        }
        // Integrated terminal: hand off to root, which owns the request lifecycle
        // (start → waiting → result). Auto-pick the single configured reader.
        if (m.mezze_mode === "odoo_terminal") {
            const dev = this.state.devices.length === 1 ? this.state.devices[0] : null;
            this.props.onTerminalSelect({
                method: m,
                deviceId: dev ? dev.id : null,
                deviceName: dev ? dev.name : "",
                remaining: roundTo(this.remaining, this.decimals),
            });
        }
        // Bank-app QR: root generates the native QR for the current remaining.
        if (m.mezze_mode === "bank_qr") {
            this.props.onQrSelect({ method: m, amount: roundTo(this.remaining, this.decimals) });
        }
    }

    closeDialog() {
        this.state.selected = null;
        // clear any integrated-terminal / QR state when leaving the method
        if (this.props.terminal) {
            this.props.onTerminalCancel({ silent: true });
        }
        if (this.props.qr) {
            this.props.onQrCancel({ silent: true });
        }
    }

    // ---- cash --------------------------------------------------------------
    get cashTenderedNumber() {
        const n = parseFloat(this.state.cashTendered);
        return Number.isFinite(n) ? n : 0;
    }

    get cashRecorded() {
        return recordedAmount(this.cashTenderedNumber, this.remaining, this.decimals);
    }

    get cashChange() {
        return changeFor(this.cashTenderedNumber, this.remaining, this.decimals);
    }

    get quickOptions() {
        return quickCashOptions(this.remaining, this.decimals);
    }

    get cashConfirmLabel() {
        return this.props.inFlight
            ? _t("Processing…")
            : _t("Confirm Cash") + " · " + this.fmt(this.cashRecorded);
    }

    get refLabel() {
        return _t("Ref");
    }

    pickCash(v) {
        this.state.cashTendered = String(v);
    }

    async cashConfirm() {
        if (this.props.inFlight || this.cashRecorded <= 0) {
            return;
        }
        const method = this.state.selected;
        const r = await this.props.onTender({
            method,
            amount: this.cashRecorded,
            change: this.cashChange,
        });
        this._afterTender(r);
    }

    // ---- manual / external -------------------------------------------------
    async manualConfirm(payload) {
        const r = await this.props.onTender(payload);
        this._afterTender(r);
    }

    _afterTender(r) {
        // close the tender dialog on success, or when a modal takes over (warn /
        // manager); keep it open on a plain rejection so the cashier can adjust.
        if (r && (r.ok || r.warn || r.manager)) {
            this.state.selected = null;
        }
    }

    // ---- manager approval form --------------------------------------------
    submitManager() {
        if (this.props.inFlight) {
            return;
        }
        const { code, pin, reason } = this.state.mgr;
        this.props.onManagerApprove({ code, pin, reason });
    }

    cancelManager() {
        this.state.mgr = { code: "", pin: "", reason: "" };
        this.props.onManagerCancel();
    }
}
