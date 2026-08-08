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
    connSemantic,
    filterProducts,
    clampIndex,
} from "@mezze_bridge/cashier/order_store";
import { debugEnabled, installDebugHandle } from "@mezze_bridge/cashier/debug";
import { getCashMachineAdapter, isCashUncertain, CMS } from "@mezze_bridge/cashier/cash_machine_service";

const CUR = { symbol: "EGP", position: "before", decimals: 2 };

function store() {
    return new OrderStore({ currency: CUR });
}
const P = (id, price, available = true) => ({ id, name: "P" + id, list_price: price, available });

describe("Mezze Cashier · money helpers", () => {
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

describe("Mezze Cashier · cart state", () => {
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

describe("Mezze Cashier · S2C-2 tender helpers", () => {
    test("isSupportedMethod: every live tender mode", () => {
        expect(isSupportedMethod({ mezze_mode: "cash" })).toBe(true);
        expect(isSupportedMethod({ mezze_mode: "manual" })).toBe(true);
        expect(isSupportedMethod({ mezze_mode: "external_terminal" })).toBe(true);
        expect(isSupportedMethod({ mezze_mode: "customer_account" })).toBe(true);
        expect(isSupportedMethod({ mezze_mode: "cash_machine" })).toBe(true);
        expect(isSupportedMethod({ mezze_mode: "bank_qr" })).toBe(true);
        expect(isSupportedMethod({ mezze_mode: "nope" })).toBe(false);
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

describe("Mezze Cashier · debug handle gating (S2C-1A)", () => {
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

describe("Mezze Cashier · S2C-7 cash-machine service", () => {
    test("simulator adapter resolves only for the test provider", () => {
        expect(getCashMachineAdapter("test").pending).toBe(false);
        expect(getCashMachineAdapter("test").id).toBe("test");
    });

    test("real / unknown providers resolve to a PENDING adapter (never fakes success)", () => {
        expect(getCashMachineAdapter("glory").pending).toBe(true);
        expect(getCashMachineAdapter("").pending).toBe(true);
        expect(getCashMachineAdapter(undefined).pending).toBe(true);
    });

    test("only ERROR/UNKNOWN are uncertain (force-done eligible)", () => {
        expect(isCashUncertain(CMS.UNKNOWN)).toBe(true);
        expect(isCashUncertain(CMS.ERROR)).toBe(true);
        expect(isCashUncertain(CMS.APPROVED)).toBe(false);
        expect(isCashUncertain(CMS.CANCELLED)).toBe(false);
        expect(isCashUncertain(CMS.WAITING_CASH)).toBe(false);
        expect(isCashUncertain(CMS.COUNTING)).toBe(false);
    });
});

describe("Mezze Cashier · connectivity semantics (V2A)", () => {
    test("online -> success, offline -> danger, unknown -> neutral (UNKNOWN != OFFLINE)", () => {
        expect(connSemantic("online")).toBe("success");
        expect(connSemantic("unavailable")).toBe("danger");
        expect(connSemantic("offline")).toBe("danger");
        expect(connSemantic("unknown")).toBe("neutral");
        expect(connSemantic("checking")).toBe("neutral");
        // the invariant: an unknown signal must never render as offline/danger
        expect(connSemantic("unknown")).not.toBe(connSemantic("unavailable"));
    });
});

describe("Mezze Cashier · R1B favorites — per (branch,user) storage isolation", () => {
    const P = (id) => ({ id, name: "P" + id, list_price: 10, available: true });
    function fresh(configId, userId) {
        const s = new OrderStore({ currency: CUR, config_id: configId, user: { id: userId } });
        localStorage.removeItem(s.favKey); // start clean for the test
        return s;
    }

    test("key is scoped to branch AND user (real bootstrap ids)", () => {
        const a = new OrderStore({ config_id: 7, user: { id: 42 } });
        expect(a.favKey).toBe("mezze:favorites:v1:7:42");
        const b = new OrderStore({ config_id: 7, user: { id: 43 } });
        expect(b.favKey).not.toBe(a.favKey);          // same branch, different cashier
        const c = new OrderStore({ config_id: 8, user: { id: 42 } });
        expect(c.favKey).not.toBe(a.favKey);          // same cashier, different branch
    });

    test("cashier A and cashier B on one terminal do NOT share favorites", () => {
        const A = fresh(1, 100);
        const B = fresh(1, 200);
        A.addProduct(P(5));
        A.addProduct(P(5));
        A.addProduct(P(9));
        expect(A.favoriteIds()).toEqual([5, 9]);       // A has history
        expect(B.favoriteIds()).toEqual([]);           // B, same terminal+branch, has none
        localStorage.removeItem(A.favKey);
    });

    test("same cashier + branch keeps history across a new store (reload)", () => {
        const A1 = fresh(1, 300);
        A1.addProduct(P(3));
        const A2 = new OrderStore({ config_id: 1, user: { id: 300 } }); // reload = new store
        expect(A2.favoriteIds()).toEqual([3]);
        localStorage.removeItem(A1.favKey);
    });

    test("same cashier switching branch gets separate history", () => {
        const branch1 = fresh(1, 400);
        const branch2 = fresh(2, 400);
        branch1.addProduct(P(6));
        expect(branch1.favoriteIds()).toEqual([6]);
        expect(branch2.favoriteIds()).toEqual([]);
        localStorage.removeItem(branch1.favKey);
    });

    test("brand-new user has no favorites (opens on All)", () => {
        const neu = fresh(1, 999);
        expect(neu.favoriteIds()).toEqual([]);
    });
});

describe("Mezze Cashier · R1B exact-line remove/undo (distinct same-product lines)", () => {
    const P = (id, price) => ({ id, name: "P" + id, list_price: price || 10, available: true });
    function store() {
        return new OrderStore({ currency: CUR, config_id: 1, user: { id: 1 } });
    }

    test("same product with different context = two DISTINCT lines with distinct keys", () => {
        const s = store();
        s.addProduct(P(7), { note: "no onion" });
        s.addProduct(P(7), { note: "extra garlic" });
        expect(s.lines.length).toBe(2);
        expect(s.lines[0].key).not.toBe(s.lines[1].key);
        expect(s.lines[0].note).toBe("no onion");
        expect(s.lines[1].note).toBe("extra garlic");
        // same product + SAME note merges (qty), never a spurious new line
        s.addProduct(P(7), { note: "no onion" });
        expect(s.lines.length).toBe(2);
        expect(s.lines[0].qty).toBe(2);
    });

    test("remove operates on the EXACT line; the sibling same-product line is untouched", () => {
        const s = store();
        s.addProduct(P(7), { note: "A" });
        s.addProduct(P(7), { note: "B" });
        const first = { ...s.lines[0] };
        const second = s.lines[1];
        s.remove(second);                         // remove the 2nd line
        expect(s.lines.length).toBe(1);
        expect(s.lines[0].key).toBe(first.key);   // the FIRST line remains, untouched
        expect(s.lines[0].note).toBe("A");
    });

    test("undo restores the EXACT removed line at its original position + state", () => {
        const s = store();
        s.addProduct(P(7), { note: "A" });
        s.addProduct(P(7), { note: "B" });
        s.lines[1].qty = 3;                        // give the 2nd line a distinct qty
        const removedKey = s.lines[1].key;
        s.remove(s.lines[1]);
        expect(s.lines.length).toBe(1);
        const ok = s.undoRemove();
        expect(ok).toBe(true);
        expect(s.lines.length).toBe(2);
        expect(s.lines[1].key).toBe(removedKey);  // exact same line
        expect(s.lines[1].note).toBe("B");        // original context
        expect(s.lines[1].qty).toBe(3);           // original qty
        expect(s.state.undo).toBe(null);          // toast cleared after restore
    });

    test("repeat undo does NOT duplicate a line", () => {
        const s = store();
        s.addProduct(P(7));
        s.remove(s.lines[0]);
        expect(s.undoRemove()).toBe(true);
        expect(s.lines.length).toBe(1);
        expect(s.undoRemove()).toBe(false);       // nothing to undo now
        expect(s.lines.length).toBe(1);           // no duplicate
    });

    test("sync aggregates distinct same-product lines (payment path unchanged)", () => {
        const s = store();
        s.addProduct(P(7), { note: "A" });        // qty 1
        s.addProduct(P(7), { note: "B" });        // qty 1, distinct line
        const sync = s.toSyncLines();
        expect(sync.length).toBe(1);              // one product line for the server
        expect(sync[0]).toEqual({ product_id: 7, qty: 2 });
    });
});

describe("Mezze Cashier · R1B exact-line remove & undo (never by product id)", () => {
    const PP = (id, price = 10) => ({ id, name: "P" + id, list_price: price, available: true });
    const st = () => new OrderStore({ currency: CUR });

    test("same product, different context = two distinct lines (not merged)", () => {
        const s = st();
        s.addProduct(PP(5), { note: "no onion" });
        s.addProduct(PP(5), { note: "extra garlic" });
        expect(s.lines.length).toBe(2);
        expect(s.lines[0].note).toBe("no onion");
        expect(s.lines[1].note).toBe("extra garlic");
        expect(s.lines[0].key).not.toBe(s.lines[1].key); // distinct stable keys
        // same product + same context still merges
        s.addProduct(PP(5), { note: "no onion" });
        expect(s.lines.length).toBe(2);
        expect(s.lines[0].qty).toBe(2);
    });

    test("remove targets the EXACT line; the sibling same-product line is untouched", () => {
        const s = st();
        s.addProduct(PP(5), { note: "no onion" });     // A idx0
        s.addProduct(PP(5), { note: "extra garlic" }); // B idx1
        s.addProduct(PP(5), { note: "extra garlic" }); // B qty 2
        expect(s.lines[1].qty).toBe(2);
        s.remove(s.lines[1]);                          // remove EXACT 2nd line
        expect(s.lines.length).toBe(1);
        expect(s.lines[0].note).toBe("no onion");      // A untouched
        expect(s.lines[0].qty).toBe(1);
    });

    test("undo restores the EXACT removed line (key, qty, note, position)", () => {
        const s = st();
        s.addProduct(PP(5), { note: "no onion" });     // A idx0
        s.addProduct(PP(5), { note: "extra garlic" }); // B idx1
        s.addProduct(PP(5), { note: "extra garlic" }); // B qty 2
        const B = { ...s.lines[1] };
        s.remove(s.lines[1]);
        expect(s.lines.length).toBe(1);
        expect(s.undoRemove()).toBe(true);
        expect(s.lines.length).toBe(2);
        const restored = s.lines[1];
        expect(restored.key).toBe(B.key);              // exact same line key
        expect(restored.qty).toBe(2);                  // original qty
        expect(restored.note).toBe("extra garlic");    // original context
        expect(s.lines[0].note).toBe("no onion");      // original position preserved
    });

    test("repeat undo does not duplicate the line (idempotent)", () => {
        const s = st();
        s.addProduct(PP(5));
        s.remove(s.lines[0]);
        expect(s.undoRemove()).toBe(true);
        expect(s.lines.length).toBe(1);
        expect(s.undoRemove()).toBe(false);   // second undo is a no-op
        expect(s.lines.length).toBe(1);
    });
});

describe("Mezze Cashier · R1B keyboard — product search filter (pure)", () => {
    const CAT = [
        { id: 1, name: "Shish Tawook", list_price: 42 },
        { id: 2, name: "Hummus Beiruti", list_price: 18 },
        { id: 3, name: "Mint Lemonade", list_price: 14 },
        { id: 4, name: "Arabic Coffee", list_price: 10 },
    ];

    test("empty / whitespace query returns the list unchanged", () => {
        expect(filterProducts(CAT, "")).toHaveLength(4);
        expect(filterProducts(CAT, "   ")).toHaveLength(4);
        expect(filterProducts(CAT, null)).toHaveLength(4);
    });

    test("case-insensitive substring match on name", () => {
        expect(filterProducts(CAT, "hum").map((p) => p.id)).toEqual([2]);
        expect(filterProducts(CAT, "COFFEE").map((p) => p.id)).toEqual([4]);
        expect(filterProducts(CAT, "i").map((p) => p.id)).toEqual([1, 2, 3, 4]); // every name has an 'i'
    });

    test("no match returns an empty list; original order is preserved", () => {
        expect(filterProducts(CAT, "zzz")).toEqual([]);
        expect(filterProducts(CAT, "a").map((p) => p.id)).toEqual([1, 3, 4]); // Tawook, Lemonade, Arabic — source order
    });

    test("tolerates a null/empty catalog", () => {
        expect(filterProducts(null, "x")).toEqual([]);
        expect(filterProducts([], "x")).toEqual([]);
    });
});

describe("Mezze Cashier · R1B keyboard — highlight index clamp (pure)", () => {
    test("moves within bounds and never wraps", () => {
        expect(clampIndex(0, 4, 1)).toBe(1);
        expect(clampIndex(3, 4, 1)).toBe(3);   // clamped at the end (no wrap to 0)
        expect(clampIndex(0, 4, -1)).toBe(0);  // clamped at the start (no wrap to end)
        expect(clampIndex(2, 4, -1)).toBe(1);
    });

    test("empty list clamps to 0; non-finite index is treated as 0", () => {
        expect(clampIndex(5, 0, 1)).toBe(0);
        expect(clampIndex(NaN, 4, 1)).toBe(1);
        expect(clampIndex(undefined, 4, 0)).toBe(0);
    });

    test("a stale index above the new length is pulled back in range", () => {
        expect(clampIndex(9, 3, 0)).toBe(2); // list shrank under the highlight
    });
});
