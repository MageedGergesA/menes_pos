/** @odoo-module **/
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
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

    get orderLabel() {
        return _t("Order");
    }

    get cashierLabel() {
        return _t("Cashier");
    }

    get refLabel() {
        return _t("Ref");
    }

    fmt(amount) {
        return formatMoney(amount, this.props.currency);
    }
}
