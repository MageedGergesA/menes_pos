/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { formatMoney } from "../order_store";

export class Cart extends Component {
    static template = "mezze_bridge.Cart";
    static props = {
        onCharge: Function,
        inFlight: { type: Boolean, optional: true },
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
}
