/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";

/** The questions a cashier is asked while someone waits.
 *
 *  "How many have we got left?" and "what's in it?" and "is that the same price on
 *  the delivery menu?" are asked across the counter, and until now the answer was to
 *  leave the till and open the back office — which in practice means the answer was
 *  a guess.
 *
 *  Two rules shape this screen.
 *
 *  **The server decides what is shown, not this component.** Cost and margin arrive
 *  only for a principal that holds finance rights; a till that computed a margin
 *  locally would need the cost price on the client, which is the thing being
 *  withheld. So the finance block renders if and only if the payload carries it —
 *  and when it does not, nothing is drawn at all. An empty "Cost: —" row reads as
 *  "the shop does not know", which is a different and worse answer than silence.
 *
 *  **Stock is stated with its date, or not stated.** ``qty_available`` exists only
 *  for a storable product. Printing "0 left" for a dish that is not stock-tracked is
 *  a lie a cashier will act on, so an untracked product simply has no stock line.
 */
export class ProductInfoScreen extends Component {
    static template = "mezze_bridge.ProductInfoScreen";
    static props = {
        api: Object,
        product: Object,
        currency: { type: Object, optional: true },
        onClose: Function,
    };

    setup() {
        this.state = useState({ loading: true, error: "", info: null });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            const res = await this.props.api.call("/products/info", {
                product_id: this.props.product.id,
            });
            this.state.info = res || null;
        } catch (err) {
            this.state.error = (err && err.message)
                || _t("Could not look that product up.");
        } finally {
            this.state.loading = false;
        }
    }

    fmt(amount) {
        return formatMoney(amount, this.props.currency);
    }

    get info() {
        return this.state.info || {};
    }

    /** Whether the server sent the finance block. Not "may the user see it" — this
     *  component is not the authority on that and must not appear to be. */
    get hasFinance() {
        return typeof this.info.cost === "number";
    }

    get hasStock() {
        return typeof this.info.qty_available === "number";
    }

    /** On hand and forecast are different answers: what is in the fridge now, and
     *  what will be there once today's deliveries and orders settle. A single number
     *  hides whichever one the cashier needed. */
    get onHand() {
        return Math.round((this.info.qty_available || 0) * 100) / 100;
    }

    get forecast() {
        return Math.round((this.info.virtual_available || 0) * 100) / 100;
    }

    get otherPricelists() {
        // The price already shown at the top is this till's own; repeating it in the
        // list below invites the reading that there are two of them.
        const here = this.info.price;
        return (this.info.pricelists || []).filter((p) => p.price !== here);
    }

    get taxLine() {
        const names = this.info.taxes || [];
        return names.length ? names.join(", ") : _t("No tax");
    }

    // ---- labels ----
    get title() { return _t("Product info"); }
    get closeLabel() { return _t("Close"); }
    get priceLabel() { return _t("Price here"); }
    get listLabel() { return _t("Catalogue price"); }
    get taxLabel() { return _t("Tax"); }
    get uomLabel() { return _t("Sold by"); }
    get codeLabel() { return _t("Reference"); }
    get barcodeLabel() { return _t("Barcode"); }
    get onHandLabel() { return _t("On hand"); }
    get forecastLabel() { return _t("Forecast"); }
    get costLabel() { return _t("Cost"); }
    get marginLabel() { return _t("Margin"); }
    get pricelistsLabel() { return _t("On other price lists"); }
    get unavailableLabel() { return _t("Marked unavailable (86)"); }
}
