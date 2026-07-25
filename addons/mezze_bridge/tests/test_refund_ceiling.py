"""Tests for the canonical refund ceiling (domain/refund.py).

Standalone:  python3 tests/test_refund_ceiling.py
Under Odoo:  TransactionCase wrapper at the bottom.

Proves the pure invariant in integer minor units: total successful refunds never
exceed the paid amount; failed/rolled-back refunds do not consume capacity;
rounding cannot create or destroy more than one minor unit; client input cannot
override server truth (the function only sees server-derived minor-unit values).
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from domain import refund as R  # noqa: E402

# --- sequential unit matrix (paid=1000 minor = 10.00 @ 2dp) --------------------
UNIT = [
    # (requested, paid, already) -> expected ok
    (1000, 1000, 0, True),    # full refund exactly equal to refundable
    (400, 1000, 0, True),     # partial below refundable
    (600, 1000, 400, True),   # second partial using the remaining amount exactly
    (601, 1000, 400, False),  # one minor unit above remaining -> reject
    (0, 1000, 0, False),      # zero refund
    (-100, 1000, 0, False),   # negative refund
    (1, 1000, 1000, False),   # already fully refunded -> 1 over -> reject
    (500, 1000, 600, False),  # would exceed (600+500>1000)
    (100, 1000, 1100, False), # historical over-refund (negative refundable) -> reject
]


def t_unit_matrix():
    fails = []
    for req, paid, already, expected in UNIT:
        v = R.check_refund(req, paid, already)
        if v.ok != expected:
            fails.append((req, paid, already, "expected", expected, "got", v))
    return fails


def t_malformed_fails_closed():
    fails = []
    for bad in ("10", 10.5, None, [10]):
        v = R.check_refund(bad, 1000, 0)  # non-int requested must be rejected
        if v.ok:
            fails.append(("malformed accepted", bad))
    # to_minor rejects malformed amounts
    try:
        R.to_minor("abc", 2)
        fails.append(("to_minor accepted garbage",))
    except ValueError:
        pass
    return fails


def t_precision_exact():
    # partial refunds must sum exactly in minor units (no float drift)
    fails = []
    paid = R.to_minor(10.00, 2)              # 1000
    a = R.to_minor(3.33, 2); b = R.to_minor(3.33, 2); c = R.to_minor(3.34, 2)
    if a + b + c != paid:
        fails.append(("3.33+3.33+3.34 != 10.00 in minor units", a, b, c))
    # a client can't exploit sub-minor precision: 10.001 rounds to 1000, not 1001
    if R.to_minor(10.001, 2) != 1000:
        fails.append(("sub-minor precision exploit", R.to_minor(10.001, 2)))
    return fails


def _simulate(paid, requests):
    """Apply requests in order; only successful ones consume capacity
    (rejected/rolled-back do not). Returns committed total."""
    already = 0
    for req in requests:
        v = R.check_refund(req, paid, already)
        if v.ok:
            already += req
    return already


def t_property_never_exceeds():
    """Generated sequences: committed total never exceeds paid; never negative."""
    rng = random.Random(20260723)
    fails = []
    for _ in range(20000):
        paid = rng.randint(0, 100000)
        reqs = [rng.randint(-500, paid + 500) for _ in range(rng.randint(0, 8))]
        committed = _simulate(paid, reqs)
        if committed > paid:
            fails.append(("exceeded", paid, reqs, committed))
            break
        if committed < 0:
            fails.append(("negative", paid, reqs, committed))
            break
    return fails


def t_property_failed_do_not_consume():
    """A rejected request must not change remaining capacity for the next one."""
    rng = random.Random(99)
    fails = []
    for _ in range(5000):
        paid = rng.randint(1, 10000)
        already = rng.randint(0, paid)
        over = (paid - already) + rng.randint(1, 100)     # guaranteed to exceed
        # a rejected over-request, then a valid remaining request, must both behave
        v1 = R.check_refund(over, paid, already)
        remaining = paid - already
        v2 = R.check_refund(remaining, paid, already) if remaining > 0 else R.check_refund(1, paid, paid)
        if v1.ok:
            fails.append(("over accepted", paid, already, over))
        if remaining > 0 and not v2.ok:
            fails.append(("valid-remaining rejected after a failed attempt", paid, already))
    return fails


def t_quantity_unit_matrix():
    """Per-line quantity ceiling (integer units)."""
    cases = [
        (1, 1, 0, True),    # refund 1 of sold 1
        (1, 1, 1, False),   # already refunded 1 of 1 -> exceeds
        (2, 1, 0, False),   # 2 of 1 -> exceeds
        (3, 5, 2, True),    # 3 of remaining (5-2)=3 -> ok exact
        (4, 5, 2, False),   # 4 of remaining 3 -> exceeds
        (0, 5, 0, False),   # zero -> invalid
        (-1, 5, 0, False),  # negative -> invalid
    ]
    fails = []
    for req, sold, already, expected in cases:
        v = R.check_line_quantity(req, sold, already)
        if v.ok != expected:
            fails.append((req, sold, already, "exp", expected, "got", v))
    return fails


def t_quantity_property():
    """Generated: committed refunded quantity never exceeds sold; failed don't consume."""
    rng = random.Random(7)
    fails = []
    for _ in range(20000):
        sold = rng.randint(0, 1000)
        already = 0
        for _ in range(rng.randint(0, 6)):
            req = rng.randint(-100, sold + 100)
            v = R.check_line_quantity(req, sold, already)
            if v.ok:
                already += req
        if already > sold or already < 0:
            fails.append((sold, already))
            break
    return fails


