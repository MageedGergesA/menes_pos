/** @odoo-module **/
// V2C — Root Kitchen Display component. Owns the board phase machine and the
// server contracts: snapshot (/kds/state) → bus poll-reconcile (/bus/poll on the
// real Odoo bus) → transition (/kds/transition). The SERVER snapshot is always
// authoritative: a reconnect re-seeds the full board (no duplicate, no stale, no
// resurrected cancellation). It NEVER fabricates tickets. Authority =
// mezze.kds.ticket. No Enterprise Preparation Display.
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { TicketCard } from "./components/ticket_card";
import {
    connSemantic, elapsedSeconds, isActive, isLate, isRtl, nextAction,
} from "./store";

const POLL_MS = 4000;      // bus poll-reconcile cadence (dropped-socket safety net)
const CONN_MS = 20000;     // local-server heartbeat
const TICK_MS = 1000;      // board clock for live timers / late (no server round-trip)

export class KdsRoot extends Component {
    static template = "mezze_bridge.KdsRoot";
    static components = { TicketCard };
    static props = {};

    setup() {
        const { boot, api, store } = this.env.mezze;
        this.api = api;
        this.store = store;
        this.boot = boot;
        this.lateMinutes = (boot && boot.late_minutes) || 15;
        this.state = useState({
            phase: "booting",          // booting|auth_required|error|board
            errorMsg: "",
            station: (boot && boot.station) || null,   // pinned station (null = all)
            stations: [],
            rows: [],                  // presented ticket rows (recomputed each tick)
            liveCount: 0,
            now: this._now(),          // board clock (ms) driving timers
            conn: "unknown",           // local-server connectivity
            busy: {},                  // ticket_id -> true while a transition is in flight
        });

        onWillStart(async () => {
            await this.boardStart();
        });
        onMounted(() => {
            this._pollTimer = window.setInterval(() => this.pollBus(), POLL_MS);
            this._connTimer = window.setInterval(() => this.pollConnectivity(), CONN_MS);
            this._tickTimer = window.setInterval(() => this.tick(), TICK_MS);
            this.pollConnectivity();
        });
        onWillUnmount(() => {
            window.clearInterval(this._pollTimer);
            window.clearInterval(this._connTimer);
            window.clearInterval(this._tickTimer);
        });
    }

    _now() {
        return Date.now();
    }

    get isRtl() {
        return isRtl(this.boot && this.boot.lang);
    }

    get branchName() {
        return (this.boot.branch && this.boot.branch.name) || "";
    }

    // ---- translated static labels -----------------------------------------
    get loadingLabel() {
        return _t("Loading the kitchen board…");
    }
    get boardTitle() {
        return _t("Kitchen");
    }
    get allStationsLabel() {
        return _t("All stations");
    }
    get liveLabel() {
        return _t("live");
    }
    get authTitle() {
        return _t("Sign in required");
    }
    get authBody() {
        return _t("Sign in with your kitchen account to open the display.");
    }
    get signInLabel() {
        return _t("Sign in");
    }
    get errorTitle() {
        return _t("Kitchen Display unavailable");
    }
    get retryLabel() {
        return _t("Try again");
    }
    get emptyTitle() {
        return _t("All caught up");
    }
    get emptyBody() {
        return _t("New kitchen tickets appear here the moment orders are fired.");
    }

    get connVariant() {
        return connSemantic(this.state.conn);
    }
    get connLabel() {
        if (this.state.conn === "online") {
            return _t("Kitchen server online");
        }
        if (this.state.conn === "unavailable" || this.state.conn === "offline") {
            return _t("Kitchen server unavailable");
        }
        return _t("Checking…");
    }

    // ---- lifecycle ---------------------------------------------------------
    async boardStart() {
        if (!this.boot || this.boot.ok === false) {
            if (this.boot && this.boot.error === "boot_missing") {
                this.state.phase = "auth_required";
            } else {
                this.state.phase = "error";
                this.state.errorMsg = this.boot && this.boot.error === "no_pos_config"
                    ? _t("Kitchen Display is not configured")
                    : _t("Authentication required");
            }
            return;
        }
        const ok = await this.seedSnapshot();
        if (ok) {
            this.state.phase = "board";
        }
    }

