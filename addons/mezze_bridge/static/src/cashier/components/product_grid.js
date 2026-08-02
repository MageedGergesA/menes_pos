/** @odoo-module **/
import { Component } from "@odoo/owl";
import { formatMoney } from "../order_store";

export class ProductGrid extends Component {
    static template = "mezze_bridge.ProductGrid";
    static props = {
        products: Array,
        currency: Object,
        onSelect: Function,
    };

    fmt(amount) {
        return formatMoney(amount, this.props.currency);
    }

    select(product) {
        if (product.available === false) {
            return;
        }
        this.props.onSelect(product);
    }
}
