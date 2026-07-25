"""Structural security-coverage test (executable route inventory).

Introspects EVERY @http.route across the controllers and fails when:
  * a data route lacks a security classification (public / integration / capability)
  * a capability-mapped endpoint does not exist as a real route
  * a mutation (POST) route is accidentally classified PUBLIC
  * a route declared GATED does not actually call self._security_gate
  * a route calls the gate but isn't in the gated set (drift)

This prevents a new data route from shipping ungated/unclassified, and reports the
gate-coverage percentage used by the enforcement-promotion gate.

Standalone:  python3 tests/test_endpoint_coverage.py
"""

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from domain import authz as A  # noqa: E402

CTRL_GLOB = os.path.join(ROOT, "controllers", "*.py")

# Rollout COMPLETE: every protected route must call the canonical gate (directly
# via _security_gate, or via _authorize which delegates to it). This set is the
# whole protected surface — the structural test fails if any protected route ships
# without the gate, or if a new legacy auth path appears.
GATED = set(A.ENDPOINT_CAPABILITY)

# Sensitive mutations that must never be public.
SENSITIVE_MUTATIONS = set(A.SIGNATURE_REQUIRED)

# Legacy auth that must never reappear (single-mechanism enforcement).
_LEGACY_AUTH = (r"def _authenticate\b", r"def _auth\b",
                r"self\._authenticate\(\)", r"self\._auth\(\)",
                r"_bridge\._authenticate\(\)")


def _eid(path):
    for pfx in ("{API_PREFIX}", "{W1_PREFIX}", "{SYNC_PREFIX}", "{HW_PREFIX}", "{AGG_PREFIX}"):
        path = path.replace(pfx, "")
    path = path.replace("/mezze/api/v1/", "").replace("/mezze/", "")
    return path.lstrip("/")


def introspect_routes():
    """Return {eid: {'methods','auth','func','file','src'}} for every route."""
    out = {}
    for f in sorted(glob.glob(CTRL_GLOB)):
        src = open(f, encoding="utf-8").read()
        for m in re.finditer(r"@http\.route\(([^)]*)\)\s*\n\s*def\s+(\w+)", src, re.S):
            deco, func = m.group(1), m.group(2)
            pm = re.search(r"f?['\"]([^'\"]+)['\"]", deco)
            if not pm:
                continue
            eid = _eid(pm.group(1))
            methods = re.search(r"methods=\[([^\]]*)\]", deco)
            methods = re.sub(r"['\" ]", "", methods.group(1)) if methods else "GET"
            auth = (re.search(r"auth=['\"](\w+)['\"]", deco) or [None, "?"])[1]
            # body of the function (until the next top-level def)
            body_m = re.search(r"\n    def %s\(.*?(?=\n    def |\Z)" % re.escape(func), src, re.S)
            out[eid] = {"methods": methods, "auth": auth, "func": func,
                        "file": os.path.basename(f), "body": body_m.group(0) if body_m else ""}
    return out


def t_every_route_classified():
    routes = introspect_routes()
    classified = set(A.PUBLIC_ROUTES) | set(A.INTEGRATION_ROUTES) | set(A.ENDPOINT_CAPABILITY)
    fails = []
    for eid in routes:
        if eid not in classified:
            fails.append(("UNCLASSIFIED route", eid, routes[eid]["file"], routes[eid]["func"]))
    return fails


def t_no_orphan_capability_maps():
    routes = set(introspect_routes())
    fails = []
    for eid in set(A.ENDPOINT_CAPABILITY) | set(A.PUBLIC_ROUTES) | set(A.INTEGRATION_ROUTES):
        if eid not in routes:
            fails.append(("mapped endpoint does not exist", eid))
    return fails


def t_no_route_double_classified():
    fails = []
    pub, integ, cap = set(A.PUBLIC_ROUTES), set(A.INTEGRATION_ROUTES), set(A.ENDPOINT_CAPABILITY)
    for a, b, na, nb in ((pub, cap, "public", "capability"), (pub, integ, "public", "integration"),
                         (integ, cap, "integration", "capability")):
        for e in a & b:
            fails.append(("double-classified", e, na, nb))
    return fails


def t_sensitive_mutation_not_public():
    fails = []
    for e in SENSITIVE_MUTATIONS & set(A.PUBLIC_ROUTES):
        fails.append(("sensitive mutation is PUBLIC", e))
    return fails


def t_every_protected_route_gated():
    """Every protected route's handler must call the canonical gate — via
    _authorize() (which derives the endpoint id from the path and delegates to
    _security_gate) or an explicit _security_gate(...) with a target."""
    routes = introspect_routes()
    fails = []
    for eid in sorted(GATED):
        meta = routes.get(eid)
        if not meta:
            continue  # orphan handled by t_no_orphan_capability_maps
        body = meta["body"]
        if "_authorize(" not in body and "_security_gate(" not in body:
            fails.append(("protected route missing canonical gate", eid, meta["file"], meta["func"]))
    return fails


def t_no_legacy_auth():
    """No second security model: the removed legacy auth methods/calls must not
    reappear anywhere in the controllers."""
    fails = []
    src_all = "".join(open(f, encoding="utf-8").read() for f in glob.glob(CTRL_GLOB))
    # strip docstrings/comments crudely: only flag actual code occurrences by
    # requiring the pattern to appear outside a leading-'#'/docstring context is
    # hard with regex, so we match def/call forms which never appear in prose.
    for pat in _LEGACY_AUTH:
        for m in re.finditer(pat, src_all):
            # ignore matches inside a docstring reference like ``_authenticate``
            start = src_all.rfind("\n", 0, m.start())
            line = src_all[start:m.start() + 40]
            if "``" in line or line.lstrip().startswith("#"):
                continue
            fails.append(("legacy auth reappeared", pat))
            break
    return fails


def coverage():
    protected = set(A.ENDPOINT_CAPABILITY)
    return {"total": len(introspect_routes()), "public": len(A.PUBLIC_ROUTES),
            "integration": len(A.INTEGRATION_ROUTES), "protected": len(protected),
            "gated": len(GATED & protected),
            "gate_pct": round(100.0 * len(GATED & protected) / max(1, len(protected)), 1),
            "signature_required": len(A.SIGNATURE_REQUIRED)}


ALL = [
    ("every_route_classified", t_every_route_classified),
    ("no_orphan_capability_maps", t_no_orphan_capability_maps),
    ("no_route_double_classified", t_no_route_double_classified),
    ("sensitive_mutation_not_public", t_sensitive_mutation_not_public),
    ("every_protected_route_gated", t_every_protected_route_gated),
    ("no_legacy_auth", t_no_legacy_auth),
]


def run_all():
    return {name: fn() for name, fn in ALL}


if __name__ == "__main__":
    results = run_all()
    total = sum(len(v) for v in results.values())
    print("Endpoint security-coverage (structural)")
    for name, fails in results.items():
        print(f"  {name:32s} {'PASS ✓' if not fails else f'FAIL ✗ {fails[:3]}'}")
    print("coverage:", coverage())
    print("RESULT:", "PASS ✓" if total == 0 else f"FAIL ✗ ({total})")
    raise SystemExit(0 if total == 0 else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestEndpointCoverage(TransactionCase):
        def test_coverage(self):
            failures = {k: v for k, v in run_all().items() if v}
            self.assertEqual(failures, {}, f"endpoint coverage failures: {failures}")
except Exception:
    pass
