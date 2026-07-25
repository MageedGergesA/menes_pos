"""Executable enforcement of RFC-001 Order lifecycle invariants.

Runnable standalone:  python3 tests/test_order_fsm.py
Runnable under Odoo:  odoo -i mezze_bridge --test-enable  (TransactionCase wrapper)

Covers: unit (forbidden pairs), property (random walks + exhaustive
reachability), regression (named forbidden transitions), replay/determinism.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from domain.order_fsm import (  # noqa: E402
    State, Event, ForbiddenTransition, apply_event, fold, reachable,
    allowed_events, is_settled, PRE_PAYMENT_STATES, SETTLED_STATES,
    TERMINAL_STATES, _T,
)

# The forbidden transitions RFC-001 calls out by name (regression anchors).
NAMED_FORBIDDEN = [
    (State.DRAFT, Event.PAY_FULL),      # Draft -> Paid
    (State.CLOSED, Event.OPEN),         # Closed -> Open
    (State.CLOSED, Event.ADD_LINE),     # no mutation after close
    (State.CANCELLED, Event.RESUME),    # Cancelled -> (anything but Archive)
    (State.CANCELLED, Event.PAY_FULL),
    (State.REFUNDED, Event.PAY_FULL),   # Refunded -> Paid
    (State.PAID, Event.ADD_LINE),       # paid orders are immutable
    (State.PAID, Event.OPEN),           # paid cannot be reopened
    (State.ARCHIVED, Event.ARCHIVE),    # terminal
]


def t_named_forbidden_all_raise():
    fails = []
    for st, ev in NAMED_FORBIDDEN:
        try:
            apply_event(st, ev)
            fails.append(("did not raise", st.value, ev.value))
        except ForbiddenTransition:
            pass
    return fails


def t_paid_cannot_become_unpaid():
    """Exhaustive: from every settled state, no pre-payment state is reachable."""
    fails = []
    for s in SETTLED_STATES:
        bad = reachable(s) & PRE_PAYMENT_STATES
        if bad:
            fails.append(("settled reaches pre-payment", s.value, [b.value for b in bad]))
    return fails


def t_determinism():
    fails = []
    for st in State:
        for ev in allowed_events(st):
            a, b = apply_event(st, ev), apply_event(st, ev)
            if a != b:
                fails.append(("non-deterministic", st.value, ev.value))
    return fails


def t_terminal_has_no_exits():
    fails = []
    for s in TERMINAL_STATES:
        if _T[s]:
            fails.append(("terminal has outgoing", s.value))
    return fails


def t_replay_safe():
    """Folding a log twice is reproducible; prefix-folding is consistent."""
    fails = []
    rng = random.Random(4242)
    for _ in range(2000):
        events, state = [], State.DRAFT
        for _ in range(rng.randint(0, 12)):
            opts = list(allowed_events(state))
            if not opts:
                break
            ev = rng.choice(opts)
            events.append(ev)
            state = apply_event(state, ev)
        if fold(events) != fold(events):
            fails.append(("non-reproducible fold", [e.value for e in events]))
        # prefix consistency: fold(prefix) then apply the rest == fold(all)
        if events:
            k = rng.randint(0, len(events))
            mid = fold(events[:k])
            if fold(events[k:], start=mid) != fold(events):
                fails.append(("prefix fold mismatch", [e.value for e in events]))
    return fails


def t_random_walk_invariants(iterations=50000):
    """Property: on any legal random walk, settlement is monotonic and no
    forbidden transition is ever silently taken."""
    fails = []
    rng = random.Random(1729)
    for _ in range(iterations):
        state = State.DRAFT
        settled_seen = False
        for _ in range(rng.randint(0, 20)):
            opts = list(allowed_events(state))
            if not opts:
                break
            ev = rng.choice(opts)
            nxt = apply_event(state, ev)
            # monotonic money: once settled, never observe a pre-payment state again
            if settled_seen and nxt in PRE_PAYMENT_STATES:
                fails.append(("un-paid!", state.value, ev.value, nxt.value))
                break
            if is_settled(nxt):
                settled_seen = True
            state = nxt
    return fails


def t_illegal_events_always_raise(iterations=20000):
    """Property: any (state, event) NOT in the table raises — no silent no-op."""
    fails = []
    rng = random.Random(99)
    all_events = list(Event)
    for _ in range(iterations):
        st = rng.choice(list(State))
        ev = rng.choice(all_events)
        legal = ev in allowed_events(st)
        try:
            apply_event(st, ev)
            if not legal:
                fails.append(("illegal did not raise", st.value, ev.value))
        except ForbiddenTransition:
            if legal:
                fails.append(("legal raised", st.value, ev.value))
    return fails


ALL = [
    ("named_forbidden_all_raise", t_named_forbidden_all_raise),
    ("paid_cannot_become_unpaid", t_paid_cannot_become_unpaid),
    ("determinism", t_determinism),
    ("terminal_has_no_exits", t_terminal_has_no_exits),
    ("replay_safe", t_replay_safe),
    ("random_walk_invariants", t_random_walk_invariants),
    ("illegal_events_always_raise", t_illegal_events_always_raise),
]


def run_all():
    results = {}
    for name, fn in ALL:
        results[name] = fn()
    return results


if __name__ == "__main__":
    results = run_all()
    total = sum(len(v) for v in results.values())
    print("RFC-001 Order-FSM invariant enforcement")
    for name, fails in results.items():
        status = "PASS ✓" if not fails else f"FAIL ✗ ({len(fails)})"
        print(f"  {name:32s} {status}")
        if fails:
            print("      sample:", fails[:2])
    print("RESULT:", "PASS ✓" if total == 0 else f"FAIL ✗ ({total})")
    raise SystemExit(0 if total == 0 else 1)


try:  # pragma: no cover — Odoo test-runner wrapper
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestOrderFsm(TransactionCase):
        def test_all_order_invariants(self):
            results = run_all()
            failures = {k: v for k, v in results.items() if v}
            self.assertEqual(failures, {}, f"Order-FSM invariants violated: {failures}")
except Exception:
    pass
