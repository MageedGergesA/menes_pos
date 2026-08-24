/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";

export class Cart extends Component {
    static template = "mezze_bridge.Cart";
    static props = {
        onCharge: Function,
        inFlight: { type: Boolean, optional: true },
        // R2A CP5: a table-bound Register can save the order to the table (draft) as
        // well as charge it. Both are optional so counter mode is unchanged.
        canSend: { type: Boolean, optional: true },
        onSend: { type: Function, optional: true },
        // R2A CP6: a counter (non-table) order can be assigned to a table.
        canAssign: { type: Boolean, optional: true },
        onAssign: { type: Function, optional: true },
        // R2A CP7: a table-bound order can be moved (transfer / merge).
        canMove: { type: Boolean, optional: true },
        onMove: { type: Function, optional: true },
        // R2A CP9: the current order can be parked (persisted + set aside).
        canPark: { type: Boolean, optional: true },
        onPark: { type: Function, optional: true },
        // PROTOTYPE PANEL: the order's context moves from the topbar into the panel head.
        tableLabel: { type: [String, { value: null }], optional: true },
        tableSubLabel: { type: String, optional: true },
        guests: { type: Number, optional: true },
        onGuests: { type: Function, optional: true },
        customerName: { type: [String, { value: null }], optional: true },
        onCustomer: { type: Function, optional: true },
        onFire: { type: Function, optional: true },
        onVoid: { type: Function, optional: true },
        onComp: { type: Function, optional: true },
        // Discount: the order-level verb and the per-line button. Both optional, so
        // a principal without orders.discount simply never sees either control.
        onLots: { type: Function, optional: true },
        // Who ordered this LINE. Deliberately not ``onSeat`` — that name is already
        // the verb that seats the whole ORDER at a table, and a second prop under
        // one name is how an unrelated feature quietly stops working.
        onLineSeat: { type: Function, optional: true },
        lotsNeeded: { type: Function, optional: true },
        onNumpad: { type: Function, optional: true },
        presets: { type: Array, optional: true },
        presetId: { type: [Number, { value: null }], optional: true },
        onPreset: { type: Function, optional: true },
        fastMethods: { type: Array, optional: true },
        onFastPay: { type: Function, optional: true },
        onTaxDisplay: { type: Function, optional: true },
        taxDisplayLabel: { type: String, optional: true },
        onCourses: { type: Function, optional: true },
        hasTable: { type: Boolean, optional: true },
        upsell: { type: Array, optional: true },
        onUpsell: { type: Function, optional: true },
        upsellReason: { type: Function, optional: true },
        onDrawer: { type: Function, optional: true },
        onBill: { type: Function, optional: true },
        onCode: { type: Function, optional: true },
        onDiscount: { type: Function, optional: true },
        onLineDiscount: { type: Function, optional: true },
        // Refund does not act on the CURRENT cart — it opens a past order — so it
        // is offered even when the cart is empty, unlike every other verb here.
        onRefund: { type: Function, optional: true },
        onSplit: { type: Function, optional: true },
        orderTypes: { type: Array, optional: true },
        onOrderType: { type: Function, optional: true },
        onNote: { type: Function, optional: true },
        // CONV-3: reopen the configurator on an existing line
        onConfigure: { type: Function, optional: true },
        onSeat: { type: Function, optional: true },
    };

    setup() {
        this.order = this.env.mezze.order;
        // Connect this component to the shared reactive cart state.
        this.cart = useState(this.order.state);
    }

    fmt(amount) {
        return formatMoney(amount, this.order.currency);
    }

    /** The one reason any order-type button is unavailable, stated once. */
    get disabledReason() {
        const blocked = (this.props.orderTypes || []).find((t) => t.disabled && t.reason);
        return blocked ? blocked.reason : "";
    }

    get lines() {
        return this.cart.lines;
    }

