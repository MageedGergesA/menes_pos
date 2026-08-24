/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMoney } from "../order_store";

/** Odoo's "Enter Code" — one box for any code a guest hands over.
 *
 *  Mezze had a full loyalty back end (`/loyalty/*`, `/giftcard/*`, `/promo/*`) and
 *  the register reached none of it. This is the entry point.
 *
 *  The screen deliberately does NOT ask what kind of code it is. A slip does not say
 *  whether it is a gift card, a coupon or a promo code, and making the cashier choose
 *  turns a two-second interaction into a question they cannot answer in front of the
 *  guest. `/codes/resolve` classifies it server-side and answers with the kind.
 *
 *  A gift card is REMEMBERED, not spent. It is a tender: it settles at payment,
 *  against the balance that exists then. Spending it here would take the money before
 *  the sale exists.
 */
export class EnterCodeScreen extends Component {
    static template = "mezze_bridge.EnterCodeScreen";
    static props = {
        api: Object,
        orderUuid: { type: [String, { value: null }], optional: true },
        partnerId: { type: [Number, { value: null }], optional: true },
        sessionId: { type: [Number, { value: null }], optional: true },
        currency: { type: Object, optional: true },
        onApplied: Function,      // a promo landed — the order totals moved
        onGiftCard: Function,     // a card was recognised — hold it for payment
        onClose: Function,
    };

    setup() {
        this.state = useState({
            code: "",
            busy: false,
            error: "",
            result: null,
            // rewards for the attached customer
            points: 0,
            rewards: [],
            rewardsLoading: false,
            rewardsError: "",
        });
        onWillStart(() => this.loadRewards());
    }

    /** What this guest can actually take, and — for anything they cannot — why.
     *
     *  A greyed-out reward with no explanation is how a cashier ends up telling a
     *  guest "the system won't let me". The endpoint already names every refusal;
     *  this turns each name into a sentence.
     */
    async loadRewards() {
        if (!this.props.partnerId) {
            return;
        }
        this.state.rewardsLoading = true;
        this.state.rewardsError = "";
        try {
            const r = await this.props.api.call("/loyalty/rewards", {
                partner_id: this.props.partnerId,
                order_uuid: this.props.orderUuid,
                session_id: this.props.sessionId,
            });
            if (r && r.ok && r.available) {
                this.state.points = r.points || 0;
                this.state.rewards = r.rewards || [];
            } else {
                this.state.rewards = [];
            }
        } catch (e) {
            this.state.rewardsError = _t("Could not read this customer's rewards.");
        }
        this.state.rewardsLoading = false;
    }

    async takeReward(reward) {
        if (!reward.claimable || this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.rewardsError = "";
        try {
            const r = await this.props.api.call("/loyalty/apply", {
                partner_id: this.props.partnerId,
                reward_id: reward.id,
                order_uuid: this.props.orderUuid,
                session_id: this.props.sessionId,
            });
            if (r && r.ok) {
                // The order moved and so did the balance; re-read both rather than
                // subtracting locally.
                await this.props.onApplied(r);
                await this.loadRewards();
            } else {
                this.state.rewardsError = (r && r.message)
                    || _t("That reward could not be applied.");
            }
        } catch (err) {
            this.state.rewardsError = this.explain(err);
        } finally {
            this.state.busy = false;
        }
    }

    /** The server's refusal names, as sentences. */
    whyNot(reward) {
        const known = {
            no_card: _t("This customer has no loyalty card yet."),
            not_enough_points: _t("Not enough points yet."),
            nothing_to_discount: _t("There is nothing left to discount on this order."),
            already_applied: _t("Already on this order."),
            no_eligible_product: _t("Nothing on this order qualifies."),
        };
        return known[reward.reason] || "";
    }

    get hasRewards() {
        return !!(this.props.partnerId && this.state.rewards.length);
    }

    get pointsLine() {
        return _t("%s points", this.state.points);
    }

    fmt(v) {
        return formatMoney(v, this.props.currency);
    }

    setCode(value) {
        // Typed EXACTLY as printed. An earlier version upper-cased this on the theory
        // that codes are printed in capitals — but Odoo mints gift-card codes as
        // lowercase hex ("0440-eeb7-4d65"), and the lookup is an exact match, so the
        // convenience silently made every auto-generated card unrecognisable. Caught
        // by driving the real screen; no unit test would have seen it.
        this.state.code = value || "";
        this.state.error = "";
    }

    get canSubmit() {
        return !!this.state.code.trim() && !this.state.busy;
    }

    async submit() {
        if (!this.canSubmit) {
            return;
        }
        this.state.busy = true;
        this.state.error = "";
        this.state.result = null;
        try {
            const r = await this.props.api.call("/codes/resolve", {
                code: this.state.code.trim(),
                order_uuid: this.props.orderUuid,
                session_id: this.props.sessionId,
            });
            this.state.result = r;
            if (r.kind === "gift_card") {
                if (!r.usable) {
                    this.state.error = r.expired
                        ? _t("That gift card has expired.")
                        : _t("That gift card has no balance left.");
                    this.state.result = null;
                } else {
                    this.props.onGiftCard({ code: r.code, balance: r.balance });
                }
            } else if (r.kind === "promo") {
                this.props.onApplied(r);
            }
        } catch (err) {
            this.state.error = this.explain(err);
        } finally {
            this.state.busy = false;
        }
    }

    /** A cashier is owed a sentence. The server already distinguishes "no such code"
     *  from "this code exists but cannot be used", so both are repeated as given
     *  rather than flattened into one apology. */
    explain(err) {
        const data = (err && err.data) || err || {};
        if (data.error === "unknown_code") {
            return _t("That code is not a gift card, a coupon or a promotion.");
        }
        if (data.error === "code_rejected") {
            return data.message || _t("That code cannot be used on this order.");
        }
        if (data.error === "empty_code") {
            return _t("Type a code first.");
        }
        return data.message || err.message
            || _t("That code could not be checked.");
    }

    get giftLine() {
        const r = this.state.result;
        return r && r.kind === "gift_card"
            ? _t("Gift card accepted — %s available", this.fmt(r.balance))
            : "";
    }

    get promoLine() {
        const r = this.state.result;
        return r && r.kind === "promo"
            ? _t("%s applied — %s off", r.name, this.fmt(r.discount))
            : "";
    }

    // ---- labels ----
    get title() { return _t("Enter Code"); }
    get hint() {
        return _t("A gift card, a coupon or a promotion — the code says which.");
    }
    get fieldLabel() { return _t("Code"); }
    get submitLabel() {
        return this.state.busy ? _t("Checking…") : _t("Apply");
    }
    get closeLabel() { return _t("Done"); }
    get rewardsTitle() { return _t("Rewards"); }
    get noCustomerLine() {
        return _t("Attach a customer to see their rewards.");
    }
}
