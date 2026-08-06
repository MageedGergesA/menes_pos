/** @odoo-module **/
// V2C — frontend unit tests for the PURE Kitchen Display logic. mezze.kds.ticket is
// the server authority; these cover the presentation/reconcile helpers only (no E2E).
import { describe, expect, test } from "@odoo/hoot";
import {
    KdsStore,
    channelLabel,
    elapsedSeconds,
    formatTimer,
    isActive,
    isAddition,
    isCancelled,
    isLate,
    isRtl,
    isTerminal,
    nextAction,
    sortTickets,
    stateLabel,
    stateSemantic,
    ticketIdentity,
} from "@mezze_bridge/kds/store";

const T = (o) => Object.assign(
    { id: 1, state: "fired", station: "Kitchen", course: 1, fired_at: null, items: [] }, o);

describe("Mezze KDS · state → canonical semantic", () => {
    test("each state maps to its canonical .mz-status variant", () => {
        expect(stateSemantic("fired")).toBe("info");
        expect(stateSemantic("accepted")).toBe("warn");
        expect(stateSemantic("preparing")).toBe("accent");
        expect(stateSemantic("ready")).toBe("ok");
        expect(stateSemantic("served")).toBe("neutral");
        expect(stateSemantic("cancel")).toBe("danger");
        expect(stateSemantic("nonsense")).toBe("neutral"); // default-safe
    });
    test("state label falls back to the raw state", () => {
        expect(stateLabel("preparing")).toBe("Preparing");
        expect(stateLabel("cancel")).toBe("Cancelled");
    });
});

describe("Mezze KDS · allowed next action (FSM)", () => {
    test("only the one forward transition is offered", () => {
        expect(nextAction("fired").action).toBe("accept");
        expect(nextAction("accepted").action).toBe("preparing");
        expect(nextAction("preparing").action).toBe("ready");
        expect(nextAction("ready").action).toBe("served");
    });
    test("terminal states expose no next action", () => {
        expect(nextAction("served")).toBe(null);
        expect(nextAction("cancel")).toBe(null);
    });
    test("active vs terminal", () => {
        expect(isActive("preparing")).toBe(true);
        expect(isActive("served")).toBe(false);
        expect(isActive("cancel")).toBe(false);
        expect(isTerminal("served")).toBe(true);
        expect(isCancelled("cancel")).toBe(true);
    });
});

describe("Mezze KDS · timer formatting (tabular)", () => {
    test("MM:SS under 100 minutes, never wrapping at 60", () => {
        expect(formatTimer(0)).toBe("00:00");
        expect(formatTimer(65)).toBe("01:05");
        expect(formatTimer(12 * 60 + 48)).toBe("12:48");
        expect(formatTimer(72 * 60 + 15)).toBe("72:15"); // lateness unmistakable
    });
    test("H:MM:SS beyond 100 minutes", () => {
        expect(formatTimer(100 * 60 + 30)).toBe("1:40:30");
    });
    test("elapsedSeconds parses server UTC datetime deterministically", () => {
        const fired = "2026-08-06 10:00:00";
        const now = Date.parse("2026-08-06T10:12:48Z");
        expect(elapsedSeconds(fired, now)).toBe(12 * 60 + 48);
        // never negative (clock skew / future stamp)
        expect(elapsedSeconds(fired, Date.parse("2026-08-06T09:59:00Z"))).toBe(0);
        expect(elapsedSeconds(null, now)).toBe(0);
    });
});

describe("Mezze KDS · late is a CONDITION, not a state", () => {
    test("late iff elapsed >= threshold minutes", () => {
        expect(isLate(14 * 60, 15)).toBe(false);
        expect(isLate(15 * 60, 15)).toBe(true);
        expect(isLate(20 * 60, 15)).toBe(true);
        // a preparing ticket can be late — state is unchanged, late is layered on top
        expect(isActive("preparing")).toBe(true);
    });
});

describe("Mezze KDS · channel badge (real channels only)", () => {
    test("known channels map to labels; unknown → Counter", () => {
        expect(channelLabel("dine_in")).toBe("Dine-in");
        expect(channelLabel("delivery")).toBe("Delivery");
        expect(channelLabel("aggregator")).toBe("Aggregator");
        expect(channelLabel("qr")).toBe("QR");
        expect(channelLabel("weird")).toBe("Counter");
    });
});

describe("Mezze KDS · addition marker", () => {
    test("course > 1 is an addition/subsequent fire", () => {
        expect(isAddition(T({ course: 1 }))).toBe(false);
        expect(isAddition(T({ course: 2 }))).toBe(true);
        expect(isAddition(T({ course: 3 }))).toBe(true);
    });
});

