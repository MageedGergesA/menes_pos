/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";

export class Cart extends Component {
    static template = "mezze_bridge.Cart";
    static props = {
        onCharge: Function,
        inFlight: { type: Boolean, optional: true },
        // R2A CP5: a table-bound Register can save the order to the table (draft) as
        // well as charge it. Both are optional so counter mode is unchanged.
        canSend: { type: Boolean, optional: true },
        onSend: { type: Function, optional: true },
        // R2A CP6: a counter (non-table) order can be assigned to a table.
        canAssign: { type: Boolean, optional: true },
        onAssign: { type: Function, optional: true },
        // R2A CP7: a table-bound order can be moved (transfer / merge).
        canMove: { type: Boolean, optional: true },
        onMove: { type: Function, optional: true },
        // R2A CP9: the current order can be parked (persisted + set aside).
        canPark: { type: Boolean, optional: true },
        onPark: { type: Function, optional: true },
    };

    setup() {
        this.order = this.env.mezze.order;
        // Connect this component to the shared reactive cart state.
        this.cart = useState(this.order.state);
    }

    fmt(amount) {
        return formatMoney(amount, this.order.currency);
    }

    get lines() {
        return this.cart.lines;
    }

    /** "<amount> each" — the reference shows a unit price beside the stepper. */
    eachLabel(line) {
        return _t("%s each", this.fmt(line.product.list_price));
    }

    /** "<n> items" beside the total, as the reference does. */
    get itemsLabel() {
        const n = this.order.count;
        return n === 1 ? _t("1 item") : _t("%s items", n);
    }

    inc(line) {
        this.order.inc(line);
    }

    dec(line) {
        this.order.dec(line);
    }

    remove(line) {
        this.order.remove(line);
    }

    lineTotal(line) {
        return (line.product.list_price || 0) * line.qty;
    }

    get chargeLabel() {
        if (this.props.inFlight) {
            return _t("Working…");
        }
        return _t("Charge") + " " + this.fmt(this.order.estimatedTotal);
    }
}
