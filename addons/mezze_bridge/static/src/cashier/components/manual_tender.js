/** @odoo-module **/
// S2C-2 — ONE reusable manual electronic tender dialog for `manual` and
// `external_terminal` methods (Card / Wallet / Transfer / custom). Every field is
// policy-driven from the method config; nothing about a specific brand is
// hardcoded. For external_terminal it states plainly that confirmation is MANUAL
// (Mezze is not talking to the terminal) — never "bank/provider verified".
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney, roundTo, tenderFields } from "../order_store";

export class ManualTender extends Component {
    static template = "mezze_bridge.ManualTender";
    static props = {
        method: Object,
        devices: Array,
        remaining: Number,
        currency: Object,
        inFlight: { type: Boolean, optional: true },
        onConfirm: Function,
        onCancel: Function,
    };

    setup() {
        const only = this.props.devices.length === 1 ? this.props.devices[0].id : null;
        this.state = useState({
            amount: String(roundTo(this.props.remaining, this.decimals)),
            deviceId: only,
            reference: "",
            approvalCode: "",
            error: "",
        });
    }

    get f() {
        return tenderFields(this.props.method);
    }

    get decimals() {
        return this.props.currency.decimals ?? 2;
    }

    fmt(amount) {
        return formatMoney(amount, this.props.currency);
    }

    get amountNumber() {
        const n = parseFloat(this.state.amount);
        return Number.isFinite(n) ? n : 0;
    }

    get noDevice() {
        // policy needs a device but none is configured for this register
        return this.f.devicePolicy !== "disabled" && this.props.devices.length === 0;
    }

    get noDeviceMsg() {
        return _t("No payment terminal is configured for this register. Contact a manager.");
    }

    get deviceBlocking() {
        return this.f.devicePolicy === "required" && this.props.devices.length === 0;
    }

    get referenceLabel() {
        const mode = this.props.method.mezze_mode;
        if (mode === "external_terminal") {
            return _t("Terminal Reference");
        }
        return _t("Payment Reference");
    }

    get confirmLabel() {
        return this.props.inFlight
            ? _t("Processing…")
            : _t("Confirm Payment") + " · " + this.fmt(this.amountNumber);
    }

    get noticeLine1() {
        return _t("Confirm only after the external terminal shows APPROVED.");
    }

    get noticeLine2() {
        return _t("Mezze records this tender manually — it does not verify it with the bank or provider.");
    }

    validate() {
        const amt = roundTo(this.amountNumber, this.decimals);
        if (amt <= 0) {
            this.state.error = _t("Enter a payment amount.");
            return null;
        }
        if (amt - roundTo(this.props.remaining, this.decimals) > 1 / 10 ** this.decimals) {
            this.state.error = _t("Amount exceeds the remaining balance.");
            return null;
        }
        if (this.f.devicePolicy === "required" && !this.state.deviceId) {
            this.state.error = _t("Select a payment device.");
            return null;
        }
        if (this.f.referencePolicy === "required" && !this.state.reference.trim()) {
            this.state.error = _t("Enter the payment reference.");
            return null;
        }
        this.state.error = "";
        const dev = this.props.devices.find((d) => d.id === this.state.deviceId);
        return {
            method: this.props.method,
            amount: amt,
            device_id: this.state.deviceId || null,
            device_name: dev ? dev.name : "",
            reference: this.state.reference.trim(),
            approval_code: this.state.approvalCode.trim(),
            change: 0,
        };
    }

    confirm() {
        if (this.props.inFlight || this.deviceBlocking) {
            return;
        }
        const payload = this.validate();
        if (payload) {
            this.props.onConfirm(payload);
        }
    }
}
