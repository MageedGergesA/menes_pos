"""Structural enforcement for the completed authorization rollout (Phase 5).

Repository-wide guards that FAIL if a second security model or a manual
authorization check is (re)introduced:

  * legacy auth methods/calls (`_authenticate`, `_auth`) reappear
  * an Odoo-native group check (`has_group`) is used for endpoint access
  * a protected route ships without the canonical gate
  * the canonical gate stops being enforcing-by-default

Runs standalone and under Odoo.
"""

import glob
import importlib.util
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_CTRL = glob.glob(os.path.join(_ROOT, "controllers", "*.py"))


def _load_coverage():
    spec = importlib.util.spec_from_file_location(
        "cov_mod", os.path.join(_HERE, "test_endpoint_coverage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _code_lines(src):
    """Yield lines that are not blank, not comments, and not docstring prose
    (a crude filter: skip lines whose stripped form starts with # or contains the
    rst ``code`` backticks used in our docstrings)."""
    for ln in src.splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or "``" in ln:
            continue
        yield ln


def run_checks():
    f = []
    cov = _load_coverage()

    # 1) no legacy auth model anywhere
    for path in _CTRL:
        for ln in _code_lines(open(path, encoding="utf-8").read()):
            if re.search(r"def _authenticate\b|def _auth\b|self\._authenticate\(\)|"
                         r"self\._auth\(\)|_bridge\._authenticate\(\)", ln):
                f.append(("legacy_auth", os.path.basename(path), ln.strip()[:60]))

    # 2) no Odoo-native group check used as an access gate in a controller
    for path in _CTRL:
        for ln in _code_lines(open(path, encoding="utf-8").read()):
            if "has_group(" in ln:
                f.append(("manual_group_check", os.path.basename(path), ln.strip()[:60]))

    # 3) every protected route calls the canonical gate (delegate)
    f += [("ungated_protected",) + tuple(x[1:]) for x in cov.t_every_protected_route_gated()]
    f += [("legacy_auth_regex",) + tuple(x[1:]) for x in cov.t_no_legacy_auth()]

    # 4) the gate is enforcing-by-default (rollout complete, not observe)
    main = open(os.path.join(_ROOT, "controllers", "main.py"), encoding="utf-8").read()
    if "get_param('mezze_bridge.api_security') or 'enforce'" not in main:
        f.append(("gate_not_enforce_by_default",))

    return f


if __name__ == "__main__":
    fails = run_checks()
    print("Security-rollout structural guards")
    print("  failures:", fails if fails else "none")
    print("RESULT:", "PASS" if not fails else "FAIL")
    raise SystemExit(0 if not fails else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestSecurityRollout(TransactionCase):
        def test_structural(self):
            self.assertEqual(run_checks(), [], "security rollout structural guards failed")
except Exception:
    pass
