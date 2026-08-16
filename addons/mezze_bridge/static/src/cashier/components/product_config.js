/** @odoo-module **/
// CONV-3 — the Register's product configurator.
//
// The RULES are not here. Which groups a product has, what a group starts on, what
// a tap does, what is still missing and which cart line the result IS all live in
// design/product-config.js, which the drive-thru board applies too. This component
// is the Register's rendering of them, in the canonical panel
// (design/product-config.css) — so a cashier who has configured a burger in the
// lane recognises this one, and neither surface can drift into its own idea of what
// "required" means.
//
// It is an authority over NOTHING financial: the live item total is a preview, and
// the server re-derives every figure from the chosen values when the order syncs.
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";

const PC = window.MezzeProductConfig;

export class ProductConfig extends Component {
    static template = "mezze_bridge.ProductConfig";
    static props = {
        config: Object,          // { product, groups, selection, lineKey }
        currency: Object,
        onToggle: Function,
        onConfirm: Function,
        onClose: Function,
    };

    get groups() {
        return this.props.config.groups || [];
    }

    get productName() {
        return this.props.config.product.name;
    }

    isOn(group, value) {
        return PC.isOn(this.props.config.selection, group, value.id);
    }

    /** A required group with nothing chosen is called out ON THE GROUP, not only in
     *  a banner at the bottom the operator has to go looking for. */
    isMissing(group) {
        return PC.missingRequired(this.groups, this.props.config.selection).includes(group);
    }

    get missing() {
        return PC.missingRequired(this.groups, this.props.config.selection);
    }

    get canConfirm() {
        return this.missing.length === 0;
    }

    /** "Choose a Size" — the message names the group, because "invalid
     *  configuration" is a puzzle rather than an instruction. */
    get warning() {
        const m = this.missing;
        return m.length ? _t("Choose a %s", m[0].attribute) : "";
    }

    groupTag(group) {
        return group.required ? _t("Choose one") : _t("Choose any");
    }

    /** Live preview of what the configuration costs. Never sent, never charged. */
    get itemTotal() {
        const base = this.props.config.product.list_price || 0;
        return formatMoney(base + PC.extraPrice(this.groups, this.props.config.selection),
                           this.props.currency);
    }

    priceExtra(value) {
        return "+" + formatMoney(value.price_extra, this.props.currency);
    }

    /** Reopening a line says so: correcting a choice is not the same act as adding. */
    get confirmLabel() {
        return this.props.config.lineKey ? _t("Save changes") : _t("Add to order");
    }

    get itemTotalLabel() {
        return _t("Item total");
    }

    get cancelLabel() {
        return _t("Cancel");
    }

    get closeLabel() {
        return _t("Close");
    }

    get title() {
        return _t("Customize item");
    }
}
