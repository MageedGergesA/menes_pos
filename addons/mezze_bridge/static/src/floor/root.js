/** @odoo-module **/
// R2A — Floor / Tables root component. Renders the REAL configured floors + tables
// from /mezze/api/v1/floors (native restaurant.floor/table geometry + live state).
// It NEVER falls back to demo data: an auth/network/empty result resolves to an
// explicit state. Table/order lifecycle stays server-authoritative; the Floor reads
// state and (later checkpoints) hands off to the Register + manager-approval flow.
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { WorkspaceRail } from "../shell/rail";
import { icon } from "../shell/icons";
import { loadAppearance } from "../shell/appearance";
import {
    formatMoney, formatElapsed, tableStateMeta, floorStats, connSemantic,
} from "./floor_store";

export class FloorRoot extends Component {
    static components = { WorkspaceRail };
    static template = "mezze_bridge.FloorRoot";
    static props = {};

    setup() {
        const { boot, api, floor } = this.env.mezze;
        this.api = api;
        this.boot = boot;
        this.floor = floor;
        this.currency = floor.currency;
        this.state = useState(floor.state);

        onWillStart(async () => {
            // same appearance contract as the Register — one setting, every surface
            await loadAppearance(this.api);
            await this.bootstrap();
        });
        onMounted(() => {
            this.pollConnectivity();
            this._connTimer = window.setInterval(() => this.pollConnectivity(), 20000);
            // Live floor: gently refresh occupancy so the host sees new opens/seatings
            // without a manual reload. Read-only; never mutates state.
            this._floorTimer = window.setInterval(() => this.refreshFloors(), 30000);
        });
        onWillUnmount(() => {
            window.clearInterval(this._connTimer);
            window.clearInterval(this._floorTimer);
        });
    }

    // ---- boot / data --------------------------------------------------------
    async bootstrap() {
        if (!this.boot || this.boot.ok === false) {
            if (this.boot && this.boot.error === "boot_missing") {
                this.state.phase = "auth_required";
            } else {
                this.state.phase = "error";
                this.state.errorMsg = this.boot && this.boot.error === "no_pos_config"
                    ? _t("POS is not ready for service") : _t("Authentication required");
            }
            return;
        }
        this.state.phase = "booting";
        try {
            const data = await this.api.call("/floors", { config_id: this.boot.config_id });
            this.floor.setFloors(data.floors || []);
            this.state.phase = "ready";
        } catch (err) {
            if (err && err.kind === "auth") {
                this.state.phase = "auth_required";
                return;
            }
            this.state.phase = "error";
            this.state.errorMsg = err && err.kind === "network"
                ? _t("Local Mezze server unavailable") : (err && err.message) || _t("Unable to load the floor");
        }
    }

    async refreshFloors() {
        if (this.state.phase !== "ready") {
            return;
        }
        try {
            const data = await this.api.call("/floors", { config_id: this.boot.config_id });
            this.floor.setFloors(data.floors || []);
        } catch {
            // a transient refresh failure must not disrupt the live floor view
        }
    }

    async pollConnectivity() {
        try {
            await this.api.call("/edge/status", {});
            this.state.conn = "online";
        } catch {
            this.state.conn = "unavailable";
        }
    }

    // ---- display helpers ----------------------------------------------------
    fmt(amount) {
        return formatMoney(amount, this.currency);
    }
    elapsed(minutes) {
        return formatElapsed(minutes);
    }
    stateMeta(status) {
        return tableStateMeta(status);
    }

    get configId() {
        return this.boot.config_id || null;
    }

    /** Branch initial for the rail's logo tile — same source as the Register's. */
    get railMark() {
        return String(this.branchName || "M").trim().charAt(0).toUpperCase() || "M";
    }

