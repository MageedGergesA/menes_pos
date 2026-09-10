/** @odoo-module **/
import { Component, onMounted, onPatched, useRef } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon } from "../../shell/icons";
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
        const report = () => this._layout();
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

    /* ── Grid layout: the design's model, clamped ────────────────────────────
       The design sizes the catalogue by COLUMN COUNT, not by card width: each
       density names a target (Compact 6 / Standard 5 / Training 4) and a maximum
       tile width (300 / 340 / 400), and then caps the count at ceil(sqrt(n)).

       That cap is the part worth having. Without it a six-item category spreads
       across six thin columns — one dish per column, a screen of mostly gutter —
       because auto-fill will always make as many tracks as fit. With it, six items
       lay out three-across and look like a menu.

       The design is authored at a fixed 1920 canvas; ours is responsive, so the
       count is clamped by what will actually fit at a legible width. Honouring the
       target blindly at 1280 would give five 110px cards, which is the failure the
       max-width is there to prevent at the other end. */
    static DENSITY = {
        compact:  { cols: 6, maxTile: 300, minTile: 140 },
        standard: { cols: 5, maxTile: 340, minTile: 168 },
        training: { cols: 4, maxTile: 400, minTile: 210 },
    };

    get densitySpec() {
        return ProductGrid.DENSITY[this.props.density] || ProductGrid.DENSITY.standard;
    }

    /** Apply the resolved template, then report the count that resulted.
     *
     *  The branch's FIXED-column setting wins outright. `:root[data-mz-grid-cols]`
     *  is an explicit administrative choice, and it is expressed as a CSS rule — so
     *  the inline template written below would silently beat it, because an inline
     *  style outranks every stylesheet. A setting that looks authoritative and
     *  changes nothing is the exact failure this file already carries two comments
     *  about; here we simply stand aside and let the rule own the layout. */
    _layout() {
        const el = this.gridRef.el;
        if (!el) {
            return;
        }
        const fixed = parseInt(
            document.documentElement.getAttribute("data-mz-grid-cols") || "", 10);
        if (fixed > 0) {
            el.style.removeProperty("grid-template-columns");
            el.style.removeProperty("max-width");
            const n = getComputedStyle(el).gridTemplateColumns
                .split(/\s+/).filter(Boolean).length;
            if (this.props.onColumns && n && n !== this._cols) {
                this._cols = n;
                this.props.onColumns(n);
            }
            return;
        }
        const spec = this.densitySpec;
        const n = (this.props.products || []).length;
        const cs = getComputedStyle(el);
        // SCREEN01_DIFF row 27 — the design's cap is `cols * maxTile + (cols-1) * 14`.
        // The gap is read from the sheet so the two can never drift; the literal is
        // only the fallback for a grid that has not been laid out yet, and it has to
        // be the ruled 14 rather than the retired 11.
        const gap = parseFloat(cs.columnGap || cs.gap) || 14;
        const inner = el.clientWidth
            - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0);

        const fits = Math.max(1, Math.floor((inner + gap) / (spec.minTile + gap)));
        const bySqrt = n ? Math.ceil(Math.sqrt(n)) : 1;
        const cols = Math.max(1, Math.min(spec.cols, bySqrt, fits));

        el.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
        // The grid never grows past what `cols` tiles at their maximum come to, so a
        // wide till gets a menu rather than four enormous cards.
        el.style.maxWidth = `${cols * spec.maxTile + (cols - 1) * gap}px`;

        if (this.props.onColumns && cols !== this._cols) {
            this._cols = cols;
            this.props.onColumns(cols);
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

    /* ── SCREEN01_DIFF row 37 — the amount and the currency are two elements ──
     *  The design sets the figure in the numeric face at 16px/700 and the currency
     *  beside it at 12px/500 in a muted ink: on a grid of cards the eye is scanning
     *  prices, and three characters of "LE" repeated twenty times at the same weight
     *  as the number is noise the cashier has to read past.
     *
     *  `formatMoney` composes the two, so this asks it for the number alone by
     *  handing it a currency that has the same precision and no symbol. The symbol
     *  is then rendered as its own span. */
    priceAmount(product) {
        const c = this.props.currency || {};
        return formatMoney(this.price(product), { decimals: c.decimals });
    }

    get currencyLabel() {
        return (this.props.currency && this.props.currency.symbol) || "";
    }

    /** Which side the symbol goes. The design is authored on an after-the-figure
     *  currency (LE), but a branch on a before-the-figure one ($) must not read
     *  "50.00 $" just because the design never had that case. */
    get currencyBefore() {
        return !!(this.props.currency && this.props.currency.position === "before");
    }

    /* ── SCREEN01_DIFF row 46 — a weighed item says so on the card ────────────
     *  The design marks it on the MEDIA, not in the text band: the fact that a dish
     *  is priced per kilo changes what tapping it means (a quantity has to be
     *  weighed and typed, it cannot be stepped), and that has to be legible before
     *  the tap, not after. `to_weight` already ships in the bootstrap payload — the
     *  cart line has read it since the weighed-line work; the grid simply never
     *  looked at it. */
    isWeighed(product) {
        return !!(product && product.to_weight);
    }

    get byWeightLabel() {
        return _t("By weight");
    }

    get weighGlyph() {
        return icon("scale");
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
