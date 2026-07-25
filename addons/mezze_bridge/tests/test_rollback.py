"""Rollback evidence: `fsm_guard = off` COMPLETELY bypasses the guard.

Proves — for pay, fire, refund, comp AND cancel — that in `off` mode there is:
  * no call to the FSM evaluator (`check_operation`),
  * no call to `apply_event`,
  * no lifecycle verdict computed,
  * no blocking,
  * no violation audit detail generated,
and that observe/enforce DO still evaluate (so `off` is a true bypass, not a
no-op that also disabled the guard everywhere).

Bypass is proven with call-counting SPIES on the evaluator and `apply_event`,
so the suite FAILS if evaluation or auditing occurs in `off` mode. Asserting
`blocked=False` alone would be insufficient; this asserts zero evaluation.

Boundary note: this exercises the single pure decision chokepoint
(`order_guard.evaluate`) that every controller `_fsm_guard` call routes through.
The controller adapter calls `evaluate` exactly once and audits/block ONLY when
`evaluate` returns audit_detail/blocked; so `off` -> (blocked=False, detail=None)
guarantees the adapter neither blocks nor audits. Live Odoo was NOT booted (none
available); the adapter contract is asserted, not observed in-process.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import domain.order_guard as og  # noqa: E402
from domain.order_guard import (  # noqa: E402
    MODE_OFF, MODE_OBSERVE, MODE_ENFORCE, EvalResult,
)

OPS = ("pay", "fire", "refund", "comp", "cancel")
# (op -> (allowed_state, forbidden_state)) representative pairs, per the FSM.
STATES = {
    "pay": ("draft", "paid"),
    "fire": ("draft", "paid"),
    "refund": ("paid", "draft"),
    "comp": ("draft", "paid"),
    "cancel": ("draft", "paid"),
}
CTX = {"endpoint": "test", "order_id": 1, "order_uuid": "u", "branch_id": 1,
       "company_id": 1, "actor_uid": 1, "correlation_id": "c", "ts": "t"}


class _Spies:
    """Install counting spies on the evaluator and apply_event; restore on exit."""

    def __enter__(self):
        self.n = {"check": 0, "apply": 0}
        self._c, self._a = og.check_operation, og.apply_event

        def spy_check(state, operation):
            self.n["check"] += 1
            return self._c(state, operation)

        def spy_apply(state, event):
            self.n["apply"] += 1
            return self._a(state, event)

        og.check_operation, og.apply_event = spy_check, spy_apply
        return self

    def __exit__(self, *a):
        og.check_operation, og.apply_event = self._c, self._a


def _off_fully_bypasses(op):
    """True iff `off` never evaluates/audits/blocks for either state of `op`."""
    for state in STATES[op]:
        with _Spies() as sp:
            res = og.evaluate(state, op, MODE_OFF, CTX)
        if sp.n["check"] != 0 or sp.n["apply"] != 0:
            return False, ("off evaluated", op, state, dict(sp.n))
        if res != EvalResult(False, False, None, None):
            return False, ("off not inert", op, state, res)
    return True, None


def _non_off_still_evaluates(op):
    """True iff observe/enforce DO evaluate (proves off is a real bypass)."""
    allowed_state, forbidden_state = STATES[op]
    for mode in (MODE_OBSERVE, MODE_ENFORCE):
        with _Spies() as sp:
            res = og.evaluate(forbidden_state, op, mode, CTX)
        if sp.n["check"] == 0:
            return False, ("mode did not evaluate", op, mode)
        if res.audit_detail is None:           # forbidden -> must produce telemetry
            return False, ("no audit on forbidden", op, mode)
        if mode == MODE_ENFORCE and not res.blocked:
            return False, ("enforce did not block forbidden", op)
        if mode == MODE_OBSERVE and res.blocked:
            return False, ("observe blocked", op)
    # allowed op must never block in any mode
    for mode in (MODE_OBSERVE, MODE_ENFORCE):
        if og.evaluate(allowed_state, op, mode, CTX).blocked:
            return False, ("allowed op blocked", op, mode)
    return True, None


def run_rollback():
    """Return {op: bool} — True iff off fully bypasses AND non-off still guards."""
    out = {}
    for op in OPS:
        off_ok, _ = _off_fully_bypasses(op)
        eval_ok, _ = _non_off_still_evaluates(op)
        out[op] = off_ok and eval_ok
    return out


def rollback_failures():
    fails = []
    for op in OPS:
        ok1, why1 = _off_fully_bypasses(op)
        ok2, why2 = _non_off_still_evaluates(op)
        if not ok1:
            fails.append(why1)
        if not ok2:
            fails.append(why2)
    return fails


# ------------------------------ mutation tests ------------------------------
def run_mutations():
    """Prove the rollback suite catches a broken off-mode bypass."""
    results = {}
    real_eval = og.evaluate

    # M1: off mode still EVALUATES (calls check_operation) -> must be caught
    def eval_off_evaluates(state, operation, mode, ctx=None):
        if mode == MODE_OFF:
            og.check_operation(state, operation)          # illegal work in off
            return EvalResult(False, False, None, None)
        return real_eval(state, operation, mode, ctx)
    og.evaluate = eval_off_evaluates
    results["off_still_evaluates"] = bool(rollback_failures())
    og.evaluate = real_eval

    # M2: off mode still AUDITS (returns audit_detail) -> must be caught
    def eval_off_audits(state, operation, mode, ctx=None):
        if mode == MODE_OFF:
            return EvalResult(False, True, None, {"leak": True})
        return real_eval(state, operation, mode, ctx)
    og.evaluate = eval_off_audits
    results["off_still_audits"] = bool(rollback_failures())
    og.evaluate = real_eval

    # M3: enforce permits a forbidden op -> must be caught
    def eval_enforce_permits(state, operation, mode, ctx=None):
        r = real_eval(state, operation, mode, ctx)
        return r._replace(blocked=False) if r.violation else r
    og.evaluate = eval_enforce_permits
    results["enforce_permits_forbidden"] = bool(rollback_failures())
    og.evaluate = real_eval

    return results


ALL = [("rollback_bypass_all_ops", lambda: rollback_failures())]


def run_all():
    return {name: fn() for name, fn in ALL}


if __name__ == "__main__":
    per_op = run_rollback()
    fails = rollback_failures()
    muts = run_mutations()
    print("Rollback (off-mode full bypass) evidence")
    for op, ok in per_op.items():
        print(f"  {op:8s} {'BYPASS ✓' if ok else 'FAIL ✗'}")
    print("mutation resistance (True = broken bypass detected):")
    for name, caught in muts.items():
        print(f"  {name:28s} {'CAUGHT ✓' if caught else 'MISSED ✗'}")
    ok = (not fails) and all(muts.values())
    print("RESULT:", "PASS ✓" if ok else f"FAIL ✗ {fails[:2]}")
    raise SystemExit(0 if ok else 1)


try:  # pragma: no cover — Odoo wrapper
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestRollback(TransactionCase):
        def test_off_mode_full_bypass(self):
            self.assertEqual(rollback_failures(), [], "off mode did not fully bypass")

        def test_rollback_mutation_resistance(self):
            self.assertTrue(all(run_mutations().values()), "rollback bypass mutation not caught")
except Exception:
    pass
