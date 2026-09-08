/** @odoo-module **/
import { Component, onMounted, onPatched, useRef } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";

export class ProductGrid extends Component {
    static template = "mezze_bridge.ProductGrid";
    static props = {
        // The cashier's card size: compact | standard | training. Drives the grid's
        // own track sizing (see .mz-grid[data-mz-cards] in product-browser.css).
        density: { type: String, optional: true },
        // Reports how many columns the grid ACTUALLY resolved to, so the catalogue
        // header can state the real number. It used to print a hardcoded lookup
        // ({compact:6, standard:5, training:3}) that had no connection to the CSS —
        // the strip said "5 cols" while the grid rendered eleven.
        onColumns: { type: Function, optional: true },
        // ids of the cashier's favourites, so the grid can star them where the
        // design stars them
        favoriteIds: { type: Array, optional: true },
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

    setup() {
        this.gridRef = useRef("grid");
        const report = () => this._reportColumns();
        onMounted(() => {
            report();
            // A cashier resizing the window, or the order panel opening, changes the
            // column count without any state change here — so the caption has to
            // follow the layout, not the render.
            if (typeof ResizeObserver !== "undefined" && this.gridRef.el) {
                this._ro = new ResizeObserver(report);
                this._ro.observe(this.gridRef.el);
            }
        });
        onPatched(report);
    }

    /** The columns the browser actually resolved, read off the resolved grid rather
     *  than predicted. `auto-fill` means the answer depends on the available width,
     *  so it cannot be known from the density alone. */
    _reportColumns() {
        if (!this.props.onColumns || !this.gridRef.el) {
            return;
        }
        const tracks = getComputedStyle(this.gridRef.el).gridTemplateColumns;
        const n = tracks && tracks !== "none" ? tracks.split(/\s+/).filter(Boolean).length : 0;
        if (n && n !== this._cols) {
            this._cols = n;
            this.props.onColumns(n);
        }
    }

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
    get optionsLabel() {
        return _t("Options");
    }

    /** Configurable: real modifier groups, POS attributes, or a combo to choose. */
    hasOptions(p) {
        return !!((p.modifiers && p.modifiers.length)
                  || (p.combos && p.combos.length) || p.is_combo);
    }

    get bestSellerLabel() {
        return _t("BEST SELLER");
    }

    get comboLabel() {
        return _t("COMBO");
    }

    /** "LOW · 3 LEFT" — the design's wording. Only drawn when the count is small
     *  enough to act on; a number on every tile is noise a cashier learns to
     *  ignore, and then ignores the one that mattered. */
    lowStockLabel(p) {
        return _t("LOW · %s LEFT", p.stock_left);
    }

    /** The design stars a favourite in the grid, not only in its own category. */
    isFavorite(p) {
        return (this.props.favoriteIds || []).includes(p.id);
    }

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
