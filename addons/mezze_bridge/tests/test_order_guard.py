"""Tests for the order-operation guard (domain/order_guard.py).

Standalone:  python3 tests/test_order_guard.py
Under Odoo:  TransactionCase wrapper at the bottom.

Covers pay/refund/comp/fire: FSM equivalence, mode behaviour (off/observe/
enforce), telemetry shape, determinism, and mutation resistance. The guard's
verdicts are sourced from the RFC-001 FSM, so the "only open orders can be
paid/modified/fired; only paid orders can be refunded" rules have ONE source.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from domain import order_guard  # noqa: E402
from domain.order_guard import (  # noqa: E402
    check_operation, evaluate, EvalResult, MODE_OFF, MODE_OBSERVE, MODE_ENFORCE,
    ODOO_STATE_MAP, OP_EVENT_MAP,
)
from domain.order_fsm import allowed_events  # noqa: E402

check = check_operation

# Operator-facing rules, sourced from the FSM (regression anchors).
REGRESSION = [
    ("draft", "pay", True), ("paid", "pay", False), ("done", "pay", False),
    ("cancel", "pay", False),
    ("paid", "refund", True), ("done", "refund", True), ("draft", "refund", False),
    ("cancel", "refund", False),
    ("draft", "comp", True), ("paid", "comp", False), ("done", "modify", False),
    ("draft", "cancel", True), ("paid", "cancel", False),
    ("draft", "fire", True), ("paid", "fire", False), ("done", "fire", False),
    ("cancel", "fire", False),
    ("paid", "close", True), ("cancel", "cancel", False),
]

# A representative ctx exactly as the controller adapter builds it (PII-safe).
SAMPLE_CTX = {
    "endpoint": "orders/refund", "order_id": 42, "order_uuid": "u-42",
    "branch_id": 7, "company_id": 3, "actor_uid": 9,
    "correlation_id": "corr-abc", "ts": "2026-07-22 10:00:00",
}
REQUIRED_TELEMETRY = {
    "operation", "server_state", "mapped_event", "reason", "reason_code",
    "mode", "observe_proceeded", "endpoint", "order_id", "order_uuid",
    "branch_id", "company_id", "actor_uid", "correlation_id", "ts",
}


def t_regression():
    fails = []
    for state, op, expected in REGRESSION:
        v = check(state, op)
        if v.ok != expected:
            fails.append((state, op, "expected=%s got=%s (%s)" % (expected, v.ok, v.reason)))
    return fails


def t_unknown_never_blocks():
    fails = []
    for v in (check("weird", "pay"), check("draft", "teleport"), check(None, None)):
        if not v.ok:
            fails.append(("unknown blocked", v))
    return fails


def t_guard_matches_fsm_exhaustively():
    """Guard verdict == FSM for every mapped (state, operation): no divergence."""
    fails = []
    for odoo_state, fsm_state in ODOO_STATE_MAP.items():
        for op, event in OP_EVENT_MAP.items():
            v = check(odoo_state, op)
            fsm_ok = event in allowed_events(fsm_state)
            if v.ok != fsm_ok:
                fails.append((odoo_state, op, "guard=%s fsm=%s" % (v.ok, fsm_ok)))
    return fails


def t_evaluate_modes():
    fails = []
    # off: never evaluates, never blocks, never audits — even on a forbidden op
    r = evaluate("paid", "pay", MODE_OFF, SAMPLE_CTX)
    if r != EvalResult(False, False, None, None):
        fails.append(("off not inert", r))
    # allowed op in any mode: no block, no audit
    for mode in (MODE_OBSERVE, MODE_ENFORCE):
        r = evaluate("draft", "pay", mode, SAMPLE_CTX)
        if r.blocked or r.violation or r.audit_detail is not None:
            fails.append(("allowed op flagged", mode, r))
    # forbidden + observe: NOT blocked, audit present, observe_proceeded True
    r = evaluate("paid", "pay", MODE_OBSERVE, SAMPLE_CTX)
    if r.blocked or not r.violation or not r.audit_detail or r.audit_detail["observe_proceeded"] is not True:
        fails.append(("observe wrong", r))
    # forbidden + enforce: blocked, audit present, observe_proceeded False
    r = evaluate("paid", "pay", MODE_ENFORCE, SAMPLE_CTX)
    if not r.blocked or not r.violation or not r.audit_detail or r.audit_detail["observe_proceeded"] is not False:
        fails.append(("enforce wrong", r))
    # unknown mode -> safe default observe (never blocks)
    r = evaluate("paid", "pay", "banana", SAMPLE_CTX)
    if r.blocked:
        fails.append(("unknown mode blocked", r))
    return fails


def t_evaluate_telemetry():
    import re
    fails = []
    r = evaluate("paid", "pay", MODE_OBSERVE, SAMPLE_CTX)
    d = r.audit_detail
    if d is None:
        return [("no audit detail on violation",)]
    missing = REQUIRED_TELEMETRY - set(d.keys())
    if missing:
        fails.append(("missing telemetry", missing))
    # keys are a subset of the known-safe allowlist -> no secret/PII key can slip in
    extra = set(d.keys()) - REQUIRED_TELEMETRY
    if extra:
        fails.append(("unexpected (possibly unsafe) telemetry keys", extra))
    # authoritative server state comes from the passed state, not any client field
    if d["server_state"] != "paid" or d["operation"] != "pay":
        fails.append(("state/op wrong", d.get("server_state"), d.get("operation")))
    if d["reason_code"] != "forbidden_transition":
        fails.append(("reason_code", d.get("reason_code")))
    # no PAN-like value (12-19 consecutive digits) leaked into any telemetry value
    for k, v in d.items():
        if re.search(r"\d{12,19}", str(v)):
            fails.append(("possible PAN in telemetry", k))
    return fails


def t_operations_map_to_correct_event():
    """Prove each endpoint operation maps to the intended canonical event."""
    expected = {"pay": "pay_full", "refund": "refund", "comp": "add_line",
                "fire": "send", "cancel": "cancel", "close": "close"}
    fails = []
    for op, ev in expected.items():
        if OP_EVENT_MAP[op].value != ev:
            fails.append((op, "mapped to", OP_EVENT_MAP[op].value, "expected", ev))
    return fails


def t_determinism():
    fails = []
    for s in ODOO_STATE_MAP:
        for op in OP_EVENT_MAP:
            if evaluate(s, op, MODE_ENFORCE, SAMPLE_CTX) != evaluate(s, op, MODE_ENFORCE, SAMPLE_CTX):
                fails.append((s, op))
    return fails


def t_server_state_wins():
    """A client-ish field in ctx must NEVER change the verdict; only the
    authoritative server state param governs (RFC-000 never-trust-client)."""
    fails = []
    r_paid = evaluate("paid", "cancel", MODE_ENFORCE, {**SAMPLE_CTX, "client_state": "draft"})
    if not r_paid.blocked:
        fails.append(("client_state overrode server state -> unblocked forbidden cancel",))
    r_draft = evaluate("draft", "cancel", MODE_ENFORCE, {**SAMPLE_CTX, "client_state": "paid"})
    if r_draft.blocked:
        fails.append(("client_state blocked a legal cancel",))
    if not r_paid.audit_detail or r_paid.audit_detail.get("server_state") != "paid":
        fails.append(("audit recorded client state, not server",))
    return fails


# ------------------------------ mutation tests ------------------------------
def run_mutations():
    """Prove the suite FAILS when the guard is broken. Each entry returns True
    iff a broken guard is detected by the assertions above."""
    results = {}

    # M1: map comp to the WRONG event (settlement). A wrong-but-consistent map
    # can't be caught by self-equivalence; the explicit mapping test must catch it.
    saved = OP_EVENT_MAP["comp"]
    from domain.order_fsm import Event
    OP_EVENT_MAP["comp"] = Event.PAY_FULL
    results["wrong_event_map"] = bool(t_operations_map_to_correct_event())
    OP_EVENT_MAP["comp"] = saved

    # M1b: cancel mapped to the WRONG event -> mapping test must catch
    saved_c = OP_EVENT_MAP["cancel"]
    OP_EVENT_MAP["cancel"] = Event.PAY_FULL
    results["cancel_wrong_event_map"] = bool(t_operations_map_to_correct_event())
    OP_EVENT_MAP["cancel"] = saved_c

    # M4: client state trusted -> server_state test must catch
    real_eval = order_guard.evaluate
    def client_trusting_eval(state, op, mode, ctx=None):
        # simulate trusting a client-supplied state from ctx
        eff = (ctx or {}).get("client_state", state)
        return real_eval(eff, op, mode, ctx)
    order_guard.evaluate = client_trusting_eval
    globals()["evaluate"] = client_trusting_eval
    results["client_state_trusted"] = bool(t_server_state_wins())
    order_guard.evaluate = real_eval
    globals()["evaluate"] = real_eval

    # M2: enforce allows a forbidden transition -> observe/enforce test must catch
    real_eval = order_guard.evaluate
    def bad_eval(state, op, mode, ctx=None):
        r = real_eval(state, op, mode, ctx)
        return r._replace(blocked=False) if r.violation else r  # never block
    order_guard.evaluate = bad_eval
    globals()["evaluate"] = bad_eval
    results["enforce_allows_forbidden"] = bool(t_evaluate_modes())
    order_guard.evaluate = real_eval
    globals()["evaluate"] = real_eval

    # M3: audit removed (detail dropped) -> telemetry test must catch
    def no_audit_eval(state, op, mode, ctx=None):
        r = real_eval(state, op, mode, ctx)
        return r._replace(audit_detail=None) if r.violation else r
    order_guard.evaluate = no_audit_eval
    globals()["evaluate"] = no_audit_eval
    try:
        no_audit_caught = bool(t_evaluate_telemetry())
    except Exception:
        no_audit_caught = True  # blowing up on missing detail also counts as caught
    results["audit_removed"] = no_audit_caught
    order_guard.evaluate = real_eval
    globals()["evaluate"] = real_eval

    return results


ALL = [
    ("regression", t_regression),
    ("unknown_never_blocks", t_unknown_never_blocks),
    ("guard_matches_fsm_exhaustively", t_guard_matches_fsm_exhaustively),
    ("evaluate_modes", t_evaluate_modes),
    ("evaluate_telemetry", t_evaluate_telemetry),
    ("operations_map_to_correct_event", t_operations_map_to_correct_event),
    ("determinism", t_determinism),
    ("server_state_wins", t_server_state_wins),
]


def run_all():
    return {name: fn() for name, fn in ALL}


if __name__ == "__main__":
    results = run_all()
    total = sum(len(v) for v in results.values())
    print("Order-guard tests (pay/refund/comp/fire, FSM-sourced)")
    for name, fails in results.items():
        print(f"  {name:34s} {'PASS ✓' if not fails else f'FAIL ✗ {fails[:2]}'}")
    muts = run_mutations()
    print("mutation resistance (each must be True = broken guard detected):")
    for name, caught in muts.items():
        print(f"  {name:34s} {'CAUGHT ✓' if caught else 'MISSED ✗'}")
    mut_ok = all(muts.values())
    print("RESULT:", "PASS ✓" if (total == 0 and mut_ok) else "FAIL ✗")
    raise SystemExit(0 if (total == 0 and mut_ok) else 1)


try:  # pragma: no cover — Odoo wrapper
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestOrderGuard(TransactionCase):
        def test_rules(self):
            failures = {k: v for k, v in run_all().items() if v}
            self.assertEqual(failures, {}, f"order-guard rules violated: {failures}")

        def test_mutation_resistance(self):
            self.assertTrue(all(run_mutations().values()), "guard mutation not caught")
except Exception:
    pass
