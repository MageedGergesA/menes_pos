/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";
import { icon } from "../../shell/icons";

export class Cart extends Component {
    static template = "mezze_bridge.Cart";
    static props = {
        onCharge: Function,
        inFlight: { type: Boolean, optional: true },
        // Design v3: a check another terminal has moved cannot be charged —
        // "Charge is disabled until resolved". Passed in rather than read here so
        // the Cart keeps knowing nothing about how a conflict was detected.
        conflicted: { type: Boolean, optional: true },
        // SCREEN01_DIFF row 67: the banner itself now renders in the panel, so the
        // Cart needs the conflict and its three resolutions. Still detected and
        // resolved in root.js — this component only draws it.
        conflict: { type: [Object, { value: null }], optional: true },
        conflictTitle: { type: String, optional: true },
        conflictReview: { type: Boolean, optional: true },
        onKeepMine: { type: Function, optional: true },
        onKeepTheirs: { type: Function, optional: true },
        onConflictReview: { type: Function, optional: true },
        // Design v3 (L.tenderLocked): the server refuses edits to a check that
        // already carries a tender, a settlement or a split. It answers "ok" while
        // doing so, so unless the till is told, the cashier's change disappears
        // with nothing said.
        editLocked: { type: Boolean, optional: true },
        // Design v3 panel header: the class of sale + seat, what is on the table,
        // and the check's identity and age.
        orderTitle: { type: String, optional: true },
        orderCountsLine: { type: String, optional: true },
        orderMetaLine: { type: String, optional: true },
        orderNote: { type: String, optional: true },
        orderNoteLabel: { type: String, optional: true },
        orderNoteCount: { type: String, optional: true },
        onOrderNote: { type: Function, optional: true },
        editLockMessage: { type: String, optional: true },
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
        // SCREEN01_DIFF row 74: detach the guest from the check.
        onClearCustomer: { type: Function, optional: true },
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
        // Whether the More sheet is open. Local to the panel on purpose: it is a
        // view preference for this till at this moment, it must not survive a
        // recall, and nothing on the server has an opinion about it.
        // Which line is expanded. The design keeps every OTHER line compact and
        // opens the controls on one at a time; a panel where all six carry a
        // stepper is a panel that fits three.
        // `sumOpen`: whether the money breakdown is expanded. SCREEN01_DIFF row 113.
        // Local and defaulted OPEN, for the same reason as `sheet`: it is a view
        // preference for this till at this moment. Open by default because a bill
        // that hides its tax by default is the failure the VAT row was added to fix
        // — collapsing is a choice the cashier makes, never the state they inherit.
        this.state = useState({
            sheet: false, lineMenu: null, selLine: null, sumOpen: true,
        });
    }

    fmt(amount) {
        return formatMoney(amount, this.order.currency);
    }

    /* ── SCREEN01_DIFF row 118 — the grand total's currency is its own element ──
     *  The design sets the figure at 30px and the currency beside it at 15px in a
     *  muted ink. Composed into one string they carry the same weight, so "LE" is
     *  read with the same emphasis as the amount the guest is being asked for.
     *  Same approach as the product tile (row 37): ask the formatter for the number
     *  alone by handing it a currency with the same precision and no symbol. */
    amountOnly(value) {
        const c = this.order.currency || {};
        return formatMoney(value, { decimals: c.decimals });
    }

    get currencyLabel() {
        return (this.order.currency && this.order.currency.symbol) || "";
    }

