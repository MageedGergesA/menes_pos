/** @odoo-module **/
import { Component } from "@odoo/owl";
import { formatMoney } from "../order_store";

export class Receipt extends Component {
    static template = "mezze_bridge.Receipt";
    static props = {
        receipt: Object,
        currency: Object,
        onNewOrder: Function,
    };

    get receipt() {
        return this.props.receipt;
    }

    fmt(amount) {
        return formatMoney(amount, this.props.currency);
    }
}
