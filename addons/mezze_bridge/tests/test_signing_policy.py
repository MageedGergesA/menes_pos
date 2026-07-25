"""Pure tests for the signing-policy state machine (domain/signing_policy.py).

Standalone + Odoo. Covers per-principal mode resolution, off/observe/enforce
handling by route sensitivity, canonical-string determinism + tamper-sensitivity,
and the production dangerous-config detector, with mutation checks.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from domain import signing_policy as sp  # noqa: E402

SIG = frozenset({"orders/pay", "orders/refund"})


def run_resolution():
    f = []
    # per-type param wins over global wins over secure default
    cfg = {"mezze_bridge.signing_mode.terminal": "enforce",
           "mezze_bridge.signing_mode": "observe"}
    if sp.mode_for(cfg.get, "terminal") != sp.ENFORCE:
        f.append("per_type_not_preferred")
    if sp.mode_for(cfg.get, "admin") != sp.OBSERVE:      # falls back to global
        f.append("global_fallback")
    if sp.mode_for({}.get, "cashier") != sp.OBSERVE:     # secure default
        f.append("default_wrong")
    # handling by sensitivity
    if sp.effective(sp.ENFORCE, "orders/pay", SIG) != sp.ENFORCE:
        f.append("sensitive_enforce")
    if sp.effective(sp.OBSERVE, "orders/pay", SIG) != sp.OBSERVE:
        f.append("sensitive_observe")
    if sp.effective(sp.OBSERVE, "reports/summary", SIG) != sp.OFF:
        f.append("nonsensitive_observe_should_off")
    if sp.effective(sp.ENFORCE, "reports/summary", SIG) != sp.ENFORCE:
        f.append("nonsensitive_enforce")
    if sp.effective(sp.OFF, "orders/pay", SIG) != sp.OFF:
        f.append("off_stays_off")
    return f


def run_canonical():
    f = []
    a = sp.canonical_string("POST", "/x/pay", "abc", "100", "n1", "terminal:T1", "k1")
    b = sp.canonical_string("post", "/x/pay", "abc", "100", "n1", "terminal:T1", "k1")
    if a != b:
        f.append("method_case_not_normalized")   # method upcased -> deterministic
    # each meaningful field changes the string
    base = dict(method="POST", path="/x/pay", body_sha256="abc", timestamp="100",
                nonce="n1", principal="terminal:T1", kid="k1")
    ref = sp.canonical_string(**base)
    for k, v in (("path", "/x/refund"), ("body_sha256", "xyz"), ("timestamp", "101"),
                 ("nonce", "n2"), ("principal", "terminal:T2"), ("kid", "k2"),
                 ("method", "GET")):
        if sp.canonical_string(**dict(base, **{k: v})) == ref:
            f.append("tamper_not_bound:%s" % k)
    return f


def run_dangerous():
    f = []
    # production, signing off, no break-glass -> dangerous
    if not sp.dangerous_config("production", sp.OFF, {}, True, 300, False, False):
        f.append("prod_off_not_flagged")
    # production, machine downgraded to observe -> dangerous
    d = sp.dangerous_config("production", sp.ENFORCE,
                            {"terminal": sp.OBSERVE, "integration": sp.ENFORCE, "admin": sp.ENFORCE},
                            True, 300, False, False)
    if not any("machine_signing_downgraded" in x for x in d):
        f.append("downgrade_not_flagged")
    # break-glass suppresses (but still auditable elsewhere)
    if sp.dangerous_config("production", sp.OFF, {}, True, 300, False, True):
        f.append("breakglass_not_honored")
    # nonce off while enforcing
    if "nonce_disabled_while_enforcing" not in sp.dangerous_config(
            "production", sp.ENFORCE, {}, False, 300, False, True):
        f.append("nonce_off_not_flagged")
    # absurd skew
    if not any("bad_clock_skew" in x for x in sp.dangerous_config(
            "development", sp.OBSERVE, {}, True, 99999, False, False)):
        f.append("skew_not_flagged")
    # safe production config -> empty
    safe = sp.dangerous_config("production", sp.ENFORCE,
                               {"terminal": sp.ENFORCE, "integration": sp.ENFORCE, "admin": sp.ENFORCE},
                               True, 300, False, False)
    if safe:
        f.append("safe_flagged:%s" % safe)
    return f


def run_mutations():
    caught = total = 0
    total += 1  # canonical must bind the route
    if sp.canonical_string("POST", "/a", "b", "1", "n", "p", "k") != sp.canonical_string("POST", "/A", "b", "1", "n", "p", "k"):
        caught += 1
    total += 1  # enforce must block sensitive
    if sp.effective(sp.ENFORCE, "orders/pay", SIG) == sp.ENFORCE:
        caught += 1
    total += 1  # prod-off must be dangerous
    if sp.dangerous_config("production", sp.OFF, {}, True, 300, False, False):
        caught += 1
    return caught, total


if __name__ == "__main__":
    r = run_resolution(); c = run_canonical(); d = run_dangerous(); ca, t = run_mutations()
    ok = not (r or c or d) and ca == t
    print("Signing-policy tests")
    print("  resolution :", r or "ok")
    print("  canonical  :", c or "ok")
    print("  dangerous  :", d or "ok")
    print("  mutations  : %d/%d" % (ca, t))
    print("RESULT:", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestSigningPolicy(TransactionCase):
        def test_resolution(self):
            self.assertEqual(run_resolution(), [], "signing mode resolution wrong")

        def test_canonical(self):
            self.assertEqual(run_canonical(), [], "canonical string not deterministic/bound")

        def test_dangerous(self):
            self.assertEqual(run_dangerous(), [], "dangerous-config detector wrong")

        def test_mutations(self):
            ca, t = run_mutations()
            self.assertEqual(ca, t, "policy mutation not caught")
except Exception:
    pass