    get currencyBefore() {
        return !!(this.order.currency && this.order.currency.position === "before");
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
            out.push({ group: "order", key: "customer", glyph: icon("person"), label: _t("Customer"),
                       disabled: busy, run: () => p.onCustomer() });
        }
        if (p.onSeat) {
            out.push({ group: "order", key: "seat", glyph: icon("chair"), label: _t("Seat"),
                       disabled: busy, run: () => p.onSeat() });
        }
        if (p.canAssign && p.onAssign) {
            out.push({ group: "order", key: "assign", glyph: icon("table_restaurant"), label: _t("Assign table"),
                       disabled: busy || empty, run: () => p.onAssign() });
        }
        if (p.canMove && p.onMove) {
            out.push({ group: "order", key: "move", glyph: icon("swap_horiz"), label: _t("Move table"),
                       disabled: busy, run: () => p.onMove() });
        }
        if (p.canSend && p.onSend) {
            out.push({ group: "order", key: "send", glyph: icon("upload"), label: _t("Send to table"),
                       disabled: busy || empty, run: () => p.onSend() });
        }
        if (p.canPark && p.onPark) {
            out.push({ group: "primary", key: "park", glyph: icon("pause"), label: _t("Park order"),
                       disabled: busy, run: () => p.onPark() });
        }
        if (p.onDiscount) {
            out.push({ group: "order", key: "discount", glyph: icon("percent"), label: _t("Discount"),
                       disabled: busy || empty, run: () => p.onDiscount() });
        }
        if (p.onTaxDisplay) {
            // Core's Actions → Tax. Display only: the server prices every order the
            // same way whichever figure the cashier is looking at.
            out.push({ group: "order", key: "tax", glyph: icon("sell"), label: p.taxDisplayLabel || _t("Tax"),
                       disabled: busy, run: () => p.onTaxDisplay() });
        }
        if (p.onCourses && p.hasTable) {
            // A course is a TABLE's sequence. Offering it on a counter order would be
            // offering something that cannot exist.
            out.push({ group: "fire", key: "courses", glyph: icon("outdoor_grill"), label: _t("Courses"),
                       disabled: busy, run: () => p.onCourses() });
        }
        if (p.onDrawer) {
            // A NO-SALE open: making change, correcting a miscount. Not tied to the
            // cart, so it is offered whether or not anything has been rung up —
            // needing an order first is exactly when a cashier does not have one.
            out.push({ group: "cash", key: "drawer", glyph: icon("point_of_sale"), label: _t("Open drawer"),
                       disabled: busy, run: () => p.onDrawer() });
        }
        if (p.onBill) {
            // The slip a guest asks for at the end of a meal. Acts on what is in the
            // cart, so it is offered whenever there is something to be asked for.
            out.push({ group: "primary", key: "bill", glyph: icon("receipt_long"), label: _t("Bill"),
                       disabled: busy || empty, run: () => p.onBill() });
        }
        if (p.onCode) {
            // Odoo's "Enter Code". One box for a gift card, a coupon or a promo code
            // — the slip in the guest's hand does not say which, and the cashier
            // should not have to know.
            out.push({ group: "cash", key: "code", glyph: icon("dialpad"), label: _t("Enter Code"),
                       disabled: busy || empty, run: () => p.onCode() });
        }
        if (p.onSplit) {
            // the payment screen already does partial + mixed tender; "Split" is the
            // name a cashier looks for, so it points at the flow that exists
            out.push({ group: "order", key: "split", glyph: icon("call_split"), label: _t("Split"),
                       disabled: busy || empty, run: () => p.onSplit() });
        }
        if (p.onFire) {
            out.push({ group: "primary", key: "fire", glyph: icon("skillet"), label: _t("Send to kitchen"),
                       disabled: busy || empty, run: () => p.onFire() });
        }
        if (p.onRefund) {
            out.push({ group: "danger", key: "refund", glyph: icon("currency_exchange"), label: _t("Refund"),
                       disabled: busy, run: () => p.onRefund() });
        }
        if (p.onVoid) {
            // destructive, and manager-gated behind the click — kept last so it is
            // never the neighbour of a routine verb like Fire
            out.push({ group: "danger", key: "void", glyph: icon("block"), label: _t("Void"), danger: true,
                       disabled: busy || empty, run: () => p.onVoid() });
        }
        return out;
    }

    /* ── The design's order-panel footer ──────────────────────────────────────
       Three verbs on the panel and everything else behind More.

       We shipped all sixteen as one flat grid. That is not a smaller version of
       the design's footer, it is a different instrument: sixteen equally-weighted
       tiles state that comping an order and opening the drawer are the same kind
       of decision, and the two a cashier reaches for every single check —
       send to the kitchen, and the bill — are somewhere in the middle of them.

       The order below is the design's, not ours, and the grouping is the design's
       too. Anything this branch does not offer simply does not appear; a group
       with nothing in it is not rendered, so a counter till never opens a sheet
       with an empty "Fire" heading in it. */
    static PRIMARY_ORDER = ["fire", "park", "bill"];

    /** The verbs that live ON the panel. */
    get primaryActions() {
        const by = Object.fromEntries(this.verbs.map((a) => [a.key, a]));
        return Cart.PRIMARY_ORDER.map((k) => by[k]).filter(Boolean);
    }

    /** Everything else, under the design's four headings. */
    get sheetGroups() {
        const titles = {
            order: _t("Order"), fire: _t("Fire"),
            cash: _t("Cash"), danger: _t("Danger"),
        };
        const rest = this.verbs.filter((a) => a.group && a.group !== "primary");
        return ["order", "fire", "cash", "danger"].map((key) => ({
            key, title: titles[key], danger: key === "danger",
            items: rest.filter((a) => a.group === key),
        })).filter((g) => g.items.length);
    }

    get moreLabel() {
        return _t("More");
    }

    get moreGlyph() {
        return icon("more_horiz");
    }

    get noteGlyph() {
        return icon("sticky_note_2");
    }

    /** SCREEN01_DIFF row 97 — the mark the design puts before a typed instruction. */
    /* SCREEN01_DIFF row 78 — the empty check. */
    get emptyGlyph() {
        return icon("receipt_long");
    }

    get emptyTitle() {
        return _t("No items yet");
    }

    get emptyBody() {
        return _t("Tap a dish to start the check.");
    }

    get conflictGlyph() {
        return icon("sync_problem");
    }

    get keepMineLabel() {
        return _t("Keep mine");
    }

    get keepTheirsLabel() {
        return _t("Keep theirs");
    }

    get reviewLabel() {
        return _t("Review");
    }

    get typedNoteGlyph() {
        return icon("edit_note");
    }

    /* ── The design's per-line overflow ──────────────────────────────────────
       The design shows `− n +`, Edit, Note and `⋯` on a line, and puts the rest
       behind that `⋯`: Discount line, Comp line, Assign seat, Move to course,
       Void line — the gated ones carrying a lock, Void tinted danger.

       Ours put every one of them on the row. On a configurable, lot-tracked,
       seated line that is seven controls in a 436px column, so the row wrapped
       and the two verbs a cashier actually uses — the stepper and Note — were
       the same size as comping the item.

       Deliberately NOT here: the design's "Move to course". Our `onCourses` acts
       on the ORDER and is gated on the check having a table; a per-line button
       pointing at it would move the whole check while saying it moved one line.
       It needs a per-line course setter first. */
    /* ── One line expands at a time (design 01 §6, §11) ──────────────────────
       The reference line is a single compact row — qty, name, tags, amount — and
       only the SELECTED one grows to show `− n + · Edit · Note · ⋯`. Ours expanded
       every line, so a six-line check needed the height of twelve: on the seeded
       reference order the sixth line fell below the fold where the design fits all
       six plus an upsell row plus the totals.

       Selecting is also what makes the per-line verbs legible — §11 calls the
       selected / locked / menu states mutually exclusive, which only means anything
       once a line can be selected at all. */
    isLineSelected(line) {
        if (this.state.selLine) {
            return this.state.selLine === line.key;
        }
        // Nothing chosen yet -> the FIRST line is the open one, as the reference
        // shows it (its top line carries the stepper, Edit, Note and the overflow;
        // the five below it are compact). It also means the controls are reachable
        // the moment a check has anything on it, without a cashier having to learn
        // that a line must be tapped before it can be changed.
        const lines = this.lines || [];
        return !!lines.length && lines[0].key === line.key;
    }

    /** Owl compiles `t-on-*` as an EXPRESSION, not a statement block — an inline
     *  `if (…) { … }` fails template compilation outright, and the whole Cart stops
     *  mounting rather than degrading. Keyboard handling belongs in a method. */
    onLineKey(ev, line) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.selectLine(line);
        }
    }

    selectLine(line) {
        const key = line.key;
        const already = this.state.selLine === key;
        this.state.selLine = already ? null : key;
        // Collapsing a line must take its overflow with it, or the menu is left
        // hanging under a row that is no longer open.
        if (already || this.state.lineMenu !== key) {
            this.state.lineMenu = null;
        }
    }

    lineMenuOpen(line) {
        return this.state.lineMenu === line.key;
    }

    toggleLineMenu(line) {
        this.state.lineMenu = this.lineMenuOpen(line) ? null : line.key;
    }

    /** The overflow items for ONE line, in the design's order. Anything this
     *  branch does not offer is simply absent — never a dead control. */
    lineMenuItems(line) {
        const p = this.props;
        const busy = !!p.inFlight;
        const out = [];
        if (p.onLineDiscount && this.canDiscountLine(line)) {
            out.push({ key: "discount", glyph: icon("percent"),
                       label: _t("Discount line"), gated: true, danger: false,
                       disabled: busy, run: () => p.onLineDiscount(line) });
        }
        if (p.onComp && !this.isComped(line)) {
            out.push({ key: "comp", glyph: icon("card_giftcard"),
                       label: _t("Comp line"), gated: true, danger: false,
                       disabled: busy, run: () => p.onComp(line) });
        }
        if (p.onLineSeat) {
            // The label carries the seat once one is set. The control on the row used
            // to read "S2" rather than a fixed verb, and that is the only place the
            // line states who ordered it — moving it into the overflow must not cost
            // the cashier that fact.
            out.push({ key: "seat", glyph: icon("chair"),
                       label: line.seat ? _t("Seat %s", line.seat) : _t("Assign seat"),
                       gated: false, danger: false,
                       disabled: busy, run: () => p.onLineSeat(line) });
        }
        if (p.onNumpad) {
            out.push({ key: "pad", glyph: icon("dialpad"),
                       label: _t("Type quantity"), gated: false, danger: false,
                       disabled: busy, run: () => p.onNumpad(line) });
        }
        if (p.onLots && p.lotsNeeded(line)) {
            out.push({ key: "lot", glyph: icon("inventory_2"),
                       label: _t("Lot / serial"), gated: false, danger: false,
                       disabled: busy, run: () => p.onLots(line) });
        }
        // Removing the line lives HERE, not on the row. The design's line has no
        // delete of its own: taking an item off a check is the same class of act
        // as comping it, and a destructive control sitting permanently beside the
        // quantity stepper is one mis-tap from a wrong bill.
        out.push({ key: "void", glyph: icon("block"),
                   label: _t("Void line"), gated: false, danger: true,
                   disabled: busy, run: () => this.remove(line) });
        return out;
    }

    /** The overflow keeps each control's ORIGINAL test id. These controls did not
     *  disappear when the design moved them off the row — they are one tap deeper —
     *  and renaming their hooks at the same time would have made every existing
     *  test look like a behaviour change rather than a layout one. */
    lineActTestId(key) {
        return {
            discount: "mz-line-discount", comp: "mz-line-comp",
            seat: "mz-line-seat", pad: "mz-line-numpad",
            lot: "mz-line-lot", void: "mz-line-remove",
        }[key] || ("mz-line-" + key);
    }

    get lineMoreLabel() {
        return _t("More actions");
    }

    /** The lock the design puts on a row that will ask for a manager. */
    get gatedGlyph() {
        return icon("lock");
    }

    toggleSheet() {
        this.state.sheet = !this.state.sheet;
    }

    /** A breakdown row is shown only when the order really has one. On a catalogue
     *  where no product carries a tax there is nothing to break down, so the panel
     *  shows one honest Total instead of a Subtotal/Service/VAT stack of zeroes. */
    get hasBreakdown() {
        return this.order.taxBreakdown.length > 0;
    }

    /** One row per tax as the branch names it — "VAT 14%" is the account.tax's own
     *  label, not a string this screen invented. */
    get taxRows() {
        return this.order.taxBreakdown;
    }

    get serviceCharge() {
        return this.order.serviceCharge;
    }

    /* ── SCREEN01_DIFF row 113 — collapsing the breakdown ────────────────────
     *  The design offers the toggle behind its own `hasSumToggle` flag; what makes
     *  that flag true is computed in the prototype and not recoverable from the
     *  frozen file, so the condition here is the only one that makes sense: offer it
     *  when there is a breakdown to collapse. With one Total and nothing above it
     *  the control would toggle nothing. */
    get hasSumToggle() {
        return this.hasBreakdown || !!this.serviceCharge;
    }

    get sumToggleLabel() {
        return this.state.sumOpen ? _t("Hide breakdown") : _t("Show breakdown");
    }

    get sumToggleGlyph() {
        return icon(this.state.sumOpen ? "expand_less" : "expand_more");
    }

    toggleSummary() {
        this.state.sumOpen = !this.state.sumOpen;
    }

    /** "Service charge 12%" — the rate is stated, as the design states it. A bare
     *  "Service charge" invites the guest to ask what it is, at the counter. */
    get serviceLabel() {
        const pct = this.order.servicePct;
        return pct ? _t("Service charge %s", pct + "%") : _t("Service charge");
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

    /** Design v3: a line carried in from another check is badged on the check it
     *  lands on. `/tables/merge` re-homes the source's lines and then unlinks the
     *  source, so without this the destination shows items the cashier looking at
     *  it never rang up and nothing says where they came from. */
    isMerged(line) {
        return !!(line && line.merged_from);
    }

    /** FIRED / PREPARING / SERVED — the design badges what the kitchen has done
     *  with this line, so "is the kofta on its way?" is answered at the till. */
    kitchenLabel(line) {
        const named = {
            fired: _t("FIRED"), accepted: _t("ACCEPTED"),
            preparing: _t("PREPARING"), ready: _t("READY"), served: _t("SERVED"),
        }[line && line.kitchen_state];
        if (named) {
            return named;
        }
        // The design badges EVERY line, and a line the kitchen has not been told
        // about is NEW. We showed a badge only once a ticket existed, so on a
        // freshly rung-up check — which is most of a cashier's day — the column
        // was blank and "has this gone yet?" had no answer on screen.
        return _t("NEW");
    }

    get mergedLabel() {
        return _t("Merged");
    }

    get compedLabel() {
        return _t("Comped");
    }

    get currentOrderLabel() {
        return _t("Current order");
    }

    /** The design puts a `payments` mark on Charge. Falls back to nothing rather
     *  than to a stand-in character: an unrecognised symbol on the one button that
     *  takes money is worse than no symbol. */
    get chargeGlyph() {
        return icon("payments");
    }

    /** The design's wording. "Add customer" describes a database row; "Attach a
     *  guest" describes what the cashier is doing to the check in front of them,
     *  and it is the phrase used on every other surface in the design. */
    get addCustomerLabel() {
        return _t("Attach a guest");
    }

    get removeGuestGlyph() {
        return icon("person_remove");
    }

    get removeGuestLabel() {
        return _t("Remove guest from this check");
    }

    get customerGlyph() {
        return icon(this.props.customerName ? "person" : "person_add");
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
        if (this.props.conflicted) {
            return _t("Resolve conflict to charge");
        }
        return _t("Charge (Ctrl+Enter or F2)");
    }

    get chargeLabel() {
        if (this.props.conflicted) {
            // The design's own words. A disabled button with its usual label
            // reads as a broken till; this one says what to do about it.
            return _t("Resolve conflict to charge");
        }
        if (this.props.inFlight) {
            return _t("Working…");
        }
        // SCREEN01_DIFF row 125 — the amount is its own element beside this label
        // now, set in the numeric face, so it is no longer composed into the string.
        return _t("Charge");
    }

    /** SCREEN01_DIFF row 125 — the design puts the figure on the button only when
     *  it can actually be pressed. A disabled CTA quoting a total reads as a price
     *  the till is refusing rather than one it is waiting to take. */
    get chargeReady() {
        return !!(this.lines.length && !this.props.inFlight && !this.props.conflicted);
    }
}
