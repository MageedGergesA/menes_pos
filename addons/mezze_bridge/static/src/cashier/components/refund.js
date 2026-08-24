/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";

/** Give money back, from the till.
 *
 *  ``/orders/refund`` is the best-engineered code in this module — per-line quantity
 *  ceilings, an order-level money ceiling in integer minor units, a per-original
 *  advisory lock, and an ORM constraint behind all of it — and until now nothing in
 *  the product could reach it. A cashier facing a guest with a wrong dish had to
 *  leave the till and open the back office.
 *
 *  Two rules shape this screen.
 *
 *  **It refunds LINES, not amounts.** The endpoint reconstructs every refund line
 *  from server truth and refuses a request that does not name its source line, so
 *  this asks which items are coming back rather than how much money to hand over.
 *  A cashier who could type an amount would eventually type the wrong one.
 *
 *  **It shows what is LEFT.** ``refundable`` already accounts for earlier partial
 *  refunds, so the stepper cannot ask for more than remains. Letting it try and then
 *  showing a rejection is how a cashier ends up apologising for something they
 *  cannot explain.
 */
export class RefundScreen extends Component {
    static template = "mezze_bridge.RefundScreen";
    static props = {
        api: Object,
        sessionId: { type: [Number, { value: null }], optional: true },
        currency: { type: Object, optional: true },
        onDone: Function,
        onCancel: Function,
    };

    setup() {
        this.state = useState({
            loading: true,
            orders: [],
            picked: null,          // the order being refunded
            qty: {},               // line_id -> quantity coming back
            reason: "",
            error: "",
            busy: false,
            search: "",
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const res = await this.props.api.call("/orders/recent", {
                session_id: this.props.sessionId, limit: 40,
            });
            this.state.orders = (res && res.orders) || [];
        } catch (err) {
            this.state.error = (err && err.message)
                || _t("Could not load recent orders.");
        } finally {
            this.state.loading = false;
        }
    }

    fmt(amount) {
        return formatMoney(amount, this.props.currency);
    }

    get visibleOrders() {
        const q = this.state.search.trim().toLowerCase();
        if (!q) {
            return this.state.orders;
        }
        return this.state.orders.filter((o) =>
            (o.pos_reference || "").toLowerCase().includes(q)
            || (o.partner || "").toLowerCase().includes(q));
    }

    /** Lines that still have something to give back. An order refunded in full is
     *  shown, but with nothing to select — that is the honest answer to "can I
     *  refund this?", and it is different from the order not being there. */
    get refundableLines() {
        const o = this.state.picked;
        return o ? (o.lines || []).filter((l) => this.remaining(l) > 0) : [];
    }

    remaining(line) {
        const left = typeof line.refundable === "number" ? line.refundable : line.qty;
        return Math.max(0, left);
    }

    picked(line) {
        return this.state.qty[line.line_id] || 0;
    }

    step(line, delta) {
        const next = Math.min(this.remaining(line),
                              Math.max(0, this.picked(line) + delta));
        this.state.qty[line.line_id] = next;
        this.state.error = "";
    }

    all(line) {
        this.state.qty[line.line_id] = this.remaining(line);
        this.state.error = "";
    }

    pick(order) {
        this.state.picked = order;
        this.state.qty = {};
        this.state.error = "";
    }

    back() {
        this.state.picked = null;
        this.state.qty = {};
    }

    get total() {
        const o = this.state.picked;
        if (!o) {
            return 0;
        }
        return (o.lines || []).reduce((sum, l) => {
            const n = this.picked(l);
            if (!n || !l.qty) {
                return sum;
            }
            return sum + (l.price / l.qty) * n;      // the line's own unit price
        }, 0);
    }

    get anythingPicked() {
        return Object.values(this.state.qty).some((n) => n > 0);
    }

    get canSubmit() {
        return this.anythingPicked && !!this.state.reason.trim() && !this.state.busy;
    }

    setReason(value) {
        this.state.reason = value;
        this.state.error = "";
    }

    setSearch(value) {
        this.state.search = value;
    }

    get lines() {
        return Object.entries(this.state.qty)
            .filter(([, n]) => n > 0)
            .map(([lineId, n]) => ({ line_id: Number(lineId), qty: n }));
    }

    async submit() {
        if (!this.canSubmit) {
            return;
        }
        this.state.busy = true;
        this.state.error = "";
        try {
            await this.props.onDone({
                orderId: this.state.picked.id,
                lines: this.lines,
                reason: this.state.reason.trim(),
                amount: this.total,
            });
        } catch (err) {
            this.state.error = this.explain(err);
        } finally {
            this.state.busy = false;
        }
    }

    /** A cashier is owed a sentence, not an error code.
     *
     *  The screen used to print whatever the envelope carried, so a refusal read as
     *  "permission_denied" — which tells the person holding the receipt nothing and
     *  tells the cashier nothing they can act on. */
    explain(err) {
        const code = (err && err.error) || "";
        const known = {
            permission_denied: _t("A supervisor or manager has to approve this refund."),
            approval_required: _t("A supervisor or manager has to approve this refund."),
            refund_line_missing: _t("Choose at least one item to give back."),
            refund_exceeds: _t("That is more than is left to refund on this order."),
            order_not_found: _t("That order could not be found any more."),
            currency_mismatch: _t("That order was taken in a different currency."),
            company_mismatch: _t("That order belongs to another company."),
        };
        return known[code] || (err && err.message)
            || _t("That refund did not go through.");
    }

    // ---- labels ----
    get title() { return _t("Refund"); }
    get pickLabel() { return _t("Which order?"); }
    get searchLabel() { return _t("Search a receipt or a customer"); }
    get reasonLabel() { return _t("Why is this coming back?"); }
    get cancelLabel() { return _t("Cancel"); }
    get backLabel() { return _t("Back to orders"); }
    get emptyLabel() { return _t("No orders in this session yet."); }
    get nothingLabel() {
        return _t("Everything on this order has already been refunded.");
    }
    get allLabel() { return _t("All"); }
    get submitLabel() {
        return this.anythingPicked
            ? _t("Refund %s", this.fmt(this.total))
            : _t("Choose what is coming back");
    }
}