    /** Full authoritative snapshot (mount + every reconnect). */
    async seedSnapshot() {
        try {
            const data = await this.api.call("/kds/state", {
                config_id: this.boot.config_id,
            });
            this.store.seedSnapshot(data);
            this.refresh();
            if (this.state.phase === "error") {
                this.state.phase = "board";
                this.state.errorMsg = "";
            }
            return true;
        } catch (err) {
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
                return false;
            }
            // Only surface a hard error at first mount; a later transient failure
            // keeps the last board and is retried by the poll/heartbeat.
            if (this.state.phase === "booting") {
                this.state.phase = "error";
                this.state.errorMsg = err && err.kind === "network"
                    ? _t("Kitchen server unavailable")
                    : (err && err.message) || _t("Unable to load the kitchen board");
            }
            return false;
        }
    }

    /** Poll the REAL Odoo bus since our cursor and reconcile advisory updates. On a
     *  poll failure we mark offline; on RECOVERY we re-seed the full snapshot so any
     *  event missed while disconnected is reconciled from the authoritative server. */
    async pollBus() {
        if (this.state.phase !== "board" || !this.store.kdsChannel) {
            return;
        }
        try {
            const d = await this.api.call("/bus/poll", {
                channels: [this.store.kdsChannel, this.store.waiterChannel].filter(Boolean),
                last: this.store.busLast,
            });
            const wasOffline = this._busOffline;
            this._busOffline = false;
            if (wasOffline) {
                // reconnect → authoritative re-seed (no duplicate / stale / resurrected cancel)
                await this.seedSnapshot();
                return;
            }
            if (d && d.last) {
                this.store.busLast = d.last;
            }
            let changed = false;
            for (const n of (d && d.notifications) || []) {
                if (this.store.applyBusMessage(n && n.message)) {
                    changed = true;
                }
            }
            if (changed) {
                this.refresh();
            }
        } catch {
            this._busOffline = true;   // recovered on the next successful poll
        }
    }

    async pollConnectivity() {
        try {
            await this.api.call("/edge/status", {});
            this.state.conn = "online";
        } catch (err) {
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
                return;
            }
            this.state.conn = "unavailable";
        }
    }

    /** Board clock: advance `now` so timers/late recompute; no server round-trip. */
    tick() {
        this.state.now = this._now();
        // late transitions can change ordering emphasis; recompute derived rows cheaply
        this.recomputeDerived();
    }

    /** Recompute the presented rows + counters from the store for the pinned station. */
    refresh() {
        this.state.stations = this.store.stations();
        this.recomputeDerived();
    }

    recomputeDerived() {
        const rows = this.store.visible(this.state.station);
        this.state.rows = rows;
        this.state.liveCount = this.store.liveCount(this.state.station);
    }

    // ---- station pin -------------------------------------------------------
    selectStation(station) {
        this.state.station = station || null;
        this.recomputeDerived();
    }

    // ---- per-ticket derived (consumed by the template / passed to cards) ----
    ticketProps(ticket) {
        const secs = elapsedSeconds(ticket.fired_at, this.state.now);
        return {
            ticket,
            elapsed: secs,
            late: isActive(ticket.state) && isLate(secs, this.lateMinutes),
            busy: !!this.state.busy[ticket.id],
        };
    }

    // ---- transitions (backend is authoritative) ----------------------------
    async onAdvance(ticket) {
        const na = nextAction(ticket.state);
        if (!na) {
            return;
        }
        await this._transition(ticket, na.action);
    }

    async onRecall(ticket) {
        await this._transition(ticket, "recall");
    }

    async _transition(ticket, action) {
        if (this.state.busy[ticket.id]) {
            return;
        }
        this.state.busy = { ...this.state.busy, [ticket.id]: true };
        try {
            const res = await this.api.call("/kds/transition", {
                ticket_id: ticket.id,
                action,
            });
            // The server returns the AUTHORITATIVE ticket payload — upsert it, so a
            // second screen that lost the race converges to the real state (a no-op
            // transition just returns changed=false and the same terminal state).
            if (res && res.ticket) {
                this.store.upsert(res.ticket);
                this.refresh();
            }
        } catch (err) {
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
                return;
            }
            // A lost race / stale bump reconciles from the server snapshot rather
            // than trusting the local view.
            await this.seedSnapshot();
        } finally {
            const busy = { ...this.state.busy };
            delete busy[ticket.id];
            this.state.busy = busy;
        }
    }

    retry() {
        this.state.errorMsg = "";
        this.state.phase = "booting";
        this.boardStart();
    }
}