    get branchName() {
        return (this.boot.branch && this.boot.branch.name) || "";
    }
    get userName() {
        return (this.boot.user && this.boot.user.name) || "";
    }
    get connVariant() {
        return connSemantic(this.state.conn);
    }
    get connLabel() {
        if (this.state.conn === "online") {
            return _t("Local server online");
        }
        if (this.state.conn === "unavailable") {
            return _t("Local server unavailable");
        }
        return _t("Checking…");
    }
    get registerUrl() {
        const cfg = this.boot.config_id ? `?config_id=${this.boot.config_id}` : "";
        return "/mezze/pos" + cfg;
    }
    // F3 — the Floor exposes the SAME workspace destinations as the Register, so the
    // nav is stable between staff workspaces. Orders/Reservations are phases of the
    // Register app, reached with a ?view= deep link (navigation only — the Register
    // still boots exactly as it does today and no order/business state is touched).
    _registerView(view) {
        const sep = this.boot.config_id ? "&" : "?";
        return this.registerUrl + sep + "view=" + view;
    }
    get ordersUrl() {
        return this._registerView("orders");
    }
    get reservationsUrl() {
        return this._registerView("reservations");
    }

    get floors() {
        return this.state.floors;
    }
    get activeFloor() {
        return this.floor.activeFloor;
    }
    get tables() {
        const f = this.activeFloor;
        return (f && f.tables) || [];
    }
    get stats() {
        return floorStats(this.tables);
    }
    get isEmpty() {
        return this.state.phase === "ready" && !this.floors.length;
    }

    // Absolute-position style for a table from its real geometry (native
    // restaurant.table position_h/v + width/height, in the floor's pixel space).
    tableStyle(t) {
        const round = t.shape === "round";
        return (
            `left:${t.x || 0}px;top:${t.y || 0}px;` +
            `width:${Math.max(t.w || 60, 60)}px;height:${Math.max(t.h || 60, 60)}px;` +
            `border-radius:${round ? "50%" : "var(--mz-radius-lg, 14px)"};`
        );
    }

    // Seat dots laid around the table perimeter (visual capacity cue, like the design
    // reference). Capped so a very large table stays legible.
    seatDots(t) {
        const n = Math.max(0, Math.min(Number(t.seats) || 0, 12));
        return Array.from({ length: n }, (_, i) => i);
    }
    seatDotStyle(t, i, total) {
        const angle = (360 / Math.max(total, 1)) * i - 90;
        const rad = (angle * Math.PI) / 180;
        // place dots just outside the table box, centered
        const rx = 50 + 48 * Math.cos(rad);
        const ry = 50 + 48 * Math.sin(rad);
        return `left:${rx}%;top:${ry}%;`;
    }

    // ---- labels (all translated; the Arabic till reads this screen too) -----
    get floorTitle() {
        return _t("Floor");
    }

    get floorGlyph() {
        return icon("table_restaurant");
    }

    get canvasHint() {
        return _t("Tap a table to see it");
    }

    get zoomHint() {
        return _t("Drag to move the plan");
    }

    get zoomGroupLabel() {
        return _t("Zoom");
    }

    get zoomInLabel() {
        return _t("Zoom in");
    }

    get zoomOutLabel() {
        return _t("Zoom out");
    }

    get zoomFitLabel() {
        return _t("Fit the plan");
    }

    get zonesLabel() {
        return _t("Zones");
    }

    get tableDetailLabel() {
        return _t("Table detail");
    }

    get noTablesHint() {
        return _t("No tables configured on this zone.");
    }

    get closeLabel() {
        return _t("Clear selection");
    }

    get noSelectionHint() {
        return _t("Tap a table to see who is on it and what it has run up.");
    }

    /* ── Canvas: pan and zoom ─────────────────────────────────────────────────
       The design's canvas is pannable by drag and zooms 0.7–1.4 in 0.1 steps, with
       a zoom readout that doubles as zoom-to-fit. It is NOT a scroll region: a floor
       plan is a map, and a scrollbar on a map hides the part you are not looking at
       instead of letting you take it in.

       Zoom is clamped rather than free. Below 0.7 the table numbers stop being
       readable and the plan becomes decoration; above 1.4 a dining room no longer
       fits the panel, which is the one thing this screen exists to show. */
    static ZOOM_MIN = 0.7;
    static ZOOM_MAX = 1.4;
    static ZOOM_STEP = 0.1;

    get zoom() {
        return this.state.zoom || 1;
    }

    get zoomPct() {
        return Math.round(this.zoom * 100) + "%";
    }