describe("Mezze KDS · identity (dine-in table vs order ref)", () => {
    test("table wins for dine-in; otherwise the order/tracking ref", () => {
        expect(ticketIdentity(T({ table: "T6" }))).toEqual({ kind: "table", value: "T6" });
        expect(ticketIdentity(T({ table: null, tracking: "A-12" }))).toEqual({ kind: "ref", value: "A-12" });
    });
});

describe("Mezze KDS · RTL-safe", () => {
    test("ar mirrors; others do not", () => {
        expect(isRtl("ar_001")).toBe(true);
        expect(isRtl("ar")).toBe(true);
        expect(isRtl("en_US")).toBe(false);
        expect(isRtl(null)).toBe(false);
    });
});

describe("Mezze KDS · board sort (FIFO)", () => {
    test("oldest fire first, stable by id", () => {
        const rows = sortTickets([
            T({ id: 3, fired_at: "2026-08-06 10:05:00" }),
            T({ id: 1, fired_at: "2026-08-06 10:01:00" }),
            T({ id: 2, fired_at: "2026-08-06 10:01:00" }),
        ]);
        expect(rows.map((r) => r.id)).toEqual([1, 2, 3]);
    });
});

describe("Mezze KDS · KdsStore reconcile — server authoritative + idempotent", () => {
    test("seedSnapshot replaces the board and seeds the cursor", () => {
        const s = new KdsStore();
        s.seedSnapshot({
            tickets: [T({ id: 1 }), T({ id: 2, station: "Bar" })],
            last_bus_id: 42, kds_channel: "mezze_kds_7", waiter_channel: "mezze_waiter_7",
        });
        expect(s.all().length).toBe(2);
        expect(s.busLast).toBe(42);
        expect(s.kdsChannel).toBe("mezze_kds_7");
        expect(s.stations()).toEqual(["Bar", "Kitchen"]);
    });

    test("bus update upserts by id — same event twice = ONE ticket (exactly once)", () => {
        const s = new KdsStore();
        s.seedSnapshot({ tickets: [] });
        const body = T({ id: 9, state: "fired", course: 2 });
        s.applyBusMessage({ type: "mezze_kds_update", payload: body });
        s.applyBusMessage({ type: "mezze_kds_update", payload: body }); // duplicate delivery
        expect(s.all().length).toBe(1);
        expect(s.all()[0].id).toBe(9);
    });

    test("a cancellation update is shown in place, never silently removed", () => {
        const s = new KdsStore();
        s.seedSnapshot({ tickets: [T({ id: 5, state: "preparing" })] });
        s.applyBusMessage({ type: "mezze_kds_update", payload: T({ id: 5, state: "cancel" }) });
        const row = s.all().find((t) => t.id === 5);
        expect(row.state).toBe("cancel");        // still present
        expect(s.visible().some((t) => t.id === 5)).toBe(true); // still on the board
    });

    test("reconnect re-seed drops stale + never resurrects an aged-out cancel", () => {
        const s = new KdsStore();
        s.seedSnapshot({ tickets: [T({ id: 1 }), T({ id: 2, state: "cancel" })] });
        // server aged out the cancelled ticket → fresh authoritative snapshot omits it
        s.seedSnapshot({ tickets: [T({ id: 1, state: "preparing" })] });
        expect(s.all().map((t) => t.id)).toEqual([1]);
        expect(s.all()[0].state).toBe("preparing");
    });

    test("liveCount ignores terminal tickets and respects station filter", () => {
        const s = new KdsStore();
        s.seedSnapshot({ tickets: [
            T({ id: 1, state: "fired", station: "Kitchen" }),
            T({ id: 2, state: "served", station: "Kitchen" }),
            T({ id: 3, state: "ready", station: "Bar" }),
        ] });
        expect(s.liveCount()).toBe(2);            // fired + ready (served excluded)
        expect(s.liveCount("Kitchen")).toBe(1);
        expect(s.visible("Bar").length).toBe(1);
    });

    test("non-KDS or malformed bus messages are ignored", () => {
        const s = new KdsStore();
        s.seedSnapshot({ tickets: [] });
        expect(s.applyBusMessage({ type: "mezze_waiter_ready", payload: { id: 1 } })).toBe(false);
        expect(s.applyBusMessage(null)).toBe(false);
        expect(s.applyBusMessage({ type: "mezze_kds_update", payload: {} })).toBe(false);
        expect(s.all().length).toBe(0);
    });
});