    /** "<amount> each" — the reference shows a unit price beside the stepper.
     *  The LINE's unit price, not the product's list price: a configured line costs
     *  its extras, and "each" contradicting the line total is worse than no label. */
    eachLabel(line) {
        return _t("%s each", this.fmt(this.order.unitPrice(line)));
    }

    /** "<n> items" beside the total, as the reference does. */
    get itemsLabel() {
        const n = this.order.count;
        return n === 1 ? _t("1 item") : _t("%s items", n);
    }

    /** A line can be reconfigured only if its product actually has choices. */
    canConfigure(line) {
        const PC = window.MezzeProductConfig;
        return !!(PC && PC.isConfigurable(line.product));
    }

    get editLabel() {
        return _t("Edit");
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
        return this.order.unitPrice(line) * line.qty;
    }

    /** A comped line is still SERVED — it stays on the ticket and on the kitchen
     *  side; only the money changes. Showing it struck through at 0.00 is how the
     *  cashier tells the two apart at a glance. */
    isComped(line) {
        return !!line.comped;
    }

    // ---- PROTOTYPE ACTION GRID ---------------------------------------------------
    /** The verbs the prototype shows are Discount, Note, Customer, Split, Park, Gift
     *  card and Refund. Only Customer and Park exist in this product, so the GRID is
     *  what is adopted — populated with the verbs that genuinely work, including three
     *  the prototype never had. A verb is listed only when its handler was passed in,
     *  so this list can never drift ahead of the features behind it. */
    get lotLabel() {
        return _t("Lot");
    }

    get padLabel() {
        return _t("123");
    }

    get seatLabel() {
        return _t("Seat");
    }

    /** Sold by the kilo rather than by the item. */
    isWeighed(line) {
        return !!(line && line.product && line.product.to_weight);
    }

    /** The measurement, with its unit. A bare "0.4" beside a row of counts reads as
     *  a mistake; "0.4 kg" reads as a scale. */
    weightText(line) {
        const uom = (line.product && line.product.uom_name) || "";
        return uom ? `${line.qty} ${uom}` : String(line.qty);
    }

    /** What the control reads once a seat is set. Short, because it sits in a row of
     *  small controls — but never a bare number, which in a row of quantities and
     *  discounts is unreadable. */
    seatText(line) {
        return line.seat ? _t("S%s", line.seat) : this.seatLabel;
    }