    get canvasTransform() {
        const p = this.state.pan || { x: 0, y: 0 };
        // translate BEFORE scale so a drag moves the plan by the distance the finger
        // moved, not by that distance multiplied by the zoom.
        return `transform:translate(${p.x}px, ${p.y}px) scale(${this.zoom});`;
    }

    zoomIn() {
        this.state.zoom = Math.min(FloorRoot.ZOOM_MAX,
                                   Number((this.zoom + FloorRoot.ZOOM_STEP).toFixed(2)));
    }

    zoomOut() {
        this.state.zoom = Math.max(FloorRoot.ZOOM_MIN,
                                   Number((this.zoom - FloorRoot.ZOOM_STEP).toFixed(2)));
    }

    /** Back to 1:1 AND back to the origin. Zoom-to-fit that left the plan panned off
     *  screen would be a button that appears to do nothing. */
    zoomFit() {
        this.state.zoom = 1;
        this.state.pan = { x: 0, y: 0 };
    }

    onCanvasDown(ev) {
        // Only a drag on empty canvas pans. Starting a pan from a table would make
        // every mis-swipe on a token move the room instead of opening the check.
        if (ev.target.closest(".mz-tbl")) {
            return;
        }
        this._panFrom = { x: ev.clientX, y: ev.clientY,
                          pan: { ...(this.state.pan || { x: 0, y: 0 }) } };
        this.state.panning = true;
    }

    onCanvasMove(ev) {
        if (!this._panFrom) {
            return;
        }
        this.state.pan = {
            x: this._panFrom.pan.x + (ev.clientX - this._panFrom.x),
            y: this._panFrom.pan.y + (ev.clientY - this._panFrom.y),
        };
    }

    onCanvasUp() {
        this._panFrom = null;
        this.state.panning = false;
    }

    /* ── Legend, with the counts the design puts on it ───────────────────────
       A legend that only names the colours tells a host what the map means. One
       that counts them tells them what the room is doing, which is the question
       they actually walked over to answer. */
    get legend() {
        const rows = [
            { key: "available", label: _t("Available") },
            { key: "occupied", label: _t("Occupied") },
            { key: "bill", label: _t("Bill requested") },
            { key: "reserved", label: _t("Reserved") },
        ];
        const tables = this.tables;
        return rows.map((r) => Object.assign({}, r, {
            count: tables.filter((t) => t.status === r.key).length,
        }));
    }

    /** "Terrace 4" — the zone tab carries how many of its tables are free, because
     *  choosing which room to walk to is the decision this tab strip supports. */
    freeCount(floorId) {
        const fl = (this.floors || []).find((f) => f.id === floorId);
        return ((fl && fl.tables) || []).filter((t) => t.status === "available").length;
    }

    /* ── The selection card ───────────────────────────────────────────────────
       The design gives the side panel a 320px card describing the selected table:
       its number and state, then key/value detail rows, then the verbs that act on
       it. Ours had no side panel at all — tapping a table either jumped straight to
       the Register or did nothing, so a host could not look at a table without
       either committing to it or learning nothing. */
    get selectedTable() {
        const id = this.state.selectedTableId;
        return id ? (this.tables.find((t) => t.id === id) || null) : null;
    }

    /** Only the rows this table actually has. A card padded out with "—" reads as
     *  broken; a shorter card reads as a quiet table. */
    get selectionRows() {
        const t = this.selectedTable;
        if (!t) {
            return [];
        }
        const rows = [];
        rows.push({ k: _t("Seats"), v: String(t.seats || 0) });
        if (t.guests) {
            rows.push({ k: _t("Covers"), v: String(t.guests) });
        }
        if (t.minutes) {
            rows.push({ k: _t("Seated"), v: formatElapsed(t.minutes) });
        }
        if (t.server) {
            rows.push({ k: _t("Server"), v: t.server });
        }
        if (t.total) {
            rows.push({ k: _t("Running total"), v: this.fmt(t.total), money: true });
        }
        if (t.reservation && t.reservation.who) {
            rows.push({ k: _t("Booked"), v: t.reservation.who });
            if (t.reservation.time) {
                rows.push({ k: _t("For"), v: t.reservation.time });
            }
        }
        return rows;
    }

