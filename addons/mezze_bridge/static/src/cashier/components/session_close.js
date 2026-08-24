/** @odoo-module **/
/**
 * End of day — close the till's POS session from the Register.
 *
 * Until now this was the last step of the daily cycle that forced somebody into
 * the Odoo backend. A restaurant closing at 1am should not need a laptop.
 *
 * Two things this screen deliberately does NOT do:
 *
 *  - it does not compute the close. `action_pos_session_closing_control()` on the
 *    server posts the journal entry, exactly as Odoo's own POS does; this screen
 *    reads a preview and then asks the server to close. Nothing about the money is
 *    decided here.
 *  - it does not grant anybody permission. Closing needs a capability a till does
 *    not hold, so the commit goes through the SAME manager-PIN elevation used for
 *    comps and refunds — one prompt, verified server-side, both identities audited.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class SessionClose extends Component {
    static template = "mezze_bridge.SessionClose";
    static props = {
        api: Object,
        boot: { type: Object, optional: true },
        currency: { type: Object, optional: true },
        onElevate: Function,
    };

    setup() {
        this.state = useState({
            loading: true,
            error: null,
            preview: null,
            closed: null,
            // The shift report. Kept out of the initial load: the close preview is
            // what this screen is for, and a cashier who only wants to close should
            // not wait on a full day's aggregation to see the drawer figure.
            z: null,
            zLoading: false,
            zError: null,
            zPrinted: null,
            // Counting the drawer, note by note. `counts` is keyed by denomination
            // id; the total is derived rather than typed, so the two cannot
            // disagree — the server refuses a mismatch anyway.
            counts: {},
        });
        onWillStart(() => this.load());
    }

    get sessionId() {
        return (this.props.boot || {}).session_id || null;
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        const id = this.sessionId;
        if (!id) {
            this.state.loading = false;
            this.state.error = _t("This register has no open session to close.");
            return;
        }
        try {
            const r = await this.props.api.call(`/sessions/${id}/close/preview`, {});
            if (!r || !r.ok) {
                this.state.error = (r && r.message) || _t("Could not read the session.");
            } else {
                this.state.preview = r;
            }
        } catch (e) {
            // A till that cannot reach the server must not show a half-read total
            // and invite a close on it.
            this.state.error = _t("Could not reach the server. Try again in a moment.");
        }
        this.state.loading = false;
    }

    /** The Z report: gross, refunds, tax per rate, discounts, takings by tender.
     *
     *  Mezze had no Z report on any surface that ships — the only one in the tree
     *  was the design prototype, whose figures are literals. This reads the branch's
     *  own day from `/sessions/<id>/z_report`, which is Odoo's `get_sale_details`.
     */
    async loadZ() {
        const id = this.sessionId;
        if (!id || this.state.zLoading) {
            return;
        }
        this.state.zLoading = true;
        this.state.zError = null;
        try {
            const r = await this.props.api.call(`/sessions/${id}/z_report`, {});
            if (!r || !r.ok) {
                this.state.zError = (r && r.message) || _t("Could not read the shift report.");
            } else {
                this.state.z = r;
            }
        } catch (e) {
            this.state.zError = _t("Could not reach the server. Try again in a moment.");
        }
        this.state.zLoading = false;
    }

    async printZ() {
        const id = this.sessionId;
        if (!id) {
            return;
        }
        this.state.zPrinted = null;
        this.state.zError = null;
        try {
            // The hardware endpoints live outside the versioned API prefix.
            const r = await this.props.api.call("/print/z_report", { session_id: id },
                                                { base: "/mezze/hardware" });
            if (r && r.ok) {
                this.state.zPrinted = _t("Sent to the printer.");
            } else {
                // A printer that is not there is worth saying out loud; the figures on
                // screen are still the day's figures.
                this.state.zError = (r && r.message)
                    || _t("The printer could not be reached.");
            }
        } catch (e) {
            this.state.zError = _t("The printer could not be reached.");
        }
    }

    get denominations() {
        return (this.state.preview && this.state.preview.denominations) || [];
    }

    countOf(denomination) {
        return this.state.counts[denomination.id] || 0;
    }

    setCount(denomination, value) {
        const n = parseInt(value, 10);
        this.state.counts[denomination.id] =
            Number.isFinite(n) && n > 0 ? n : 0;
    }

    /** What the drawer holds, from the notes actually counted. */
    get countedCash() {
        return this.denominations.reduce(
            (sum, d) => sum + d.value * this.countOf(d), 0);
    }

    get anythingCounted() {
        return this.denominations.some((d) => this.countOf(d) > 0);
    }

    /** Over or short against what the session expects. Shown BEFORE the close, so
     *  the cashier finds out at the drawer rather than from a refusal. */
    get variance() {
        const p = this.state.preview;
        if (!p || !this.anythingCounted) {
            return null;
        }
        return this.countedCash - (p.cash_expected || 0);
    }

    get varianceLabel() {
        const v = this.variance;
        if (v === null) {
            return "";
        }
        if (Math.abs(v) < 0.005) {
            return _t("The drawer balances.");
        }
        return v > 0
            ? _t("Over by %s", this.money(v))
            : _t("Short by %s", this.money(Math.abs(v)));
    }

    money(v) {
        const sym = (this.props.currency && this.props.currency.symbol) || "";
        const n = Number(v || 0).toFixed(2);
        return sym ? `${n} ${sym}` : n;
    }

    /** Open orders are the one thing that should stop a close, so say so plainly. */
    get blocked() {
        const p = this.state.preview;
        return !!(p && p.orders_open > 0);
    }

    get blockedReason() {
        const p = this.state.preview || {};
        return _t(
            "%s order(s) are still open. Settle or cancel them before closing the day.",
            p.orders_open
        );
    }

    confirm() {
        if (this.blocked || !this.state.preview) {
            return;
        }
        const id = this.sessionId;
        // The capability a till lacks is borrowed for exactly this one call.
        this.props.onElevate({
            title: _t("Close the session"),
            detail: _t("Posts the day's journal entry. This cannot be undone."),
            run: async ({ managerCode, managerPin }) => {
                const r = await this.props.api.call(`/sessions/${id}/close`, {
                    manager_code: managerCode,
                    manager_pin: managerPin,
                    // Send the NOTES, not a typed total. The server derives the
                    // figure from them and keeps the breakdown, so a variance can be
                    // investigated instead of merely recorded.
                    denominations: this.anythingCounted
                        ? this.denominations
                              .filter((d) => this.countOf(d) > 0)
                              .map((d) => ({ value: d.value, count: this.countOf(d) }))
                        : undefined,
                });
                if (!r || !r.ok) {
                    throw new Error((r && r.message) || _t("The close was refused."));
                }
                this.state.closed = r;
            },
        });
    }
}
