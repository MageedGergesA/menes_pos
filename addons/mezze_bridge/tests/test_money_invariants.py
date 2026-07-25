"""P0 seed — executable enforcement of RFC-001 money invariants.

This is the first increment of running software from the Implementation Roadmap
(Program P0, task P0-E0.1-04) and the Gap Model (Vol I area #5 "Business
Invariants", Vol III risk #87 "invariants unenforced"). It converts a subset of
RFC-001's documented money invariants into *enforced, tested* guarantees.

Design decisions (board-reviewed):
  * Money is INTEGER MINOR UNITS everywhere (no float money). RFC-001 value
    object "Money"; Gap Model capability #14. Floats are used only for input
    percentages, never for stored/settled amounts.
  * Discount is applied BEFORE tax (RFC-001 invariant; Discount Engine "runs
    before Tax Engine"). Tax is computed on the discounted base.
  * Rounding is applied ONCE, at the point each amount becomes money.
  * The reference calc mirrors controllers/main.py: per-line discount %, sum of
    line bases, tax on discounted base, tip added untaxed, and split tenders
    where the LAST tender absorbs rounding drift so tenders sum EXACTLY to grand.

Runnable two ways:
  * Standalone (no Odoo needed):  python3 tests/test_money_invariants.py
  * Under Odoo's test runner via the TransactionCase wrapper at the bottom.

The reference implementation here is the CONFORMANCE ORACLE: the real product
calc (frontend pos.html + controllers/main.py) is later property-tested to match
it bit-for-bit (Roadmap P3 / Gap Model P6 tax parity). Enforcing the oracle
first means the invariants can never silently regress.
"""

import random

# --------------------------------------------------------------------------
# Reference calculation — pure, deterministic, integer minor units.
# --------------------------------------------------------------------------


def line_base_minor(unit_price_minor, qty, discount_pct):
    """One order line's base amount, in minor units, after per-line discount.

    RFC-001: line total = (unit price after discount) * qty, rounded once to
    money. Discount is a percentage in [0, 100]. Never negative.
    """
    assert isinstance(unit_price_minor, int) and unit_price_minor >= 0
    assert isinstance(qty, int) and qty >= 1
    assert 0.0 <= discount_pct <= 100.0
    after = unit_price_minor * (1.0 - discount_pct / 100.0)
    # round once, to money (minor units are already the smallest unit)
    return max(0, int(round(after))) * qty


def compute_order(lines, tax_rate_pct, order_discount_minor=0, tip_minor=0):
    """Compute an order in minor units.

    lines: list of (unit_price_minor:int, qty:int, discount_pct:float)
    Returns a dict of settled money facts. All values are ints (minor units).
    """
    line_bases = [line_base_minor(u, q, d) for (u, q, d) in lines]
    subtotal = sum(line_bases)                      # INV: total == sum of lines
    # order-level discount cannot exceed the subtotal (no negative taxable base)
    order_discount = max(0, min(int(order_discount_minor), subtotal))
    taxable = subtotal - order_discount             # INV: discount before tax
    tax = int(round(taxable * (tax_rate_pct / 100.0)))   # tax on DISCOUNTED base
    tax = max(0, tax)                               # INV: tax >= 0
    grand = taxable + tax + max(0, int(tip_minor))  # round-once already applied
    return {
        "line_bases": line_bases,
        "subtotal": subtotal,
        "order_discount": order_discount,
        "taxable": taxable,
        "tax": tax,
        "tip": max(0, int(tip_minor)),
        "grand": grand,
    }


def settle(grand_minor, tenders_minor):
    """Split settlement where the LAST tender absorbs rounding drift.

    Mirrors controllers/main.py: tenders must sum EXACTLY to grand. Returns
    (adjusted_tenders, paid, change, balance).
    """
    tenders = [max(0, int(t)) for t in tenders_minor]
    if not tenders:
        return [], 0, 0, max(0, grand_minor)
    running = sum(tenders[:-1])
    # last tender absorbs the remainder so the split is faithful to grand
    last = grand_minor - running
    tenders = tenders[:-1] + [last]
    paid = sum(tenders)
    change = max(0, paid - grand_minor)             # change only when overpaid
    balance = max(0, grand_minor - paid)            # balance only when underpaid
    return tenders, paid, change, balance


# --------------------------------------------------------------------------
# Invariants (RFC-001 / RFC-002 P1.4 "truth durable", money invariants).
# Each returns None on success or a string describing the violation.
# --------------------------------------------------------------------------


def inv_total_equals_sum_of_lines(o):
    if o["subtotal"] != sum(o["line_bases"]):
        return "subtotal != sum(line_bases)"


def inv_discount_before_tax(o, tax_rate_pct):
    # tax must equal rate applied to the DISCOUNTED base, never the pre-discount one
    expected = max(0, int(round(o["taxable"] * (tax_rate_pct / 100.0))))
    if o["tax"] != expected:
        return "tax not computed on discounted base"
    # and it must differ from taxing the pre-discount base whenever a discount exists
    pre = max(0, int(round(o["subtotal"] * (tax_rate_pct / 100.0))))
    if o["order_discount"] > 0 and tax_rate_pct > 0 and o["tax"] == pre and pre != expected:
        return "tax appears to be on pre-discount base"


def inv_no_negative_money(o):
    for k in ("subtotal", "order_discount", "taxable", "tax", "tip", "grand"):
        if o[k] < 0:
            return f"negative money in {k}"


def inv_discount_not_exceed_subtotal(o):
    if o["order_discount"] > o["subtotal"]:
        return "order discount exceeds subtotal"


