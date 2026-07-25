"""Tests for the canonical authorization/integrity rules (domain/authz.py).

Standalone:  python3 tests/test_authz.py
Unit + property + mutation. Runtime auth is proven in test_runtime_security.py.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from domain import authz as A  # noqa: E402


def t_capability_matrix():
    fails = []
    cases = [
        ("cashier", A.ORDERS_PAY, True),
        ("cashier", A.ORDERS_REFUND, False),    # refund needs supervisor+
        ("cashier", A.ORDERS_COMP, False),
        ("cashier", A.ADMIN_SETTINGS, False),
        ("supervisor", A.ORDERS_REFUND, True),
        ("supervisor", A.ORDERS_COMP, True),
        ("supervisor", A.ADMIN_SETTINGS, False),
        ("manager", A.ORDERS_REFUND, True),
        ("manager", A.ADMIN_SETTINGS, True),
        ("manager", A.REPORTS_EXPORT, True),
        (None, A.ORDERS_PAY, False),            # unknown role -> deny
        ("cashier", "orders.delete", False),    # unknown capability -> deny
    ]
    for role, cap, expected in cases:
        if A.can(role, cap) != expected:
            fails.append((role, cap, "exp", expected))
    return fails


def t_role_supersets():
    # least-privilege monotonic: cashier ⊆ supervisor ⊆ manager
    fails = []
    if not A.capabilities_for("cashier") <= A.capabilities_for("supervisor"):
        fails.append("cashier not subset of supervisor")
    if not A.capabilities_for("supervisor") <= A.capabilities_for("manager"):
        fails.append("supervisor not subset of manager")
    return fails


def t_scope():
    fails = []
    # same company+branch -> ok
    if not A.check_scope(1, 5, 1, 5).ok:
        fails.append("same scope rejected")
    # cross company -> company_mismatch
    v = A.check_scope(1, 5, 2, 5)
    if v.ok or v.reason != A.COMPANY_MISMATCH:
        fails.append(("cross-company not blocked", v))
    # cross branch -> branch_mismatch
    v = A.check_scope(1, 5, 1, 9)
    if v.ok or v.reason != A.BRANCH_MISMATCH:
        fails.append(("cross-branch not blocked", v))
    # None target -> allowed
    if not A.check_scope(1, 5, None, None).ok:
        fails.append("unscoped rejected")
    # explicit allow_cross -> ok
    if not A.check_scope(1, 5, 2, 9, allow_cross_company=True, allow_cross_branch=True).ok:
        fails.append("explicit cross not allowed")
    return fails


def t_replay_window():
    fails = []
    now = 1_000_000.0
    if not A.replay_window_ok(now - 100, now, 300):
        fails.append("fresh rejected")
    if A.replay_window_ok(now - 400, now, 300):
        fails.append("expired accepted")
    if A.replay_window_ok(now + 400, now, 300):
        fails.append("far-future accepted")
    if A.replay_window_ok("garbage", now, 300):
        fails.append("garbage accepted")
    return fails


def t_signature_compare():
    fails = []
    if not A.signatures_equal("abc123", "abc123"):
        fails.append("equal rejected")
    if A.signatures_equal("abc123", "abc124"):
        fails.append("different accepted")
    if A.signatures_equal("", "x") or A.signatures_equal(None, "x"):
        fails.append("empty accepted")
    return fails


def t_property_default_deny():
    """No (role, capability) is granted unless explicitly in ROLE_CAPS."""
    rng = random.Random(3)
    roles = list(A.ROLE_CAPS.keys()) + ["ghost", None]
    caps = list(A.ALL_CAPABILITIES) + ["made.up", "orders.delete"]
    fails = []
    for _ in range(5000):
        role = rng.choice(roles)
        cap = rng.choice(caps)
        granted = A.can(role, cap)
        truth = cap in A.ROLE_CAPS.get(role, frozenset()) and cap in A.ALL_CAPABILITIES
        if granted != truth:
            fails.append((role, cap, granted, truth))
            break
    return fails


ALL = [
    ("capability_matrix", t_capability_matrix),
    ("role_supersets", t_role_supersets),
    ("scope", t_scope),
    ("replay_window", t_replay_window),
    ("signature_compare", t_signature_compare),
    ("property_default_deny", t_property_default_deny),
]


def run_mutations():
    results = {}
    real_can, real_scope, real_win, real_sig = A.can, A.check_scope, A.replay_window_ok, A.signatures_equal

    def run(fn):
        return bool(t_capability_matrix() or t_scope() or t_replay_window() or t_signature_compare())

    # permission removed (always allow)
    A.can = lambda role, cap: True
    results["permission_removed"] = bool(t_capability_matrix() or t_property_default_deny())
    A.can = real_can
    # company/branch validation removed (scope always ok)
    A.check_scope = lambda *a, **k: A.ScopeVerdict(True, A.OK)
    results["scope_removed"] = bool(t_scope())
    A.check_scope = real_scope
    # timestamp/replay window ignored (always ok)
    A.replay_window_ok = lambda *a, **k: True
    results["timestamp_ignored"] = bool(t_replay_window())
    A.replay_window_ok = real_win
    # signature verification removed (always equal)
    A.signatures_equal = lambda *a, **k: True
    results["signature_removed"] = bool(t_signature_compare())
    A.signatures_equal = real_sig
    return results


def run_all():
    return {name: fn() for name, fn in ALL}


if __name__ == "__main__":
    results = run_all()
    total = sum(len(v) for v in results.values())
    print("Authorization/integrity tests")
    for name, fails in results.items():
        print(f"  {name:26s} {'PASS ✓' if not fails else f'FAIL ✗ {fails[:1]}'}")
    muts = run_mutations()
    print("mutation resistance (True = broken rule detected):")
    for name, caught in muts.items():
        print(f"  {name:22s} {'CAUGHT ✓' if caught else 'MISSED ✗'}")
    ok = total == 0 and all(muts.values())
    print("RESULT:", "PASS ✓" if ok else "FAIL ✗")
    raise SystemExit(0 if ok else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestAuthz(TransactionCase):
        def test_rules(self):
            failures = {k: v for k, v in run_all().items() if v}
            self.assertEqual(failures, {}, f"authz rules violated: {failures}")

        def test_mutation_resistance(self):
            self.assertTrue(all(run_mutations().values()), "authz mutation not caught")
except Exception:
    pass
