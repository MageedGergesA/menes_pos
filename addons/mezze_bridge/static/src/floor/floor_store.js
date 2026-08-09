/** @odoo-module **/
// R2A — reactive Floor state + PURE helpers (exported for HOOT tests). The server
// (/mezze/api/v1/floors) is the single source of table truth; this holds only view
// state and derives display values. No table/order FSM lives here — the Floor reads
// state and hands off to the Register / existing manager-approval flow.
import { reactive } from "@odoo/owl";

/** Money formatting mirrors the cashier's contract (symbol + position) so amounts
 *  read identically across the Register and the Floor. LTR-isolated in the CSS. */
export function formatMoney(amount, currency) {
    const dp = currency && Number.isInteger(currency.decimals) ? currency.decimals : 2;
    const sym = (currency && currency.symbol) || "";
    const n = (Number(amount) || 0).toLocaleString("en-US", {
        minimumFractionDigits: dp, maximumFractionDigits: dp,
    });
    if (!sym) {
        return n;
    }
    return (currency.position === "before") ? `${sym} ${n}` : `${n} ${sym}`;
}

/** Elapsed minutes -> compact dwell label: 38′, 1h 04′. Uses a prime mark so it
 *  never collides with a translated "min". Non-negative, integer. */
export function formatElapsed(minutes) {
    const m = Math.max(0, Math.round(Number(minutes) || 0));
    if (m < 60) {
        return m + "′";
    }
    const h = Math.floor(m / 60);
    const r = m % 60;
    return h + "h " + String(r).padStart(2, "0") + "′";
}

/** Canonical, NEVER color-only mapping for a table's operational state. Each state
 *  carries a text label, a canonical .mz-status variant (for the chip), and a shape
 *  treatment (ring / solid / dashed) so the state is legible without relying on hue.
 *  Only states the /floors endpoint actually returns are mapped; unknown -> available. */
export function tableStateMeta(status) {
    const MAP = {
        available: { label: "Open", variant: "success", fill: "ring" },
        occupied: { label: "Occupied", variant: "info", fill: "solid" },
        reserved: { label: "Reserved", variant: "violet", fill: "dashed" },
        bill: { label: "Bill", variant: "warn", fill: "solid" },
    };
    return MAP[status] || MAP.available;
}

/** Whether a table is actively serving guests (drives occupancy/covers stats). */
export function isServing(status) {
    return status === "occupied" || status === "bill";
}

/** Header stats for a floor: occupied/total, total covers (guests), average dwell
 *  over the SERVING tables only. Pure — derived from the tables array. */
export function floorStats(tables) {
    const list = tables || [];
    const total = list.length;
    const serving = list.filter((t) => isServing(t.status));
    const covers = list.reduce((s, t) => s + (t.guests || 0), 0);
    const dwellers = serving.filter((t) => (t.minutes || 0) > 0);
    const avgDwell = dwellers.length
        ? Math.round(dwellers.reduce((s, t) => s + t.minutes, 0) / dwellers.length)
        : 0;
    return { total, occupied: serving.length, covers, avgDwell };
}

/** V2A connectivity signal -> canonical .mz-status variant (shared contract with the
 *  cashier/KDS: UNKNOWN is neutral, never danger). */
export function connSemantic(state) {
    if (state === "online") {
        return "success";
    }
    if (state === "unavailable" || state === "offline") {
        return "danger";
    }
    return "neutral";
}

export class FloorStore {
    constructor(boot) {
        this.currency = (boot && boot.currency) || { symbol: "", position: "after", decimals: 2 };
        this.state = reactive({
            phase: "booting", // booting | ready | auth_required | error
            errorMsg: "",
            floors: [], // [{ id, name, tables: [...] }]
            activeFloorId: null,
            conn: "unknown",
        });
    }

    /** The floor currently shown (active tab), or the first available. */
    get activeFloor() {
        const f = this.state.floors;
        if (!f.length) {
            return null;
        }
        return f.find((x) => x.id === this.state.activeFloorId) || f[0];
    }

    setFloors(floors) {
        this.state.floors = floors || [];
        if (!this.state.activeFloorId && this.state.floors.length) {
            this.state.activeFloorId = this.state.floors[0].id;
        }
    }

    selectFloor(id) {
        this.state.activeFloorId = id;
    }
}
