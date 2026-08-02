/** @odoo-module **/
// S2C-1 — frontend unit tests for the pure cashier logic. The server remains the
// financial authority; these cover the UX-side helpers and cart state machine.
import { describe, expect, test } from "@odoo/hoot";
import {
    OrderStore,
    changeFor,
    computeChange,
    formatMoney,
    isSupportedMethod,
    quickCashOptions,
    recordedAmount,
    roundTo,
    tenderFields,
} from "@mezze_bridge/cashier/order_store";
import { debugEnabled, installDebugHandle } from "@mezze_bridge/cashier/debug";

const CUR = { symbol: "EGP", position: "before", decimals: 2 };

function store() {
    return new OrderStore({ currency: CUR });
}
const P = (id, price, available = true) => ({ id, name: "P" + id, list_price: price, available });

describe("money helpers", () => {
    test("formatMoney places symbol per currency position", () => {
        expect(formatMoney(920, CUR)).toBe("EGP 920.00");
        expect(formatMoney(920, { symbol: "ج.م", position: "after", decimals: 2 })).toBe("920.00 ج.م");
    });

    test("computeChange: exact, over, short, invalid", () => {
        expect(computeChange(920, 1000)).toBe(80);
        expect(computeChange(920, 920)).toBe(0);
        expect(computeChange(920, 500)).toBe(0); // never negative
        expect(computeChange(920, "abc")).toBe(0);
    });

    test("roundTo avoids float dust", () => {
        expect(roundTo(0.1 + 0.2, 2)).toBe(0.3);
    });

    test("quickCashOptions returns exact + round-ups, adapts to amount", () => {
        const opts = quickCashOptions(920, 2);
        expect(opts[0]).toBe(920); // exact first
        expect(opts).toInclude(1000);
        expect(opts.every((v) => v >= 920)).toBe(true);
    });
});

describe("cart state", () => {
    test("addProduct creates a line then increments qty", () => {
        const s = store();
        s.addProduct(P(1, 100));
        expect(s.lines.length).toBe(1);
        expect(s.lines[0].qty).toBe(1);
        s.addProduct(P(1, 100));
        expect(s.lines.length).toBe(1);
        expect(s.lines[0].qty).toBe(2);
        expect(s.count).toBe(2);
    });

    test("unavailable product cannot be added", () => {
        const s = store();
        const ok = s.addProduct(P(9, 50, false));
        expect(ok).toBe(false);
        expect(s.isEmpty).toBe(true);
    });

    test("inc / dec / remove and estimated total", () => {
        const s = store();
        s.addProduct(P(1, 100));
        s.addProduct(P(2, 250));
        s.inc(s.lines[0]); // P1 qty 2
        expect(s.estimatedTotal).toBe(450);
        s.dec(s.lines[0]); // P1 qty 1
        expect(s.estimatedTotal).toBe(350);
        s.dec(s.lines[1]); // P2 qty 0 -> removed
        expect(s.lines.length).toBe(1);
        s.remove(s.lines[0]);
        expect(s.isEmpty).toBe(true);
    });

    test("toSyncLines carries only product_id + qty (server recomputes money)", () => {
        const s = store();
        s.addProduct(P(1, 100));
        s.addProduct(P(1, 100));
        expect(s.toSyncLines()).toEqual([{ product_id: 1, qty: 2 }]);
    });

    test("clear empties the cart", () => {
        const s = store();
        s.addProduct(P(1, 100));
        s.clear();
        expect(s.isEmpty).toBe(true);
    });
});

describe("S2C-2 tender helpers", () => {
    test("isSupportedMethod: cash/manual/external only", () => {
        expect(isSupportedMethod({ mezze_mode: "cash" })).toBe(true);
        expect(isSupportedMethod({ mezze_mode: "manual" })).toBe(true);
        expect(isSupportedMethod({ mezze_mode: "external_terminal" })).toBe(true);
        expect(isSupportedMethod({ mezze_mode: "customer_account" })).toBe(false);
        expect(isSupportedMethod({ mezze_mode: "bank_qr" })).toBe(false);
        expect(isSupportedMethod(null)).toBe(false);
    });

    test("recordedAmount never exceeds the balance; changeFor is the excess", () => {
        // partial tender below balance
        expect(recordedAmount(300, 1000)).toBe(300);
        expect(changeFor(300, 1000)).toBe(0);
        // completing tender with change (cash)
        expect(recordedAmount(350, 323.58)).toBe(323.58);
        expect(changeFor(350, 323.58)).toBe(26.42);
        // exact
        expect(recordedAmount(200, 200)).toBe(200);
        expect(changeFor(200, 200)).toBe(0);
        // invalid / zero
        expect(recordedAmount(0, 100)).toBe(0);
        expect(recordedAmount("x", 100)).toBe(0);
    });

    test("tenderFields is policy-driven per method", () => {
        const card = tenderFields({
            mezze_mode: "external_terminal", device_policy: "required", reference_policy: "optional",
        });
        expect(card.external).toBe(true);
        expect(card.devicePolicy).toBe("required");
        expect(card.referencePolicy).toBe("optional");
        expect(card.showApproval).toBe(true);
        const wallet = tenderFields({
            mezze_mode: "manual", device_policy: "disabled", reference_policy: "required",
        });
        expect(wallet.external).toBe(false);
        expect(wallet.devicePolicy).toBe("disabled");
        expect(wallet.referencePolicy).toBe("required");
        expect(wallet.showApproval).toBe(false);
        const cash = tenderFields({ mezze_mode: "cash" });
        expect(cash.cash).toBe(true);
    });
});

describe("debug handle gating (S2C-1A)", () => {
    test("debugEnabled: empty=off, any non-empty string=on", () => {
        expect(debugEnabled("")).toBe(false);
        expect(debugEnabled(undefined)).toBe(false);
        expect(debugEnabled("1")).toBe(true);
        expect(debugEnabled("assets")).toBe(true);
        expect(debugEnabled("tests")).toBe(true);
    });

    test("installDebugHandle exposes only in debug and removes stale global", () => {
        delete window.__mezzeCashier;
        installDebugHandle({ debug: "" }, { marker: "a" });
        expect(window.__mezzeCashier).toBe(undefined); // normal mode -> absent
        installDebugHandle({ debug: "1" }, { marker: "b" });
        expect(window.__mezzeCashier).toEqual({ marker: "b" }); // debug -> present
        installDebugHandle({ debug: "assets" }, { marker: "c" });
        expect(window.__mezzeCashier).toEqual({ marker: "c" }); // assets -> present
        installDebugHandle({ debug: "" }, { marker: "d" });
        expect(window.__mezzeCashier).toBe(undefined); // return to normal -> deleted
    });
});
