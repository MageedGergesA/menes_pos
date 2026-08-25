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
        // 'total' (tax-included) or 'subtotal' (tax-excluded) — the branch's
        // iface_tax_included, flipped by the Tax verb. Display only.
        taxDisplay: { type: String, optional: true },
        // R1B keyboard: id of the tile highlighted for Enter-to-add (null when not searching).
        highlightId: { type: [Number, { value: null }], optional: true },
        // 86: mark a product unavailable branch-wide. Passed only when the principal
        // may actually do it, so the badge never appears as a control that fails.
        onEightySix: { type: Function, optional: true },
        // "How many left?" / "what does that cost us?" — asked across the counter.
        onInfo: { type: Function, optional: true },
    };

    /** The control has to name its product: a row of identical "Info" buttons is
     *  indistinguishable in a screen reader's element list. */
    infoLabel(p) {
        return _t("About %s", p.name);
    }

    /** "86" is the kitchen's word for "we are out of it" and the reference shows it
     *  on every card. It is a TOGGLE: 86 a dish when it runs out, un-86 it when the
     *  next batch lands, without leaving the till. */
    eightySixLabel(p) {
        return p.available === false ? _t("Bring back %s", p.name) : _t("86 %s", p.name);
    }

    /** The catalogue price in the mode this till is showing.
     *
     *  The tile rendered `list_price` unconditionally, so a branch set to
     *  "Tax-Excluded Price" — and a cashier who flips the Tax verb — saw the grid
     *  disagree with the cart beside it. Both figures come from the server's own
     *  `compute_all`; this only chooses between them.
     */
    price(product) {
        const wanted = this.props.taxDisplay === "subtotal"
            ? product.price_excl
            : product.price_incl;
        return typeof wanted === "number" ? wanted : (product.list_price || 0);
    }

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
            // an internal reference, not part of what the dish is called
            .replace(/^\[[^\]]*\]\s*/, "")
            // A parenthetical is a QUALIFIER, not a word of the name: "Baklava
            // (per kg)" is Baklava. Taking it as a word gave charAt(0) of "(per",
            // so the tile read "B(" -- a bracket standing in for a dish.
            .replace(/\([^)]*\)/g, " ")
            .split(/\s+/)
            // Anything with no letter or digit contributes no initial. A name can
            // start with punctuation or an ampersand, and a tile showing "&" names
            // nothing. Unicode-aware, so an Arabic catalogue initials correctly.
            .map((w) => (w.match(/[\p{L}\p{N}]/u) || [""])[0])
            .filter(Boolean)
            .slice(0, 2)
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
