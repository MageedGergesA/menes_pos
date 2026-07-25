"""Integration-boundary test: the FSM guard is wired BEFORE mutation/side effects.

Without booting Odoo, this proves the wiring invariant at the closest safe
boundary — the controller source: for each lifecycle-sensitive endpoint, the
``_fsm_guard(..., '<operation>', ...)`` call must appear, and must appear BEFORE
the endpoint's first real mutation / external side effect. A regression that
moves a mutation ahead of the guard (or drops the guard) fails this test.

Standalone:  python3 tests/test_guard_wiring.py
"""

import os
import re

CTRL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "controllers", "main.py")

# operation label -> a regex marking the FIRST mutation/side-effect that must
# come AFTER the guard for that endpoint.
CASES = [
    ("pay", r"add_payment\("),                       # order_pay: no payment before guard
    ("refund", r"sync_from_ui\("),                    # order_refund: no ledger write before guard
    ("comp", r"'discount':\s*100\.0"),                # order_comp: no line mutation before guard
    ("fire", r"_make_station_tickets\(|\._broadcast\("),  # _do_fire: no ticket/broadcast before guard
]


def _functions(src):
    """Return [(start, end, name)] for every top-level controller method."""
    defs = [(m.start(), m.group(1)) for m in re.finditer(r"\n    def (\w+)\(", src)]
    out = []
    for i, (start, name) in enumerate(defs):
        end = defs[i + 1][0] if i + 1 < len(defs) else len(src)
        out.append((start, end, name))
    return out


def _enclosing(functions, pos):
    for start, end, name in functions:
        if start <= pos < end:
            return start, end, name
    return None


def _guard_positions(src, operation):
    pat = re.compile(r"_fsm_guard\([^)]*['\"]%s['\"]" % re.escape(operation))
    return [m.start() for m in pat.finditer(src)]


def t_guard_present_and_before_mutation():
    """Within the SAME function, the guard must precede the first mutation."""
    src = open(CTRL, encoding="utf-8").read()
    functions = _functions(src)
    fails = []
    for op, mutation_re in CASES:
        guards = _guard_positions(src, op)
        if not guards:
            fails.append((op, "no _fsm_guard call found"))
            continue
        guard_pos = guards[0]
        fn = _enclosing(functions, guard_pos)
        if not fn:
            fails.append((op, "guard not inside a function"))
            continue
        f_start, f_end, fname = fn
        body = src[f_start:f_end]
        muts = [m.start() + f_start for m in re.finditer(mutation_re, body)]
        if not muts:
            fails.append((op, "mutation marker %s not found in %s" % (mutation_re, fname)))
            continue
        if guard_pos >= min(muts):
            fails.append((op, "guard after mutation in %s" % fname))
    return fails


def t_guard_returns_block_before_proceeding():
    """Each guard call must be immediately followed by an early-return on block."""
    src = open(CTRL, encoding="utf-8").read()
    fails = []
    # pattern: blocked = self._fsm_guard(...)  \n  if blocked: return blocked
    calls = list(re.finditer(r"self\._fsm_guard\([^\n]*\)", src))
    for m in calls:
        tail = src[m.end():m.end() + 120]
        if "return blocked" not in tail:
            fails.append(("guard call not followed by 'return blocked'", src[m.start():m.end()][:60]))
    return fails


# Patterns that would constitute a pos.order LIFECYCLE cancellation. Today the
# bridge has NONE (drive-thru/aggregator cancels mutate sibling records, not the
# order). This tripwire stays green until someone adds a real pos.order cancel —
# at which point it FAILS unless that write is preceded by a 'cancel' guard.
POS_ORDER_CANCEL_PATTERNS = [
    r"\.action_pos_order_cancel\(",
    r"\b(?:order|orig)\.write\(\{[^}]*['\"]state['\"]\s*:\s*['\"]cancel['\"]",
    r"\b(?:order|orig)\.state\s*=\s*['\"]cancel['\"]",
]


def t_pos_order_cancel_writes_are_guarded():
    """Every pos.order cancellation write must be preceded, in the same function,
    by a `_fsm_guard(..., 'cancel', ...)`. Vacuously true now (zero such writes);
    a future unguarded pos.order cancel trips this test."""
    src = open(CTRL, encoding="utf-8").read()
    functions = _functions(src)
    guard_pat = re.compile(r"_fsm_guard\([^)]*['\"]cancel['\"]")
    fails = []
    for pat in POS_ORDER_CANCEL_PATTERNS:
        for m in re.finditer(pat, src):
            fn = _enclosing(functions, m.start())
            if not fn:
                fails.append(("cancel write outside a function", m.group(0)[:40]))
                continue
            f_start, f_end, fname = fn
            guards = [g.start() + f_start for g in guard_pat.finditer(src[f_start:f_end])]
            if not any(g < m.start() for g in guards):
                fails.append(("unguarded pos.order cancel in %s" % fname, m.group(0)[:40]))
    return fails


def t_missing_order_handled():
    """The guard adapter must short-circuit on a missing/nonexistent order so a
    bad/malformed identifier never crashes the endpoint."""
    src = open(CTRL, encoding="utf-8").read()
    m = re.search(r"def _fsm_guard\(.*?(?=\n    def )", src, re.S)
    if not m:
        return [("_fsm_guard not found",)]
    body = m.group(0)
    fails = []
    if "not order or not order.exists()" not in body:
        fails.append(("missing-order short-circuit removed",))
    if "except Exception" not in body:
        fails.append(("guard exception fail-safe removed",))
    return fails


ALL = [
    ("guard_present_and_before_mutation", t_guard_present_and_before_mutation),
    ("guard_returns_block_before_proceeding", t_guard_returns_block_before_proceeding),
    ("pos_order_cancel_writes_are_guarded", t_pos_order_cancel_writes_are_guarded),
    ("missing_order_handled", t_missing_order_handled),
]


def run_all():
    return {name: fn() for name, fn in ALL}


if __name__ == "__main__":
    results = run_all()
    total = sum(len(v) for v in results.values())
    print("Guard wiring (structural integration)")
    for name, fails in results.items():
        print(f"  {name:40s} {'PASS ✓' if not fails else f'FAIL ✗ {fails}'}")
    print("RESULT:", "PASS ✓" if total == 0 else f"FAIL ✗ ({total})")
    raise SystemExit(0 if total == 0 else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestGuardWiring(TransactionCase):
        def test_wiring(self):
            failures = {k: v for k, v in run_all().items() if v}
            self.assertEqual(failures, {}, f"guard wiring regressions: {failures}")
except Exception:
    pass