def inv_grand_is_sum(o):
    if o["grand"] != o["taxable"] + o["tax"] + o["tip"]:
        return "grand != taxable + tax + tip (double rounding?)"


def inv_integer_minor_units(o):
    for k, v in o.items():
        if k == "line_bases":
            if any(not isinstance(x, int) for x in v):
                return "non-integer line base (float money leaked)"
        elif not isinstance(v, int):
            return f"non-integer money in {k}"


def inv_settlement_sums_to_grand(grand, tenders, paid, change, balance):
    if sum(tenders) != paid:
        return "paid != sum(tenders)"
    if paid >= grand and balance != 0:
        return "fully paid but balance != 0"
    if paid >= grand and change != paid - grand:
        return "change != overpayment"
    if paid < grand and change != 0:
        return "underpaid but change != 0"
    if paid < grand and balance != grand - paid:
        return "balance != underpayment"


def inv_determinism(lines, rate, disc, tip):
    a = compute_order(lines, rate, disc, tip)
    b = compute_order(lines, rate, disc, tip)
    if a != b:
        return "calc is non-deterministic"


# --------------------------------------------------------------------------
# Property test harness (seeded, deterministic — reproducible in CI).
# --------------------------------------------------------------------------


def _rand_case(rng):
    n = rng.randint(1, 8)
    lines = [(rng.randint(1, 500000), rng.randint(1, 20), rng.choice([0.0, 5.0, 10.0, 12.5, 33.3, 50.0]))
             for _ in range(n)]
    rate = rng.choice([0.0, 5.0, 14.0, 15.0, 20.0])
    subtotal_guess = sum(u * q for u, q, _ in lines)
    disc = rng.randint(0, subtotal_guess + 1000)        # sometimes exceeds subtotal on purpose
    tip = rng.randint(0, 5000)
    return lines, rate, disc, tip


def run_property_tests(iterations=20000, seed=1729):
    rng = random.Random(seed)
    failures = []
    for i in range(iterations):
        lines, rate, disc, tip = _rand_case(rng)
        o = compute_order(lines, rate, disc, tip)
        checks = [
            inv_total_equals_sum_of_lines(o),
            inv_discount_before_tax(o, rate),
            inv_no_negative_money(o),
            inv_discount_not_exceed_subtotal(o),
            inv_grand_is_sum(o),
            inv_integer_minor_units(o),
            inv_determinism(lines, rate, disc, tip),
        ]
        # settlement: random split into 1-3 tenders
        k = rng.randint(1, 3)
        raw = [rng.randint(0, o["grand"]) for _ in range(k)]
        tenders, paid, change, balance = settle(o["grand"], raw)
        checks.append(inv_settlement_sums_to_grand(o["grand"], tenders, paid, change, balance))
        for msg in checks:
            if msg:
                failures.append((i, msg, (lines, rate, disc, tip)))
                break
    return failures


# --------------------------------------------------------------------------
# Golden unit cases (documented behavior — the SAR 10% + 15% VAT example).
# --------------------------------------------------------------------------


def run_golden_cases():
    failures = []
    # 100.00 SAR item, 10% order discount, 15% VAT -> 103.50 SAR
    o = compute_order([(10000, 1, 0.0)], tax_rate_pct=15.0, order_discount_minor=1000)
    if not (o["subtotal"] == 10000 and o["taxable"] == 9000 and o["tax"] == 1350 and o["grand"] == 10350):
        failures.append(("golden_sar_10pct_15vat", o))
    # zero-rated item -> no tax
    o2 = compute_order([(2500, 2, 0.0)], tax_rate_pct=0.0)
    if not (o2["tax"] == 0 and o2["grand"] == 5000):
        failures.append(("golden_zero_rated", o2))
    # per-line 50% discount: 400 minor * 0.5 = 200, qty 3 -> 600 base
    o3 = compute_order([(400, 3, 50.0)], tax_rate_pct=0.0)
    if o3["subtotal"] != 600:
        failures.append(("golden_line_discount", o3))
    # split payment: grand 10350, tenders [5000, 5350] sum exactly
    _, paid, change, balance = settle(10350, [5000, 999999])
    if not (paid == 10350 and change == 0 and balance == 0):
        failures.append(("golden_split_absorbs_drift", (paid, change, balance)))
    return failures


if __name__ == "__main__":
    prop_failures = run_property_tests()
    golden_failures = run_golden_cases()
    total = len(prop_failures) + len(golden_failures)
    print("RFC-001 money-invariant enforcement — P0 seed")
    print(f"  property cases run : 20000")
    print(f"  property failures  : {len(prop_failures)}")
    print(f"  golden failures    : {len(golden_failures)}")
    if prop_failures[:3]:
        print("  sample:", prop_failures[:3])
    if golden_failures:
        print("  golden sample:", golden_failures[:3])
    print("RESULT:", "PASS ✓" if total == 0 else f"FAIL ✗ ({total})")
    raise SystemExit(0 if total == 0 else 1)


# --------------------------------------------------------------------------
# Odoo test-runner wrapper (so this also runs in CI under `odoo -i mezze_bridge
# --test-enable`). Skips cleanly if Odoo isn't importable (standalone mode).
# --------------------------------------------------------------------------
try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestMoneyInvariants(TransactionCase):
        def test_property_invariants(self):
            self.assertEqual(run_property_tests(iterations=5000), [],
                             "RFC-001 money invariants violated")

        def test_golden_cases(self):
            self.assertEqual(run_golden_cases(), [], "golden money cases failed")
except Exception:  # Odoo not present — standalone mode only
    pass
