/** @odoo-module **/
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";

export class ProductGrid extends Component {
    static template = "mezze_bridge.ProductGrid";
    static props = {
        products: Array,
        currency: Object,
        onSelect: Function,
        // R1B keyboard: id of the tile highlighted for Enter-to-add (null when not searching).
        highlightId: { type: [Number, { value: null }], optional: true },
    };

    fmt(amount) {
        return formatMoney(amount, this.props.currency);
    }

    /** Thumbnail for an image-led card (DESIGN FIDELITY).
     *
     *  Uses Odoo's NATIVE image route, which the Register page can already reach:
     *  /mezze/pos is auth='user', so the browser session authorises it — no token is
     *  exposed to the page and no new backend route was added. `image_256` is the
     *  POS thumbnail size (the same field `has_image` is derived from), so a card
     *  never pulls a full-resolution photo into a till screen.
     */
    imageUrl(product) {
        return `/web/image/product.product/${product.id}/image_256`;
    }

    /** Neutral fallback when a product genuinely has no image. The reference's rich
     *  food photography is fixture content; inventing it here would be fake data. */
    initials(name) {
        return String(name || "")
            .replace(/^\[[^\]]*\]\s*/, "")
            .split(/\s+/)
            .slice(0, 2)
            .map((w) => w.charAt(0))
            .join("")
            .toUpperCase();
    }

    /** Accessible name for the quick-add affordance. "+" alone names nothing, and a
     *  bare "Add" repeated once per card is indistinguishable in a screen reader's
     *  element list — the product has to be in the name. Localised through the same
     *  catalogue as the rest of the Register, so an Arabic till never hears English. */
    addLabel(product) {
        return _t("Add %s to order", product.name);
    }

    select(product) {
        if (product.available === false) {
            return;
        }
        this.props.onSelect(product);
    }
}
