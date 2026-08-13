/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/** Turn the working order into a delivery.
 *
 *  A delivery is not "an order with a flag" — it needs a person, a phone, an
 *  address, a zone, and a fee, and the branch decides whether it will even take it.
 *  All of that is SERVER-authoritative: /delivery/availability answers eligible /
 *  fee / minimum / ETA / allowed payment for a given zone and subtotal, and this
 *  form only supplies the inputs and shows the answer. It never computes a fee,
 *  never overrides a minimum, and never assumes the branch is open — the till is
 *  not allowed to promise something the kitchen has not agreed to.
 */
export class DeliveryForm extends Component {
    static template = "mezze_bridge.DeliveryForm";
    static props = {
        api: Object,
        configId: { type: [Number, { value: null }], optional: true },
        subtotal: Number,
        currency: Object,
        customer: { type: [Object, { value: null }], optional: true },
        onCreate: Function,     // ({ zoneId, fee, customer, phone, address, note }) => …
        onCancel: Function,
    };

    setup() {
        this.state = useState({
            zones: [],
            zoneId: null,
            customer: (this.props.customer && this.props.customer.name) || "",
            phone: (this.props.customer && this.props.customer.phone) || "",
            address: "",
            note: "",
            avail: null,        // server verdict for the chosen zone
            loading: true,
            checking: false,
            busy: false,
            error: "",
        });
        onWillStart(() => this.loadZones());
    }

    async loadZones() {
        try {
            const r = await this.props.api.call("/delivery/zones", { config_id: this.props.configId });
            const zones = (r && r.zones || []).filter((z) => z.active !== false);
            Object.assign(this.state, { zones, loading: false });
            if (zones.length === 1) {
                await this.pickZone(zones[0].id);
            }
        } catch (e) {
            Object.assign(this.state, { loading: false, error: this.zonesFailedLabel });
        }
    }

    async pickZone(zoneId) {
        this.state.zoneId = zoneId ? parseInt(zoneId, 10) : null;
        this.state.avail = null;
        if (!this.state.zoneId) {
            return;
        }
        this.state.checking = true;
        try {
            this.state.avail = await this.props.api.call("/delivery/availability", {
                config_id: this.props.configId,
                zone_id: this.state.zoneId,
                subtotal: this.props.subtotal,
            });
        } catch (e) {
            this.state.error = this.availFailedLabel;
        } finally {
            this.state.checking = false;
        }
    }

    set(field, value) {
        this.state[field] = value;
        this.state.error = "";
    }

    get zone() {
        return this.state.zones.find((z) => z.id === this.state.zoneId) || null;
    }

    /** The server's verdict, in the cashier's words. Never softened: if the branch
     *  will not take the order, the button stays off and the reason is shown. */
    get verdict() {
        const a = this.state.avail;
        if (!a) {
            return null;
        }
        if (a.eligible) {
            return { ok: true, fee: a.fee, eta: a.eta_minutes, min: a.min_order };
        }
        // The server explains itself in fields, not just a code: `below_minimum`
        // comes with `remaining`, which is the number the cashier actually needs —
        // "add 40 more" is actionable, "not available" is not.
        if (a.below_minimum) {
            return { ok: false, why: _t("Add %s more to reach this zone’s %s minimum.",
                                        this.fmt(a.remaining || 0), this.fmt(a.min_order || 0)) };
        }
        const why = {
            out_of_zone: _t("That address is outside the delivery area."),
            closed: _t("The branch is closed for delivery right now."),
        };
        return { ok: false,
                 why: why[a.reason] || _t("This zone does not accept that payment method.") };
    }

    fmt(amount) {
        const c = this.props.currency || {};
        const n = (amount || 0).toFixed(c.decimals ?? 2);
        return (c.position === "before") ? `${c.symbol || ""} ${n}` : `${n} ${c.symbol || ""}`;
    }

    get canCreate() {
        const v = this.verdict;
        return !!(v && v.ok) && !!this.state.address.trim() && !!this.state.phone.trim()
            && !this.state.busy;
    }

    async create() {
        if (!this.canCreate) {
            return;
        }
        this.state.busy = true;
        this.state.error = "";
        try {
            await this.props.onCreate({
                zoneId: this.state.zoneId,
                fee: this.verdict.fee,
                customer: this.state.customer.trim(),
                phone: this.state.phone.trim(),
                address: this.state.address.trim(),
                note: this.state.note.trim(),
            });
        } catch (e) {
            this.state.error = (e && e.message) || this.createFailedLabel;
        } finally {
            this.state.busy = false;
        }
    }

    // ---- labels ----
    get title() {
        return _t("Delivery");
    }

    get zoneLabel() {
        return _t("Zone");
    }

    get chooseZoneLabel() {
        return _t("Choose a zone");
    }

    get nameLabel() {
        return _t("Name");
    }

    get phoneLabel() {
        return _t("Phone");
    }

    get addressLabel() {
        return _t("Address");
    }

    get noteLabel() {
        return _t("Note for the driver");
    }

    get createLabel() {
        return _t("Create delivery");
    }

    get cancelLabel() {
        return _t("Cancel");
    }

    get loadingLabel() {
        return _t("Loading…");
    }

    get checkingLabel() {
        return _t("Checking…");
    }

    get noZonesLabel() {
        return _t("This branch has no delivery zones set up.");
    }

    get zonesFailedLabel() {
        return _t("Could not load the delivery zones.");
    }

    get availFailedLabel() {
        return _t("Could not check delivery availability.");
    }

    get createFailedLabel() {
        return _t("Could not create the delivery.");
    }

    feeLine(v) {
        return _t("Fee %s · about %s min", this.fmt(v.fee), v.eta || "—");
    }
}
