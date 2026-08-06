/** @odoo-module **/
// V2C — one Kitchen Display ticket card. Presents a mezze.kds.ticket payload with the
// kitchen information hierarchy: timer/urgency → identity (table/order) → course →
// items → modifiers → state → next action. Channel is secondary metadata. Cancelled
// work is shown explicitly (never silently removed); late is an explicit condition,
// not a colour. All dynamic labels go through Odoo _t (real translation, incl. ar_001).
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import {
    channelLabel, formatTimer, isAddition, isCancelled, isServed,
    nextAction, stateLabel, stateSemantic, ticketIdentity,
} from "../store";

export class TicketCard extends Component {
    static template = "mezze_bridge.KdsTicketCard";
    static props = {
        ticket: Object,
        elapsed: Number,
        late: Boolean,
        busy: Boolean,
        onAdvance: Function,
        onRecall: Function,
    };

    // ---- translated label maps (literal _t so they are extracted/translated) ----
    get statusLabel() {
        const map = {
            fired: _t("Fired"),
            accepted: _t("Accepted"),
            preparing: _t("Preparing"),
            ready: _t("Ready"),
            served: _t("Served"),
            cancel: _t("Cancelled"),
        };
        return map[this.ticket.state] || stateLabel(this.ticket.state);
    }

    get statusVariant() {
        return stateSemantic(this.ticket.state);
    }

    get channel() {
        const map = {
            dine_in: _t("Dine-in"),
            counter: _t("Counter"),
            pos: _t("Counter"),
            qr: _t("QR"),
            pickup: _t("Pickup"),
            delivery: _t("Delivery"),
            drivethru: _t("Drive-thru"),
            aggregator: _t("Aggregator"),
            kiosk: _t("Kiosk"),
        };
        return map[this.ticket.channel] || channelLabel(this.ticket.channel);
    }

    get identity() {
        const id = ticketIdentity(this.ticket);
        if (id.kind === "table") {
            return _t("Table %s", id.value);
        }
        return id.value ? _t("Order %s", id.value) : _t("Counter");
    }

    get nextLabel() {
        const na = nextAction(this.ticket.state);
        if (!na) {
            return "";
        }
        const map = {
            accept: _t("Accept"),
            preparing: _t("Start prep"),
            ready: _t("Ready"),
            served: _t("Served"),
        };
        return map[na.action] || na.label;
    }

    get hasNext() {
        return !!nextAction(this.ticket.state);
    }

    // compound booleans kept in JS (Owl template idiom: single identifiers only)
    get showLate() {
        return this.props.late && !this.isCancelled && !this.isServed;
    }
    get showActions() {
        return this.hasNext || this.canRecall;
    }

    get isAddition() {
        return isAddition(this.ticket);
    }

    get isCancelled() {
        return isCancelled(this.ticket.state);
    }

    get isServed() {
        return isServed(this.ticket.state);
    }

    get courseLabel() {
        const c = Number(this.ticket.course) || 1;
        return c > 1 ? _t("Course %s", c) : "";
    }

    // explicit, non-colour text markers (spec §12/§13/§19)
    get addedText() {
        return _t("ADDED");
    }
    get cancelledText() {
        return _t("CANCELLED — do not make");
    }
    get lateText() {
        return _t("LATE");
    }
    get recallLabel() {
        return _t("Recall one step");
    }

    get timer() {
        return formatTimer(this.elapsed);
    }

    get elapsed() {
        return this.props.elapsed;
    }

    get late() {
        return this.props.late;
    }

    get busy() {
        return this.props.busy;
    }

    get ticket() {
        return this.props.ticket;
    }

    get items() {
        return this.ticket.items || [];
    }

    // recall is offered on any non-fired live ticket (kitchen mis-bump correction)
    get canRecall() {
        const s = this.ticket.state;
        return s !== "fired" && s !== "served" && s !== "cancel";
    }

    onAdvanceClick() {
        if (!this.busy) {
            this.props.onAdvance(this.ticket);
        }
    }

    onRecallClick() {
        if (!this.busy) {
            this.props.onRecall(this.ticket);
        }
    }
}
