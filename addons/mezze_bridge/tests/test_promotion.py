"""Tests for the executable enforcement-promotion gate (domain/promotion.py).

`rollback_tested` is DERIVED from per-operation evidence and is proven true only
when the real rollback suite passes for every guarded operation.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from domain.promotion import assess, rollback_tested, REQUIRED_ROLLBACK_OPS  # noqa: E402
try:  # feeds the gate with the real rollback result — works standalone and under Odoo
    from . import test_rollback
except ImportError:
    import test_rollback  # noqa: E402

FULL_ROLLBACK = {op: True for op in REQUIRED_ROLLBACK_OPS}
ALL_EVIDENCE = {
    "suites_green": True, "mutation_green": True, "rollback": dict(FULL_ROLLBACK),
    "dashboards_ready": True, "owner_approved": True,
}
CLEAN_SUMMARY = {"observed_count": 25, "unclassified": 0, "unexplained_fp": 0,
                 "by_operation": {"pay": 3, "comp": 2}}


def t_all_met_is_ready():
    r = assess(CLEAN_SUMMARY, ALL_EVIDENCE, min_observations=10)
    return [] if r.ready and not r.blocking else [("expected ready", r)]


def t_unexplained_fp_blocks():
    r = assess({**CLEAN_SUMMARY, "unexplained_fp": 2}, ALL_EVIDENCE)
    return [] if not r.ready and any("false_positives" in b for b in r.blocking) else [("fp not blocking", r)]


def t_unclassified_blocks():
    r = assess({**CLEAN_SUMMARY, "unclassified": 5}, ALL_EVIDENCE)
    return [] if not r.ready and any("unclassified" in b for b in r.blocking) else [("unclassified not blocking", r)]


def t_each_evidence_gate_blocks():
    fails = []
    for key in ("suites_green", "mutation_green", "dashboards_ready", "owner_approved"):
        r = assess(CLEAN_SUMMARY, {**ALL_EVIDENCE, key: False})
        if r.ready:
            fails.append(("evidence gate not enforced", key))
    return fails


def t_rollback_incomplete_blocks():
    fails = []
    # missing an operation entirely
    partial = {op: True for op in REQUIRED_ROLLBACK_OPS if op != "cancel"}
    r = assess(CLEAN_SUMMARY, {**ALL_EVIDENCE, "rollback": partial})
    if r.ready or not any("rollback_not_proven_for" in b for b in r.blocking):
        fails.append(("missing-op rollback not blocking", r.blocking))
    # an operation explicitly failed
    failed = dict(FULL_ROLLBACK, cancel=False)
    r = assess(CLEAN_SUMMARY, {**ALL_EVIDENCE, "rollback": failed})
    if r.ready or not any("cancel" in b for b in r.blocking):
        fails.append(("failed-op rollback not blocking", r.blocking))
    # no rollback evidence at all
    ev = {k: v for k, v in ALL_EVIDENCE.items() if k != "rollback"}
    if assess(CLEAN_SUMMARY, ev).ready:
        fails.append(("no rollback evidence wrongly ready",))
    return fails


def t_rollback_tested_derivation():
    fails = []
    ok, missing = rollback_tested({"rollback": FULL_ROLLBACK})
    if not ok or missing:
        fails.append(("full should pass", ok, missing))
    ok, missing = rollback_tested({"rollback": {"pay": True}})
    if ok or "cancel" not in missing:
        fails.append(("partial should fail", ok, missing))
    return fails


def t_rollback_from_real_suite():
    """Feed the ACTUAL rollback-suite result into the gate: it must satisfy the
    rollback criterion (all 5 ops bypass) and cover every required op."""
    real = test_rollback.run_rollback()
    fails = []
    if set(real.keys()) != set(REQUIRED_ROLLBACK_OPS):
        fails.append(("rollback suite op coverage mismatch", sorted(real.keys())))
    r = assess(CLEAN_SUMMARY, {**ALL_EVIDENCE, "rollback": real})
    if any("rollback_not_proven_for" in b for b in r.blocking):
        fails.append(("real rollback suite failed the gate", r.blocking))
    return fails


def t_defaults_safe():
    r = assess({}, {})
    return [] if not r.ready else [("empty inputs wrongly ready", r)]


def t_deterministic():
    return [] if assess(CLEAN_SUMMARY, ALL_EVIDENCE) == assess(CLEAN_SUMMARY, ALL_EVIDENCE) else [("non-deterministic",)]


# ------------------------------ mutation tests ------------------------------
def run_mutations():
    """Prove the gate rejects incomplete rollback evidence (cannot be fooled)."""
    results = {}
    # gate accepts incomplete rollback -> caught by t_rollback_incomplete_blocks
    incomplete_ready = assess(CLEAN_SUMMARY, {**ALL_EVIDENCE, "rollback": {"pay": True}}).ready
    results["incomplete_rollback_rejected"] = (incomplete_ready is False)
    # gate accepts a failed op -> must not be ready
    failed_ready = assess(CLEAN_SUMMARY, {**ALL_EVIDENCE, "rollback": dict(FULL_ROLLBACK, cancel=False)}).ready
    results["failed_op_rejected"] = (failed_ready is False)
    return results


ALL = [
    ("all_met_is_ready", t_all_met_is_ready),
    ("unexplained_fp_blocks", t_unexplained_fp_blocks),
    ("unclassified_blocks", t_unclassified_blocks),
    ("each_evidence_gate_blocks", t_each_evidence_gate_blocks),
    ("rollback_incomplete_blocks", t_rollback_incomplete_blocks),
    ("rollback_tested_derivation", t_rollback_tested_derivation),
    ("rollback_from_real_suite", t_rollback_from_real_suite),
    ("defaults_safe", t_defaults_safe),
    ("deterministic", t_deterministic),
]


def run_all():
    return {name: fn() for name, fn in ALL}


if __name__ == "__main__":
    results = run_all()
    total = sum(len(v) for v in results.values())
    print("Enforcement-promotion gate tests")
    for name, fails in results.items():
        print(f"  {name:34s} {'PASS ✓' if not fails else f'FAIL ✗ {fails[:2]}'}")
    muts = run_mutations()
    print("mutation resistance (True = incomplete evidence rejected):")
    for name, caught in muts.items():
        print(f"  {name:34s} {'CAUGHT ✓' if caught else 'MISSED ✗'}")
    ok = total == 0 and all(muts.values())
    print("RESULT:", "PASS ✓" if ok else "FAIL ✗")
    raise SystemExit(0 if ok else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestPromotion(TransactionCase):
        def test_gate(self):
            failures = {k: v for k, v in run_all().items() if v}
            self.assertEqual(failures, {}, f"promotion gate wrong: {failures}")

        def test_mutation_resistance(self):
            self.assertTrue(all(run_mutations().values()), "gate accepted incomplete evidence")
except Exception:
    pass
