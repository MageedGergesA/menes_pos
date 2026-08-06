/** @odoo-module **/
// V2C — PURE Kitchen Display logic (no Owl, no DOM, no I/O). The single place that
// interprets a mezze.kds.ticket payload for the board: state→semantic, allowed next
// action, elapsed/late timing, channel + course/addition markers, and the
// snapshot/bus RECONCILE (server-authoritative, idempotent by ticket id). Kept pure
// so HOOT can test it deterministically. mezze.kds.ticket is the authority — this
// never invents state; it only presents what the server sends.

// Forward-only kitchen life-cycle (mirrors models/kds_ticket.py FLOW). Index = order.
export const FLOW = ["fired", "accepted", "preparing", "ready", "served"];

// state -> canonical .mz-status semantic variant (DESIGN-P3B.3 authority mapping:
// fired=info, accepted=warn, preparing=accent, ready=ok, served=neutral, cancel=danger).
// NO per-state colours are invented; these are the shared component variants.
export const STATE_SEMANTIC = {
    fired: "info",
    accepted: "warn",
    preparing: "accent",
    ready: "ok",
    served: "neutral",
    cancel: "danger",
};

// English SOURCE labels (translated at the call site through Odoo _t).
export const STATE_LABEL = {
    fired: "Fired",
    accepted: "Accepted",
    preparing: "Preparing",
    ready: "Ready",
    served: "Served",
    cancel: "Cancelled",
};

// The ONE valid next transition for a live ticket (backend still validates).
// action = the /kds/transition action; label = English source (translated later).
export const NEXT_ACTION = {
    fired: { action: "accept", label: "Accept" },
    accepted: { action: "preparing", label: "Start prep" },
    preparing: { action: "ready", label: "Ready" },
    ready: { action: "served", label: "Served" },
};

// channel code (pos.order.mezze_channel or derived) -> English source label.
export const CHANNEL_LABEL = {
    dine_in: "Dine-in",
    counter: "Counter",
    pos: "Counter",
    qr: "QR",
    pickup: "Pickup",
    delivery: "Delivery",
    drivethru: "Drive-thru",
    aggregator: "Aggregator",
    kiosk: "Kiosk",
};

export function stateSemantic(state) {
    return STATE_SEMANTIC[state] || "neutral";
}

export function stateLabel(state) {
    return STATE_LABEL[state] || String(state || "");
}

export function nextAction(state) {
    return NEXT_ACTION[state] || null;
}

export function isCancelled(state) {
    return state === "cancel";
}

export function isServed(state) {
    return state === "served";
}

export function isTerminal(state) {
    return state === "served" || state === "cancel";
}

/** A ticket is "live" (kitchen still owns it) when it is neither served nor cancelled. */
export function isActive(state) {
    return FLOW.includes(state) && state !== "served";
}

export function channelLabel(channel) {
    return CHANNEL_LABEL[channel] || "Counter";
}

/** A later fire (course > 1) — a subsequent course OR an à-la-carte addition. Mezze's
 *  domain models both identically (both are later fires with an incrementing course),
 *  so the board surfaces both as "added after the first fire"; it invents no distinction
 *  the domain does not carry. */
export function isAddition(ticket) {
    return Number(ticket && ticket.course) > 1;
}

/** Primary scannable identity: dine-in → the table; otherwise the order/customer ref
 *  (tracking). Returns {kind, value} so the template can render + label per channel. */
export function ticketIdentity(ticket) {
    const t = ticket || {};
    if (t.table) {
        return { kind: "table", value: String(t.table) };
    }
    return { kind: "ref", value: String(t.tracking || t.order_id || "") };
}

// ---- timing (late is a CONDITION layered on state, never a workflow state) --------

/** Parse the server datetime "YYYY-MM-DD HH:MM:SS" (UTC) to epoch ms. */
export function parseServerDt(s) {
    if (!s) {
        return null;
    }
    const ms = Date.parse(String(s).replace(" ", "T") + "Z");
    return Number.isNaN(ms) ? null : ms;
}

/** Whole seconds elapsed since fired_at, clamped at 0. nowMs is injected (testable). */
export function elapsedSeconds(firedAt, nowMs) {
    const start = parseServerDt(firedAt);
    if (start == null) {
        return 0;
    }
    return Math.max(0, Math.floor((nowMs - start) / 1000));
}

/** Monospaced board timer. < 100 min → "MM:SS"; beyond → "H:MM:SS". Minutes are NOT
 *  wrapped at 60 (a 72-minute ticket reads "72:15"), so lateness is unmistakable. */
