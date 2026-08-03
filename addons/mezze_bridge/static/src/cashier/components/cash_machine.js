/** @odoo-module **/
// S2C-7 — automated cash-machine tender UI. Visibly DISTINCT from manual Cash: here
// the MACHINE receives and counts cash and returns change, and the native device
// result validates the payment — there is no "enter amount received" field and Mezze
// never computes a fake change success. All chrome is translated via Odoo's _t.
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";
import { CMS, isCashUncertain } from "../cash_machine_service";

export class CashMachine extends Component {
    static template = "mezze_bridge.CashMachine";
    static props = {
        machine: Object, // { state, amount, inserted, change, device, error_code, uncertain }
        currency: Object,
        inFlight: { type: Boolean, optional: true },
        onSend: Function,
        onCancel: Function,
        onRetry: Function,
        onForceDone: Function,
        onClose: Function,
    };

    setup() {
        this.state = useState({ showForce: false, mgr: { code: "", pin: "", reason: "" } });
    }

    fmt(amount) {
        return formatMoney(amount, this.props.currency);
    }

    get m() {
        return this.props.machine;
    }

    get isReady() {
        return this.m.state === CMS.READY;
    }

    get isActive() {
        return [CMS.SENDING, CMS.WAITING_CASH, CMS.COUNTING, CMS.RETURNING_CHANGE].includes(this.m.state);
    }

    get isApproved() {
        return this.m.state === CMS.APPROVED;
    }

    get isCancelled() {
        return this.m.state === CMS.CANCELLED;
    }

    get isFailed() {
        return isCashUncertain(this.m.state);
    }

    get canForceDone() {
        return this.m.state === CMS.UNKNOWN; // never for a clean connection error/cancel
    }

    get showInserted() {
        // only when the device authoritatively reported an inserted amount
        return this.isActive && this.m.inserted > 0 && this.m.inserted !== this.m.amount;
    }

    // status glyph — never color-only (paired with text + aria-live)
    get statusIcon() {
        const s = this.m.state;
        if (s === CMS.APPROVED) {
            return "✓";
        }
        if (s === CMS.CANCELLED) {
            return "⊘";
        }
        if (isCashUncertain(s)) {
            return "!";
        }
        return "•";
    }

    get statusTitle() {
        switch (this.m.state) {
            case CMS.SENDING:
                return _t("Sending amount to the cash machine…");
            case CMS.WAITING_CASH:
                return _t("Waiting for cash…");
            case CMS.COUNTING:
                return _t("Counting cash…");
            case CMS.RETURNING_CHANGE:
                return _t("Returning change…");
            case CMS.APPROVED:
                return _t("Cash received");
            case CMS.CANCELLED:
                return _t("Payment cancelled");
            case CMS.UNKNOWN:
                return _t("Cash machine status could not be confirmed.");
            case CMS.ERROR:
                return _t("Cash machine unavailable");
            default:
                return _t("Ready");
        }
    }

    get statusHint() {
        switch (this.m.state) {
            case CMS.WAITING_CASH:
                return _t("Insert notes/coins into the cash machine.");
            case CMS.COUNTING:
                return _t("The machine is counting the inserted cash.");
            case CMS.RETURNING_CHANGE:
                return _t("The machine is returning change.");
            case CMS.UNKNOWN:
                return _t("Check the machine before retrying — do not send another payment.");
            case CMS.ERROR:
                if (this.m.error_code === "device_pending" || this.m.error_code === "device_integration_pending") {
                    return _t("This cash machine is supported by Odoo but not yet available on this cashier.");
                }
                if (this.m.error_code === "connection_error") {
                    return _t("The cash machine could not be reached on the local network. No payment was taken.");
                }
                return _t("The transaction was not completed. Use another payment method or retry.");
            case CMS.CANCELLED:
                if (this.m.error_code === "connection_error") {
                    return _t("The cash machine could not be reached. No payment was taken.");
                }
                return _t("Use another payment method or retry.");
            default:
                return "";
        }
    }

    get deviceLabel() {
        return this.m.device || "";
    }

    get sendLabel() {
        return _t("Start cash machine");
    }

    get forceWarning() {
        return _t(
            "The cash-machine result could not be confirmed. Only use Force Done if you have " +
            "physically verified the machine took the cash. This payment is recorded as a manual " +
            "override and requires reconciliation."
        );
    }

    // ---- actions -----------------------------------------------------------
    send() {
        if (this.props.inFlight) {
            return;
        }
        this.props.onSend();
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
