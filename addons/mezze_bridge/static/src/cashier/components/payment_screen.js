/** @odoo-module **/
// Cash payment screen (S2C-1 supports CASH only). Shows the AUTHORITATIVE total
// from /orders/sync, lets the cashier enter or quick-pick a tender, and displays
// change. The tender/change are display-only; the backend records the amount due.
import { Component, useState } from "@odoo/owl";
import { formatMoney, computeChange, quickCashOptions, roundTo } from "../order_store";

export class PaymentScreen extends Component {
    static template = "mezze_bridge.PaymentScreen";
    static props = {
        total: Number,
        currency: Object,
        inFlight: { type: Boolean, optional: true },
        errorMsg: { type: String, optional: true },
        onConfirm: Function,
        onBack: Function,
    };

    setup() {
        this.state = useState({ tendered: "" });
    }

    fmt(amount) {
        return formatMoney(amount, this.props.currency);
    }

    get decimals() {
        return this.props.currency.decimals ?? 2;
    }

    get tenderedNumber() {
        const n = parseFloat(this.state.tendered);
        return Number.isFinite(n) ? n : 0;
    }

    get change() {
        return computeChange(this.props.total, this.tenderedNumber, this.decimals);
    }

    get canConfirm() {
        if (this.props.inFlight) {
            return false;
        }
        // Exact or over-tender only (cash cannot settle short).
        return roundTo(this.tenderedNumber, this.decimals) >= roundTo(this.props.total, this.decimals);
    }

    get quickOptions() {
        return quickCashOptions(this.props.total, this.decimals);
    }

    onInput(ev) {
        this.state.tendered = ev.target.value;
    }

    pick(amount) {
        this.state.tendered = String(amount);
    }

    confirm() {
        if (!this.canConfirm) {
            return;
        }
        this.props.onConfirm(this.tenderedNumber);
    }
}