    /** The verbs, and only the ones this table's state can honour. A greyed row of
     *  four buttons on an empty table is four things a host has to read and reject. */
    get selectionActions() {
        const t = this.selectedTable;
        if (!t) {
            return [];
        }
        const out = [];
        if (t.status === "available") {
            out.push({ key: "seat", label: _t("Seat guests"), primary: true,
                       run: () => this.openRegister(t) });
        } else if (t.status === "occupied" || t.status === "bill") {
            out.push({ key: "open", label: _t("Open order"), primary: true,
                       run: () => this.openRegister(t) });
        } else if (t.status === "reserved") {
            out.push({ key: "seat", label: _t("Seat the booking"), primary: true,
                       run: () => this.openRegister(t) });
        }
        return out;
    }

    get selectionStateLabel() {
        const t = this.selectedTable;
        return t ? tableStateMeta(t.status).label : "";
    }

    /** "4 seats · Terrace" — what the card says under the number. */
    get selectionMeta() {
        const t = this.selectedTable;
        if (!t) {
            return "";
        }
        const bits = [_t("%s seats", t.seats || 0)];
        const fl = this.activeFloor;
        if (fl && fl.name) {
            bits.push(fl.name);
        }
        return bits.join(" · ");
    }

    clearSelection() {
        this.state.selectedTableId = null;
    }

    openRegister(t) {
        const cfg = this.boot.config_id ? `config_id=${this.boot.config_id}&` : "";
        window.location.assign(`/mezze/pos?${cfg}table_id=${t.id}`);
    }

    /* ── The table token ──────────────────────────────────────────────────────
       The design's token is a wood-tone top with seat marks around it and a small
       centred info card on top: table number, a seat RATIO, an optional status
       strip, and the server and spend when there is a check. Ours printed the
       number and a loose meta line, so "is this table full?" — the question the
       map is read for — had to be inferred from the dots. */

    /** "2/4" — covers against capacity. The design leads with this because a host
     *  scanning for somewhere to put a party of three is comparing exactly it. */
    seatRatio(t) {
        return `${t.guests || 0}/${t.seats || 0}`;
    }

    /** The strip only appears when the table is saying something.
     *
     *  It reuses the STATE vocabulary rather than inventing shouty twins of it.
     *  The first version wrote "BILL" and "RESERVED", which collided with two
     *  existing terms: "BILL" is already the printed receipt's heading (a different
     *  concept sharing a spelling), and "RESERVED" duplicated "Reserved". One term
     *  per concept is the glossary contract; the strip truncates by design, so
     *  length was never a reason to coin a second word. */
    statusStrip(t) {
        if (t.status === "reserved") {
            return (t.reservation && t.reservation.time) || tableStateMeta(t.status).label;
        }
        if (t.status === "bill") {
            return tableStateMeta(t.status).label;
        }
        if (t.mezze_fired) {
            return _t("Fired");
        }
        return "";
    }

    /** Initials, not the full name: the chip is 8.5px on a 60px card, and a server's
     *  name at that size is a smudge. */
    serverInitials(t) {
        return String(t.server || "")
            .split(/\s+/).filter(Boolean).slice(0, 2)
            .map((w) => w[0].toUpperCase()).join("");
    }

    // ---- interactions (CP1: selection only; Register hand-off is CP5) --------
    onSelectFloor(id) {
        this.floor.selectFloor(id);
    }
    // CP5 — tap opens the table-bound Register (available = start, occupied = resume the
    // authoritative order). RESERVED requires a check-in/seat action (reservation FSM),
    // which is a LATER checkpoint, so it does NOT open the Register here — we just select
    // it and surface its booking. Server stays authoritative for which order a table holds.
    /** A tap SELECTS. It used to navigate straight to the Register for any
     *  serviceable table, which meant a host could not look at a table without
     *  leaving the floor: checking who was on 12 and how long they had been there
     *  cost a round trip through the till and back. The design routes it through the
     *  side panel — the verbs are there, one tap further, and they are named. */
    onTapTable(t) {
        this.state.selectedTableId = this.state.selectedTableId === t.id ? null : t.id;
    }
    retry() {
        this.state.errorMsg = "";
        this.bootstrap();
    }
}
