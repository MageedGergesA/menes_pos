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
            picked: {},            // origin_line_id -> qty selected for the new check
            evenWays: 2,
            done: null,            // the child, after a successful commit
        });
        onWillStart(() => this.load());
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
            this.state.error = _t("Could not reach the server. Nothing has been changed.");
        }
        this.state.loading = false;
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
            // We do not know whether it landed. Say so, and keep the key so a retry
            // cannot become a second check.
            this.state.error = _t(
                "The connection dropped and we cannot tell whether the split went " +
                    "through. Reopen the bill to check before trying again."
            );
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