def t_qty_precision():
    # 1.5 units at 3-digit precision = 1500 units; no float drift
    return [] if R.qty_to_units(1.5, 3) == 1500 and R.qty_to_units(0.001, 3) == 1 else [("qty precision",)]


def t_aggregate_blocks_different_uuids():
    """Different 'uuids' (modelled as separate requests) cannot jointly exceed."""
    paid = 1000
    # two full refunds: the second must be rejected by the accumulated aggregate
    already = 0
    v1 = R.check_refund(1000, paid, already); already += 1000 if v1.ok else 0
    v2 = R.check_refund(1000, paid, already)
    return [] if (v1.ok and not v2.ok) else [("aggregate bypass", v1, v2)]


ALL = [
    ("unit_matrix", t_unit_matrix),
    ("malformed_fails_closed", t_malformed_fails_closed),
    ("precision_exact", t_precision_exact),
    ("property_never_exceeds", t_property_never_exceeds),
    ("property_failed_do_not_consume", t_property_failed_do_not_consume),
    ("aggregate_blocks_different_uuids", t_aggregate_blocks_different_uuids),
    ("quantity_unit_matrix", t_quantity_unit_matrix),
    ("quantity_property", t_quantity_property),
    ("qty_precision", t_qty_precision),
]


# ------------------------------ mutation tests ------------------------------
def run_mutations():
    results = {}
    real = R.check_refund

    def mutant(name, fn):
        R.check_refund = fn
        try:
            caught = bool(t_unit_matrix() or t_property_never_exceeds() or
                          t_aggregate_blocks_different_uuids())
        finally:
            R.check_refund = real
        results[name] = caught

    # ceiling removed (always ok)
    mutant("ceiling_removed", lambda req, paid, already: R.Verdict(True, "ok", paid - already))
    # already-refunded ignored (refundable = paid)
    mutant("already_ignored", lambda req, paid, already:
           R.Verdict(0 < req <= paid, "ok", paid))
    # comparison <= changed to < (rejects exact full refund -> unit_matrix catches)
    mutant("le_changed_to_lt", lambda req, paid, already:
           R.Verdict(0 < req < (paid - already), "ok", paid - already))
    # negative accepted
    mutant("negative_accepted", lambda req, paid, already:
           R.Verdict(req <= (paid - already), "ok", paid - already))
    # client value trusted (requested treated as refundable)
    mutant("client_trusted", lambda req, paid, already: R.Verdict(True, "ok", req))

    # --- quantity-path mutations ---
    real_q = R.check_line_quantity

    def qmutant(name, fn):
        R.check_line_quantity = fn
        try:
            caught = bool(t_quantity_unit_matrix() or t_quantity_property())
        finally:
            R.check_line_quantity = real_q
        results[name] = caught

    qmutant("qty_ceiling_removed", lambda req, sold, already: R.QVerdict(True, "ok", sold - already))
    qmutant("prior_qty_ignored", lambda req, sold, already: R.QVerdict(0 < req <= sold, "ok", sold))
    qmutant("qty_negative_accepted", lambda req, sold, already:
            R.QVerdict(req <= (sold - already), "ok", sold - already))
    return results


def run_all():
    return {name: fn() for name, fn in ALL}


if __name__ == "__main__":
    results = run_all()
    total = sum(len(v) for v in results.values())
    print("Refund ceiling tests (integer minor units)")
    for name, fails in results.items():
        print(f"  {name:34s} {'PASS ✓' if not fails else f'FAIL ✗ {fails[:1]}'}")
    muts = run_mutations()
    print("mutation resistance (True = broken ceiling detected):")
    for name, caught in muts.items():
        print(f"  {name:28s} {'CAUGHT ✓' if caught else 'MISSED ✗'}")
    ok = total == 0 and all(muts.values())
    print("RESULT:", "PASS ✓" if ok else "FAIL ✗")
    raise SystemExit(0 if ok else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestRefundCeiling(TransactionCase):
        def test_ceiling(self):
            failures = {k: v for k, v in run_all().items() if v}
            self.assertEqual(failures, {}, f"refund ceiling wrong: {failures}")

        def test_mutation_resistance(self):
            self.assertTrue(all(run_mutations().values()), "ceiling mutation not caught")
except Exception:
    pass