    get verbs() {
        const p = this.props;
        const busy = !!p.inFlight;
        const empty = !this.lines.length;
        const out = [];
        if (p.onCustomer) {
            out.push({ key: "customer", glyph: "☺", label: _t("Customer"),
                       disabled: busy, run: () => p.onCustomer() });
        }
        if (p.onSeat) {
            out.push({ key: "seat", glyph: "⌸", label: _t("Seat"),
                       disabled: busy, run: () => p.onSeat() });
        }
        if (p.canAssign && p.onAssign) {
            out.push({ key: "assign", glyph: "⌗", label: _t("Assign table"),
                       disabled: busy || empty, run: () => p.onAssign() });
        }
        if (p.canMove && p.onMove) {
            out.push({ key: "move", glyph: "⇄", label: _t("Move table"),
                       disabled: busy, run: () => p.onMove() });
        }
        if (p.canSend && p.onSend) {
            out.push({ key: "send", glyph: "↥", label: _t("Send to table"),
                       disabled: busy || empty, run: () => p.onSend() });
        }
        if (p.canPark && p.onPark) {
            out.push({ key: "park", glyph: "❙❙", label: _t("Park order"),
                       disabled: busy, run: () => p.onPark() });
        }
        if (p.onDiscount) {
            out.push({ key: "discount", glyph: "%", label: _t("Discount"),
                       disabled: busy || empty, run: () => p.onDiscount() });
        }
        if (p.onTaxDisplay) {
            // Core's Actions → Tax. Display only: the server prices every order the
            // same way whichever figure the cashier is looking at.
            out.push({ key: "tax", glyph: "%", label: p.taxDisplayLabel || _t("Tax"),
                       disabled: busy, run: () => p.onTaxDisplay() });
        }
        if (p.onCourses && p.hasTable) {
            // A course is a TABLE's sequence. Offering it on a counter order would be
            // offering something that cannot exist.
            out.push({ key: "courses", glyph: "☰", label: _t("Courses"),
                       disabled: busy, run: () => p.onCourses() });
        }
        if (p.onDrawer) {
            // A NO-SALE open: making change, correcting a miscount. Not tied to the
            // cart, so it is offered whether or not anything has been rung up —
            // needing an order first is exactly when a cashier does not have one.
            out.push({ key: "drawer", glyph: "🗄", label: _t("Open drawer"),
                       disabled: busy, run: () => p.onDrawer() });
        }
        if (p.onBill) {
            // The slip a guest asks for at the end of a meal. Acts on what is in the
            // cart, so it is offered whenever there is something to be asked for.
            out.push({ key: "bill", glyph: "🧾", label: _t("Bill"),
                       disabled: busy || empty, run: () => p.onBill() });
        }
        if (p.onCode) {
            // Odoo's "Enter Code". One box for a gift card, a coupon or a promo code
            // — the slip in the guest's hand does not say which, and the cashier
            // should not have to know.
            out.push({ key: "code", glyph: "◈", label: _t("Enter Code"),
                       disabled: busy || empty, run: () => p.onCode() });
        }
        if (p.onSplit) {
            // the payment screen already does partial + mixed tender; "Split" is the
            // name a cashier looks for, so it points at the flow that exists
            out.push({ key: "split", glyph: "◫", label: _t("Split"),
                       disabled: busy || empty, run: () => p.onSplit() });
        }
        if (p.onFire) {
            out.push({ key: "fire", glyph: "▲", label: _t("Fire"),
                       disabled: busy || empty, run: () => p.onFire() });
        }
        if (p.onRefund) {
            out.push({ key: "refund", glyph: "↩", label: _t("Refund"),
                       disabled: busy, run: () => p.onRefund() });
        }
        if (p.onVoid) {
            // destructive, and manager-gated behind the click — kept last so it is
            // never the neighbour of a routine verb like Fire
            out.push({ key: "void", glyph: "⊘", label: _t("Void"), danger: true,
                       disabled: busy || empty, run: () => p.onVoid() });
        }
        return out;
    }

    /** A breakdown row is shown only when the order really has one. On a catalogue
     *  where no product carries a tax there is nothing to break down, so the panel
     *  shows one honest Total instead of a Subtotal/Service/VAT stack of zeroes. */
    get hasBreakdown() {
        const sub = this.order.subtotal;
        return typeof sub === "number" && Math.abs(sub - this.order.estimatedTotal) > 0.004;
    }

    get noteLabel() {
        return _t("Note");
    }

    get discountLabel() {
        return _t("%");
    }

    /** A line already at 100% is comped, not discounted — offering a markdown on a
     *  giveaway is a control that can only confuse. */
    canDiscountLine(line) {
        return !this.isComped(line);
    }

    get compLabel() {
        return _t("Comp");
    }

    get compedLabel() {
        return _t("Comped");
    }

    get currentOrderLabel() {
        return _t("Current order");
    }

    get addCustomerLabel() {
        return _t("Add customer");
    }

    get subtotalLabel() {
        return _t("Subtotal");
    }

    get totalLabel() {
        return _t("Total");
    }

    get guestGroupLabel() {
        return _t("Guest count");
    }

    get fewerGuestsLabel() {
        return _t("Fewer guests");
    }

    get moreGuestsLabel() {
        return _t("More guests");
    }

    get chargeTitle() {
        return _t("Charge (Ctrl+Enter or F2)");
    }

    get chargeLabel() {
        if (this.props.inFlight) {
            return _t("Working…");
        }
        return _t("Charge") + " " + this.fmt(this.order.estimatedTotal);
    }
}
