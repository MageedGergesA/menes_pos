"""Structural enforcement of the P6.2 target-scope classification (Phase 1).

Fails if a protected route is unclassified, if a Category A (target-record) route
lacks a (target_model, id_param) resolver tuple, or if the registry drifts from the
actual protected surface.
"""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)
from domain import authz as A  # noqa: E402
from domain import route_scope as R  # noqa: E402


def _introspect():
    spec = importlib.util.spec_from_file_location(
        'cov_rs', os.path.join(_HERE, 'test_endpoint_coverage.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.introspect_routes()


def run_checks():
    f = []
    protected = set(A.ENDPOINT_CAPABILITY)
    classified = set(R.ROUTE_SCOPE)
    for eid in sorted(protected - classified):
        f.append(('unclassified_protected_route', eid))
    for eid in sorted(classified - protected):
        f.append(('classified_but_not_protected', eid))
    # every route in the registry that actually exists as a route
    routes = set(_introspect())
    for eid in classified:
        if eid not in routes:
            f.append(('registry_ghost_route', eid))
    # Category A routes must declare a resolver (model, id_param)
    for eid, v in R.ROUTE_SCOPE.items():
        if v[0] == R.A and (len(v) != 3 or not v[1] or not v[2]):
            f.append(('A_route_missing_resolver', eid))
        if v[0] != R.A and len(v) != 1:
            f.append(('non_A_route_has_resolver_tuple', eid))
    return f


if __name__ == '__main__':
    fails = run_checks()
    from collections import Counter
    cats = Counter(v[0] for v in R.ROUTE_SCOPE.values())
    print('Route target-scope classification')
    print('  categories:', dict(cats), 'total', sum(cats.values()))
    print('  failures  :', fails or 'none')
    print('RESULT:', 'PASS' if not fails else 'FAIL')
    raise SystemExit(0 if not fails else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged('post_install', '-at_install', 'mezze_invariants')
    class TestRouteScope(TransactionCase):
        def test_every_protected_route_classified(self):
            self.assertEqual(run_checks(), [], 'route target-scope classification incomplete')
except Exception:
    pass
