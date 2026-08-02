/** @odoo-module **/
// S2C-4 — Bank App (Payment) QR tender. Displays the NATIVE Odoo-generated QR for
// the order's authoritative remaining, then records a MANUAL cashier confirmation
// (Odoo's own model — no automatic bank webhook). The QR graphic is a bank payload
// (IBAN/amount/currency/reference), never a Mezze token; it must never mirror in RTL
// nor invert in dark mode.
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";

export class QrPay extends Component {
    static template = "mezze_bridge.QrPay";
    static props = {
        qr: Object, // { state, amount, currency, reference, image, error, generating, confirming }
        currency: Object,
        inFlight: { type: Boolean, optional: true },
        onConfirm: Function,
        onCancel: Function,
        onRetry: Function,
        onClose: Function,
    };

    get q() {
        return this.props.qr;
    }

    get amount() {
        return formatMoney(this.q.amount || 0, this.props.currency);
    }

    get hasImage() {
        return !!this.q.image;
    }

    get title() {
        return _t("Pay by QR");
    }

    get instruction() {
        return _t("Ask the customer to scan the code with their banking app and pay.");
    }

    get noticeLine() {
        // Same honesty rule as the external terminal: manual, not bank-verified.
        return _t("Mezze records this QR payment manually — it does not verify it with the bank.");
    }

    get confirmLabel() {
        return this.props.inFlight ? _t("Working…") : _t("Confirm payment received");
    }

    get cancelLabel() {
        return _t("Cancel");
    }

    get retryLabel() {
        return _t("Regenerate QR");
    }

    get refLabel() {
        return _t("Ref");
    }
}
