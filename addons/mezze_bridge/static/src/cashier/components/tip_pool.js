/** @odoo-module **/
/**
 * Tip pool — the shift's tip liability, how it is split, and paying it out.
 *
 * A tip is money owed to staff from the moment it is captured: not the branch's
 * to keep, spend or round. So this screen shows the liability first, then the
 * rule being applied, then what each person gets — the order a team actually
 * argues in. See `docs/TIP_POOLING.md` §7.
 *
 * Two things this screen deliberately does NOT do:
 *
 *  - it does no arithmetic. Every figure is read from `/tips/*`, which derives
 *    it from the one ledger. A screen that recomputes a share is a second owner
 *    of the number, which is the defect the whole contract exists to remove.
 *  - it does not grant permission. Signing a distribution needs a capability a
 *    till does not hold, so approval goes through the SAME manager-PIN elevation
 *    as comps, refunds and the session close.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class TipPool extends Component {
    static template = "mezze_bridge.TipPool";
    static props = {
        api: Object,
        currency: { type: Object, optional: true },
        onElevate: Function,
    };

    setup() {
        this.state = useState({
            loading: true,
            error: null,      // a refusal to show the manager, not a broken screen
            denied: false,
            data: null,
            busy: false,
        });
        onWillStart(() => this.load());
    }

    async load() {
        Object.assign(this.state, { loading: true, error: null, denied: false });
        try {
            this.state.data = await this.props.api.call("/tips/pool", {});
        } catch (e) {
            // A till without reports rights should read as gated, not as broken.
            if (e && (e.status === 403 || e.code === "forbidden")) {
                this.state.denied = true;
            } else {
                this.state.error = (e && e.message) || _t("Could not read the tip pool.");
            }
        } finally {
            this.state.loading = false;
        }
    }

    get run() {
        return (this.state.data && this.state.data.run) || null;
    }

    get rows() {
        return (this.run && this.run.rows) || [];
    }

    get signed() {
        const r = this.run;
        return !!r && (r.state === "approved" || r.state === "paid");
    }

    get activeRule() {
        return (this.run && this.run.rule) || "hours";
    }

    /** Distributed total. Shown beside the pool because the contract's invariant
     *  is that they are EQUAL — and this is where a guest of the house can see it. */
    get distributed() {
        return this.rows.reduce((a, r) => a + r.share, 0);
    }

    get exact() {
        const r = this.run;
        return !!r && Math.abs(this.distributed - r.pool) < 0.005;
    }

    money(v) {
        const sym = (this.state.data && this.state.data.currency) || "";
        return `${sym} ${Number(v || 0).toFixed(2)}`.trim();
    }

    ruleMessage(code) {
        return {
            custom_pct_not_100: _t("Custom percentages must total 100 before this can be signed."),
            no_eligible_staff: _t("Nobody eligible is on shift."),
            no_weight_to_split_by: _t("No worked hours to split by yet."),
            unknown_rule: _t("That rule is not one of the six."),
        }[code] || code || _t("That rule could not be applied.");
    }

    async pickRule(rule) {
        if (this.signed || this.state.busy) {
            return;   // a signed run is re-cut by voiding it, never by a click
        }
        this.state.busy = true;
        this.state.error = null;
        try {
            const res = await this.props.api.call("/tips/compute", { rule });
            this.state.data.run = res.run;
        } catch (e) {
            this.state.error = this.ruleMessage(e && (e.code || e.message));
            if (e && e.run) {
                this.state.data.run = e.run;
            }
        } finally {
            this.state.busy = false;
        }
    }

    approve() {
        const run = this.run;
        if (!run || this.signed) {
            return;
        }
        this.props.onElevate({
            title: _t("Sign this distribution"),
            detail: _t(
                "Approval takes a snapshot: the signed figures are the paid figures. " +
                "A later clock-out cannot re-cut it."),
            run: async ({ managerCode, managerPin }) => {
                const res = await this.props.api.call("/tips/approve", {
                    run_id: run.id,
                    cashier_id: managerCode,
                    pin: managerPin,
                });
                this.state.data.run = res.run;
                return res;
            },
        });
    }

    async payout(route) {
        const run = this.run;
        if (!run || !this.signed || this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.error = null;
        try {
            const res = await this.props.api.call("/tips/payout", { run_id: run.id, route });
            this.state.data.run = res.run;
        } catch (e) {
            this.state.error = (e && e.message) || _t("The payout was refused.");
        } finally {
            this.state.busy = false;
        }
    }
}
