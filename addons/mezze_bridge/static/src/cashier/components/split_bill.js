/** @odoo-module **/
/**
 * Split Bill V2 — the allocation workspace.
 *
 * A guest says "I'll pay for one burger and one Coke". The whole design is aimed at
 * that sentence: tap the burger, tap the Coke, Split & Pay. Four actions, no modal
 * to set a quantity of one, no building of guest checks nobody asked for.
 *
 * What this component is NOT allowed to do, and why:
 *
 *  - **It does not compute money.** Line contributions shown while selecting are a
 *    preview drawn from the server's own line prices; the amounts that end up on a
 *    check come back from the commit. A cashier is looking at an estimate until the
 *    server says otherwise, and after the commit the preview is replaced outright.
 *  - **It does not write anything while you explore.** Selecting quantities creates
 *    no order, sends no request and fires nothing. Cancel is genuinely free.
 *  - **It does not decide availability.** It shows what the server said was
 *    available and refuses to exceed it, but the server checks again under a lock,
 *    because another till may have taken those burgers while this one was thinking.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class SplitBill extends Component {
    static template = "mezze_bridge.SplitBill";
    static props = {
        api: Object,
        orderId: { type: [Number, Boolean], optional: true },
        orderUuid: { type: [String, Boolean], optional: true },
        currency: { type: Object, optional: true },
        onDone: { type: Function, optional: true },
        onPay: { type: Function, optional: true },
        // Escalation for a failure this screen must not try to explain by itself.
        onAuthRequired: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({
            loading: true,
            error: null,
            stale: false,          // another station changed the bill under us
            committing: false,
            mode: "items",
            order: null,
            root: null,
            lines: [],
            modes: { items: true, seat: false, seat_reason: "", even: true },
            // By seat: the server's grouping, not the browser's arithmetic.
            seats: [],
            shared: [],
            sharedTotal: 0,
            seatsLoading: false,
            picked: {},            // origin_line_id -> qty selected for the new check
            evenWays: 2,
            done: null,            // the child, after a successful commit
        });
        onWillStart(() => this.load());
    }

    // ---------------------------------------------------------------- labels
    // Text lives in the component, not the template: that is how this codebase
    // gets its terms into i18n/*.po for a standalone Owl bundle, and a screen a
    // shift reads in Arabic must not be the one place that stayed English.
    get titleLabel() { return _t("Split bill"); }
    get byItemsLabel() { return _t("By items"); }
    get bySeatLabel() { return _t("By seat"); }
    get bySeatWhyLabel() {
        // The old reason — "not available in this product" — was true and useless:
        // it told a cashier about an absence they could do nothing about. This one
        // names something they can fix, on the panel they are already looking at.
        return _t("Assign items to seats on the order panel first");
    }
    get seatLabel() { return _t("Seat"); }
    get sharedLabel() { return _t("Shared"); }
    get sharedWhyLabel() {
        return _t("Nobody claimed these, so they stay on the table's bill.");
    }
    get takeSeatLabel() { return _t("Take this seat"); }
    get noSeatsLabel() {
        return _t("Nothing on this bill is assigned to a seat yet.");
    }
    seatHeadingLabel(n) { return _t("Seat %s", n); }
    get evenlyLabel() { return _t("Evenly"); }
    get closeLabel() { return _t("Close split"); }
    get readingLabel() { return _t("Reading the bill…"); }
    get tryAgainLabel() { return _t("Try again"); }
    get remainingLabel() { return _t("Remaining"); }
    get newCheckLabel() { return _t("New check"); }
    get moveAllLabel() { return _t("Move all"); }
    get oneMoreLabel() { return _t("One more"); }
    get oneFewerLabel() { return _t("One fewer"); }
    get cancelLabel() { return _t("Cancel"); }
    get resetLabel() { return _t("Reset"); }
    get workingLabel() { return _t("Working…"); }
    get emptyHintLabel() {
        // Deliberately NOT "the item on the left": the panes mirror under RTL, so a
        // directional word would be wrong in Arabic and right in English, which is
        // the kind of bug nobody reports and everybody notices.
        return _t("Tap an item to move it to this check.");
    }
    get staleTitleLabel() { return _t("This bill changed"); }
    get staleBodyLabel() {
        return _t("Another station updated it. Your selection has been kept where it still fits.");
    }
    get refreshLabel() { return _t("Refresh split"); }
    get splitAgainLabel() { return _t("Split again"); }
    get returnToTableLabel() { return _t("Return to table"); }
    get evenLeadLabel() {
        return _t("Divide the bill into equal checks. The odd cent goes to the earliest checks, so the total always matches.");
    }
    get evenNoteLabel() {
        return _t("Creating even checks is not yet wired to the till — use By items, or take several tenders on one bill from Payment.");
    }
    get fewerGuestsLabel() { return _t("Fewer guests"); }
    get moreGuestsLabel() { return _t("More guests"); }
    get tableLabel() { return _t("Table"); }
    get checkLabel() { return _t("Check"); }

    splitPayLabel(amount) {
        return _t("Split & pay %s", amount);
    }
    checkCreatedLabel(seq) {
        return _t("Check %s created", seq);
    }
    remainingOnBillLabel(amount) {
        return _t("Remaining on the bill %s", amount);
    }
    alreadyOnOtherChecksLabel(qty) {
        return _t("%s already on other checks", qty);
    }

    // ------------------------------------------------------------------ loading
    async load() {
        this.state.loading = true;
        this.state.error = null;
        this.state.stale = false;
        try {
            const r = await this.props.api.call("/split/state", {
                order_id: this.props.orderId || undefined,
                uuid: this.props.orderUuid || undefined,
            });
            if (!r || !r.ok) {
                this.state.error = _t("This bill could not be read.");
            } else {
                this.state.order = r.order;
                this.state.root = r.root;
                this.state.lines = r.lines || [];
                this.state.modes = r.modes || this.state.modes;
                this.state.picked = {};
            }
        } catch (e) {
            if (this._escalated(e)) {
                return;
            }
            this.state.error = e && e.kind === "server"
                ? _t("The server could not read this bill. Nothing has been changed.")
                : _t("Could not reach the server. Nothing has been changed.");
        }
        this.state.loading = false;
    }

    /** What each seat owes, asked of the SERVER.
     *
     *  The amounts are not summed here for the same reason the even split is not:
     *  they have to reconcile back to a bill, and a browser that computes its own
     *  version of a total will eventually disagree with the one that gets charged.
     */
    async loadSeats() {
        this.state.seatsLoading = true;
        try {
            const r = await this.props.api.call("/split/seats", {
                order_id: this.props.orderId || undefined,
                uuid: this.props.orderUuid || undefined,
            });
            if (r && r.ok) {
                this.state.seats = r.seats || [];
                this.state.shared = r.shared || [];
                this.state.sharedTotal = r.shared_total || 0;
                this.state.modes = r.modes || this.state.modes;
            }
        } catch (e) {
            if (this._escalated(e)) {
                return;
            }
            this.state.error = _t("The seats on this bill could not be read.");
        }
        this.state.seatsLoading = false;
    }

    async chooseMode(mode) {
        this.state.mode = mode;
        if (mode === "seat" && !this.state.seats.length) {
            await this.loadSeats();
        }
    }

    /** Turn one seat into a selection, then commit it through the ORDINARY path.
     *
     *  Deliberately not a second commit endpoint. Everything that makes a split
     *  safe — availability re-checked under a row lock, combos moving whole, one
     *  child per idempotency key, the kitchen hearing nothing — already holds on
     *  ``/split/commit``, and a by-seat route of its own would be a second place
     *  for all of it to be got right.
     */
    takeSeat(seat) {
        this.state.picked = {};
        for (const row of seat.lines || []) {
            this.state.picked[row.line_id] = row.qty;
        }
        this.state.mode = "items";
    }

    /** After another station moved things: reload truth, keep what still fits. */
    async refreshAfterConflict() {
        const wanted = { ...this.state.picked };
        await this.load();
        for (const line of this.state.lines) {
            const want = wanted[line.id];
            if (want) {
                // Preserve intent only as far as it is still honest.
                const keep = Math.min(want, line.available);
                if (keep > 0) {
                    this.state.picked[line.id] = keep;
                }
            }
        }
    }

    // ------------------------------------------------------------------- lines
    /** Combo children are shown inside their parent, never as their own row: the
     *  commercial unit is the configured product. */
    get rows() {
        return this.state.lines.filter((l) => !l.is_combo_child);
    }

    childrenOf(line) {
        const ids = new Set(line.combo_children || []);
        return this.state.lines.filter((l) => ids.has(l.id));
    }

    picked(line) {
        return this.state.picked[line.id] || 0;
    }

    /** What the guest could still take off this row right now. */
    availableOf(line) {
        return Math.max(0, (line.available || 0) - this.picked(line));
    }

    // ------------------------------------------------------------- interaction
    /** One tap is one unit — the whole speed target lives in this method. */
    onRowTap(line) {
        if (this.availableOf(line) <= 0) {
            // Tapping a fully-selected row winds it back to zero rather than doing
            // nothing: a cashier who over-taps needs a way out that is also a tap.
            this.state.picked[line.id] = 0;
            return;
        }
        this.state.picked[line.id] = this.picked(line) + 1;
    }

    inc(line) {
        if (this.availableOf(line) > 0) {
            this.state.picked[line.id] = this.picked(line) + 1;
        }
    }

    dec(line) {
        const next = this.picked(line) - 1;
        this.state.picked[line.id] = next > 0 ? next : 0;
    }

    moveAll(line) {
        this.state.picked[line.id] = line.available || 0;
    }

    reset() {
        this.state.picked = {};
    }

    onRowKey(ev, line) {
        if (ev.key === " " || ev.key === "Enter") {
            ev.preventDefault();
            this.onRowTap(line);
        } else if (ev.key === "ArrowRight" || ev.key === "+") {
            ev.preventDefault();
            this.inc(line);
        } else if (ev.key === "ArrowLeft" || ev.key === "-") {
            ev.preventDefault();
            this.dec(line);
        }
    }

    // ---------------------------------------------------------------- totals
    /** A line's share of the bill, at the price it was actually sold for. */
    contribution(line, qty) {
        const unit = line.qty ? (line.price_subtotal_incl || 0) / line.qty : 0;
        return unit * (qty === undefined ? this.picked(line) : qty);
    }

    get newCheckTotal() {
        return this.state.lines.reduce((sum, l) => sum + this.contribution(l), 0);
    }

    get remainingTotal() {
        const total = (this.state.order && this.state.order.amount_total) || 0;
        return Math.max(0, total - this.newCheckTotal);
    }

    get hasSelection() {
        return Object.values(this.state.picked).some((q) => q > 0);
    }

    money(v) {
        const sym = (this.props.currency && this.props.currency.symbol) || "";
        const n = Number(v || 0).toFixed(2);
        return sym ? `${n} ${sym}` : n;
    }

    // ----------------------------------------------------------------- commit
    get allocations() {
        return Object.entries(this.state.picked)
            .filter(([, qty]) => qty > 0)
            .map(([id, qty]) => ({ origin_line_id: Number(id), quantity: qty }));
    }

    /**
     * Commit, then hand the child straight to Payment.
     *
     * The idempotency key is minted ONCE per attempt and reused on retry, which is
     * what makes a double tap — or a retry after the network vanished mid-request —
     * one child rather than two. It is only renewed after a success.
     */
    async splitAndPay() {
        if (!this.hasSelection || this.state.committing) {
            return;
        }
        this.state.committing = true;
        this.state.error = null;
        if (!this._idemKey) {
            this._idemKey = `sb-${this.props.orderId || this.props.orderUuid}-${Date.now()}-${Math.random()
                .toString(36)
                .slice(2, 8)}`;
        }
        try {
            const r = await this.props.api.call("/split/commit", {
                order_id: this.props.orderId || undefined,
                uuid: this.props.orderUuid || undefined,
                allocations: this.allocations,
                expected_revision: this.state.order ? this.state.order.revision : undefined,
                idempotency_key: this._idemKey,
            });
            if (r && r.ok) {
                this._idemKey = null;
                this.state.done = r.child;
                this.state.order = r.root;
                this.state.lines = r.lines || [];
                this.state.picked = {};
                if (this.props.onPay) {
                    this.props.onPay(r.child);
                }
            } else if (r && r.error === "stale_revision") {
                this.state.stale = true;
            } else {
                this.state.error = this.reasonText((r && r.error) || "");
            }
        } catch (e) {
            if (this._escalated(e)) {
                this.state.committing = false;
                return;
            }
            // The server NAMES why it refused, and it says so with an HTTP status —
            // 400 for a bad allocation, 409 for a bill somebody else changed. Both
            // are thrown by api.call rather than returned, so the branches above
            // never saw them and every refusal arrived here to be reported as the
            // same shrug. A cashier was told to "try again" about a bill that was
            // already paid, and about a stale picture that a redraw would have
            // fixed. The reason travels on the error as `error`; use it.
            const code = (e && e.error) || "";
            if (code === "stale_revision") {
                this.state.stale = true;
            } else if (code && code !== "internal_error") {
                this.state.error = this.reasonText(code);
            } else {
                // Only a TRANSPORT failure is genuinely ambiguous — the request may
                // have been applied before the answer was lost. Anything the server
                // actually answered is known not to have landed, and telling a
                // cashier to go and check a bill that certainly did not change wastes
                // the one thing they do not have during service.
                // Kept as single string literals: these are catalogue keys, and a
                // sentence assembled with + is a different key from the one translated.
                this.state.error = e && e.kind === "network"
                    ? _t("The connection dropped and we cannot tell whether the split went through. Reopen the bill to check before trying again.")
                    : _t("The split was refused and nothing has changed. Try again.");
            }
        }
        this.state.committing = false;
    }

    /** Server reasons are stable strings; the sentences live here. */
    reasonText(code) {
        return {
            over_allocated: _t("There are not enough of those left on the bill."),
            quantity_not_integer: _t("Items can only be moved in whole units."),
            quantity_not_positive: _t("Choose at least one item."),
            combo_child_not_movable: _t("Part of a meal cannot move on its own."),
            combo_not_atomic: _t("A meal moves as one item."),
            already_paid: _t("This check has been paid and cannot be changed here."),
            nothing_selected: _t("Nothing is selected yet."),
            unknown_line: _t("That item is no longer on the bill."),
        }[code] || _t("The split was refused.");
    }

    close() {
        if (this.props.onDone) {
            this.props.onDone();
        }
    }

    /**
     * Hand a signed-out session back to the till instead of describing it.
     *
     * A rejected call arrives here as an exception whatever went wrong, and this
     * screen used to report every one of them as a dropped connection. That is a
     * bad answer for an expired or revoked token: the cashier is told to check
     * the bill and try again, the retry fails identically, and nothing on screen
     * ever says "sign in". The till already knows how to handle that — this just
     * stops swallowing it.
     *
     * Returns true when the error has been dealt with by escalating.
     */
    _escalated(e) {
        if (e && e.kind === "auth") {
            if (this.props.onAuthRequired) {
                this.props.onAuthRequired(e);
                return true;
            }
        }
        return false;
    }

    // ------------------------------------------------------------------ evenly
    get evenAmounts() {
        const total = (this.state.order && this.state.order.amount_total) || 0;
        const ways = Math.max(1, this.state.evenWays);
        // Shown in minor units the same way the server computes it, so the screen
        // and the receipt cannot disagree about who pays the extra cent.
        const cents = Math.round(total * 100);
        const base = Math.floor(cents / ways);
        const residual = cents - base * ways;
        return Array.from({ length: ways }, (_, i) => (base + (i < residual ? 1 : 0)) / 100);
    }

    evenWays(delta) {
        this.state.evenWays = Math.min(20, Math.max(2, this.state.evenWays + delta));
    }
}
