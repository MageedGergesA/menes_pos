/** @odoo-module **/
// S2C-3 — reusable integrated-terminal tender UI. Visibly DISTINCT from the L2
// manual dialog: here Mezze sends the amount and the terminal/provider returns the
// result — there is NO "confirm only after the terminal shows APPROVED" notice and
// no manual reference entry. All chrome is translated via Odoo's _t.
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";
import { TS, isUncertain } from "../terminal_service";

export class IntegratedTerminal extends Component {
    static template = "mezze_bridge.IntegratedTerminal";
    static props = {
        terminal: Object, // { state, amount, provider, device, error_code, uncertain, referenceMasked, forceError }
        currency: Object,
        inFlight: { type: Boolean, optional: true },
        onSend: Function,
        onCancel: Function,
        onRetry: Function,
        onForceDone: Function,
        onClose: Function,
    };

    setup() {
        this.state = useState({
            showForce: false,
            amountInput: String(this.props.terminal.amount ?? 0),
            mgr: { code: "", pin: "", reason: "" },
        });
    }

    fmt(amount) {
        return formatMoney(amount, this.props.currency);
    }

    get t() {
        return this.props.terminal;
    }

    get decimals() {
        return this.props.currency.decimals ?? 2;
    }

    // Editable on READY (default = remaining) so an integrated card can be one
    // tender in a mixed payment; locked to the sent amount once a request starts.
    get amountNumber() {
        const n = parseFloat(this.state.amountInput);
        return Number.isFinite(n) && n > 0 ? n : 0;
    }

    get amount() {
        return this.fmt(this.isReady ? this.amountNumber : this.t.amount || 0);
    }

    get isReady() {
        return this.t.state === TS.READY;
    }

    get isActive() {
        return [TS.SENDING, TS.WAITING, TS.PROCESSING].includes(this.t.state);
    }

    get isApproved() {
        return this.t.state === TS.APPROVED;
    }

    get isDeclined() {
        return this.t.state === TS.DECLINED;
    }

    get isCancelled() {
        return this.t.state === TS.CANCELLED;
    }

    get isFailed() {
        return isUncertain(this.t.state);
    }

    get canForceDone() {
        return this.isFailed;
    }

    // status glyph (never color-only — paired with text for a11y)
    get statusIcon() {
        const s = this.t.state;
        if (s === TS.APPROVED) {
            return "✓";
        }
        if (s === TS.DECLINED) {
            return "✕";
        }
        if (s === TS.CANCELLED) {
            return "⊘";
        }
        if (isUncertain(s)) {
            return "!";
        }
        return "•";
    }

    get statusTitle() {
        switch (this.t.state) {
            case TS.SENDING:
                return _t("Sending payment to terminal…");
            case TS.WAITING:
                return _t("Waiting for customer…");
            case TS.PROCESSING:
                return _t("Confirming payment…");
            case TS.APPROVED:
                return _t("Payment approved");
            case TS.DECLINED:
                return _t("Payment declined");
            case TS.CANCELLED:
                return _t("Payment cancelled");
            case TS.TIMEOUT:
            case TS.UNKNOWN:
                return _t("Payment status could not be confirmed.");
            case TS.ERROR:
                return _t("Terminal connection problem");
            default:
                return _t("Ready");
        }
    }

    get statusHint() {
        switch (this.t.state) {
            case TS.WAITING:
                return _t("Follow the instructions on the payment terminal.");
            case TS.DECLINED:
                return _t("Try another method or retry.");
            case TS.TIMEOUT:
            case TS.UNKNOWN:
                return _t("Check the terminal before retrying.");
            case TS.ERROR:
                if (this.t.error_code === "provider_pending") {
                    return _t("This terminal is supported by Odoo but not yet available on this cashier.");
                }
                return _t("The terminal could not be reached. No payment was taken.");
            default:
                return "";
        }
    }

    get deviceLabel() {
        return this.t.device || "";
    }

    get sendLabel() {
        return _t("Send to Terminal");
    }

    get cancelLabel() {
        return _t("Cancel");
    }

    get retryLabel() {
        return _t("Retry");
    }

    get forceDoneLabel() {
        return _t("Force Done");
    }

    get forceWarning() {
        return _t(
            "The terminal result could not be confirmed. Only use Force Done if you have " +
            "independently verified that the customer was charged. This payment will be " +
            "recorded as a manual override and require reconciliation."
        );
    }

    // ---- actions -----------------------------------------------------------
    send() {
        if (this.props.inFlight || this.amountNumber <= 0) {
            return;
        }
        this.props.onSend({ amount: this.amountNumber });
    }

    openForce() {
        this.state.showForce = true;
    }

    closeForce() {
        this.state.showForce = false;
        this.state.mgr = { code: "", pin: "", reason: "" };
    }

    submitForce() {
        if (this.props.inFlight) {
            return;
        }
        const { code, pin, reason } = this.state.mgr;
        this.props.onForceDone({ code, pin, reason });
    }
}
