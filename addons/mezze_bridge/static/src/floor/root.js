/** @odoo-module **/
// R2A — Floor / Tables root component. Renders the REAL configured floors + tables
// from /mezze/api/v1/floors (native restaurant.floor/table geometry + live state).
// It NEVER falls back to demo data: an auth/network/empty result resolves to an
// explicit state. Table/order lifecycle stays server-authoritative; the Floor reads
// state and (later checkpoints) hands off to the Register + manager-approval flow.
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import {
    formatMoney, formatElapsed, tableStateMeta, floorStats, connSemantic,
} from "./floor_store";

export class FloorRoot extends Component {
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

    // ---- interactions (CP1: selection only; Register hand-off is CP5) --------
    onSelectFloor(id) {
        this.floor.selectFloor(id);
    }
    // CP5 — tap opens the table-bound Register (available = start, occupied = resume the
    // authoritative order). RESERVED requires a check-in/seat action (reservation FSM),
    // which is a LATER checkpoint, so it does NOT open the Register here — we just select
    // it and surface its booking. Server stays authoritative for which order a table holds.
    onTapTable(t) {
        if (t.status === "occupied" || t.status === "bill" || t.status === "available") {
            const cfg = this.boot.config_id ? `config_id=${this.boot.config_id}&` : "";
            window.location.assign(`/mezze/pos?${cfg}table_id=${t.id}`);
            return;
        }
        // reserved (or any non-serviceable state): select + show booking, no Register jump
        this.state.selectedTableId = this.state.selectedTableId === t.id ? null : t.id;
    }
    retry() {
        this.state.errorMsg = "";
        this.bootstrap();
    }
}
