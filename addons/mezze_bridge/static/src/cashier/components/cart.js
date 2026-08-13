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
        onSplit: { type: Function, optional: true },
        onNote: { type: Function, optional: true },
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

    get lines() {
        return this.cart.lines;
    }

    /** "<amount> each" — the reference shows a unit price beside the stepper. */
    eachLabel(line) {
        return _t("%s each", this.fmt(line.product.list_price));
    }

    /** "<n> items" beside the total, as the reference does. */
    get itemsLabel() {
        const n = this.order.count;
        return n === 1 ? _t("1 item") : _t("%s items", n);
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