export function formatTimer(seconds) {
    const s = Math.max(0, Math.floor(seconds || 0));
    const mm = Math.floor(s / 60);
    const ss = s % 60;
    const p = (n) => String(n).padStart(2, "0");
    if (mm < 100) {
        return p(mm) + ":" + p(ss);
    }
    const h = Math.floor(mm / 60);
    return h + ":" + p(mm % 60) + ":" + p(ss);
}

/** Late = elapsed at/above the configured threshold (minutes). A timing condition only. */
export function isLate(seconds, lateMinutes) {
    const thr = Math.max(1, Number(lateMinutes) || 15) * 60;
    return Math.floor(seconds || 0) >= thr;
}

/** Connectivity state → canonical .mz-status semantic (UNKNOWN is neutral, not danger).
 *  Mirrors the cashier's helper so the KDS bundle stays self-contained. */
export function connSemantic(state) {
    if (state === "online") {
        return "success";
    }
    if (state === "unavailable" || state === "offline") {
        return "danger";
    }
    return "neutral"; // "unknown" / "checking" — explicitly not danger
}

/** RTL-safe: which languages mirror the layout. Numerics/timers stay LTR regardless. */
export function isRtl(lang) {
    return typeof lang === "string" && lang.slice(0, 2).toLowerCase() === "ar";
}

/** Board sort: oldest fire first (FIFO), stable by id. Returns a new array. */
export function sortTickets(tickets) {
    return (tickets || []).slice().sort((a, b) => {
        const fa = a.fired_at || "";
        const fb = b.fired_at || "";
        if (fa !== fb) {
            return fa < fb ? -1 : 1;
        }
        return (a.id || 0) - (b.id || 0);
    });
}

// ---- the board reconcile: server-authoritative, idempotent by ticket id -----------

export class KdsStore {
    constructor() {
        this.byId = new Map();      // id -> ticket payload (latest wins)
        this.busLast = 0;
        this.kdsChannel = null;
        this.waiterChannel = null;
    }

    /** Full authoritative snapshot (mount / reconnect). REPLACES the board so a
     *  reconnect drops stale tickets, never duplicates, never resurrects a cancel
     *  the server has aged out. */
    seedSnapshot(data) {
        this.byId = new Map();
        for (const t of (data && data.tickets) || []) {
            if (t && t.id != null) {
                this.byId.set(t.id, t);
            }
        }
        this.busLast = (data && data.last_bus_id) || 0;
        this.kdsChannel = (data && data.kds_channel) || null;
        this.waiterChannel = (data && data.waiter_channel) || null;
    }

    /** Apply one bus notification. A mezze_kds_update carries a full ticket payload;
     *  UPSERT by id ⇒ delivering the same event twice yields ONE ticket (idempotent),
     *  and a cancellation update sets state='cancel' in place (never a silent removal). */
    applyBusMessage(message) {
        if (!message) {
            return false;
        }
        const type = message.type || (message.payload && message.payload.type);
        const body = message.payload || message.body;
        if (type === "mezze_kds_update" && body && body.id != null) {
            this.byId.set(body.id, body);
            return true;
        }
        return false;
    }

    /** Upsert a single ticket payload (used by the fire/transition round-trip result). */
    upsert(ticket) {
        if (ticket && ticket.id != null) {
            this.byId.set(ticket.id, ticket);
            return true;
        }
        return false;
    }

    all() {
        return sortTickets(Array.from(this.byId.values()));
    }

    /** Board rows: sorted; live tickets always shown; cancelled/served kept visible
     *  (the server only returns recently-cleared ones) so the kitchen SEES a cancel.
     *  Optional station pin filters the display without hiding the data model. */
    visible(station) {
        let rows = this.all();
        if (station) {
            rows = rows.filter((t) => t.station === station);
        }
        return rows;
    }

    /** Distinct station labels currently on the board (for the station picker). */
    stations() {
        const set = new Set();
        for (const t of this.byId.values()) {
            if (t.station) {
                set.add(t.station);
            }
        }
        return Array.from(set).sort();
    }

    /** Count of live (kitchen-owned) tickets, optionally for one station. */
    liveCount(station) {
        let n = 0;
        for (const t of this.byId.values()) {
            if (!isActive(t.state)) {
                continue;
            }
            if (station && t.station !== station) {
                continue;
            }
            n += 1;
        }
        return n;
    }
}
