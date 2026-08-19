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
                });
                if (!r || !r.ok) {
                    throw new Error((r && r.message) || _t("The close was refused."));
                }
                this.state.closed = r;
            },
        });
    }
}
