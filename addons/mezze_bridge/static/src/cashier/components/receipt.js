/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";

export class Receipt extends Component {
    static template = "mezze_bridge.Receipt";
    static props = {
        receipt: Object,
        currency: Object,
        onNewOrder: Function,
        onPrint: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({ printing: false });
    }

    get receipt() {
        return this.props.receipt;
    }

    get orderLabel() {
        return _t("Order");
    }

    get cashierLabel() {
        return _t("Cashier");
    }

    get refLabel() {
        return _t("Ref");
    }

    get subtotalLabel() { return _t("Subtotal"); }
    get taxLabel() { return _t("Tax"); }
    get totalLabel() { return _t("Total"); }
    get paymentsLabel() { return _t("Payments"); }
    get totalPaidLabel() { return _t("Total paid"); }
    get changeLabel() { return _t("Change"); }
    get printLabel() { return _t("Print receipt"); }
    get newOrderLabel() { return _t("New order"); }
    get printingLabel() { return _t("Printing…"); }

    /** Only worth a line of its own when there IS tax. A tax-free country should
     *  not read "Tax 0.00" on every receipt. */
    get hasTax() {
        return Math.abs(this.receipt.tax || 0) > 0.0001;
    }

    /** Two rates on one bill need naming; a single rate is already the "Tax" row. */
    get taxLines() {
        const lines = this.receipt.tax_lines || [];
        return lines.length > 1 ? lines : [];
    }

    /**
     * Print.
     *
     * The station printer is the right destination when there is one, so it is
     * tried first. When there is not — a browser-only till, a tablet, a manager
     * looking at a copy — falling back to the browser's own print dialog is what
     * makes the button honest: it also gives "Save as PDF", which is how a guest
     * asking for a copy by email actually gets one. A button that can only fail
     * on hardware nobody has installed is worse than no button.
     */
    async print() {
        if (this.state.printing) {
            return;
        }
        this.state.printing = true;
        try {
            const res = this.props.onPrint ? await this.props.onPrint() : null;
            // `ok` means the SERVER understood the request, not that paper came out:
            // with no printer configured it answers {ok:true, sent:false,
            // reason:"no_printer"} and hands back a text preview. Treating that as
            // success meant the button did nothing at all — no ticket, no dialog, no
            // message — on exactly the tills that need the fallback most. `sent` is
            // the only field that means printed.
            if (!res || !res.sent) {
                window.print();
            }
        } catch {
            window.print();
        }
        this.state.printing = false;
    }

    fmt(amount) {
        return formatMoney(amount, this.props.currency);
    }
}
