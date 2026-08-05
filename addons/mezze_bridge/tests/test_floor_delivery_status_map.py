"""DESIGN-P3B.4 / P3B.4A — deterministic Floor + Delivery status->semantic guards.

Asserts the *design-layer* state->canonical-semantic mapping (not raw hex), and the
cross-surface invariant that a shared business meaning resolves to the same canonical
semantic FAMILY on KDS and Delivery. Parses the shipped prototype (static/pos.html),
which is where these maps live as JS/CSS. Runs standalone (python3) and under Odoo
(mezze_invariants).

Guards specifically:
  * Delivery stage badge -> exact canonical variant, with unknown -> neutral fallback.
  * Floor Occupied is NOT brand-as-status (migrated off --accent to canonical --info),
    and Bill-requested carries a non-colour text label (not colour/motion-only).
  * KDS.ready == Delivery.ready (success) and KDS.preparing == Delivery.preparing (info)
    by canonical family.
"""

import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_POS = os.path.join(_ROOT, 'static', 'pos.html')

# canonical family normalisation (compat aliases collapse to their rendered family)
_FAMILY = {
    'ok': 'success', 'success': 'success',
    'warn': 'warning', 'warning': 'warning', 'paused': 'warning',
    'accent': 'info', 'violet': 'info', 'info': 'info', 'active': 'info',
    'danger': 'danger', 'crit': 'danger',
    'neutral': 'neutral', 'offline': 'neutral', 'not-tested': 'neutral',
}

# intended Delivery stage -> canonical variant (frozen for this pass)
_DELIVERY_EXPECT = {
    'accepted': 'info', 'preparing': 'info', 'ready': 'success', 'assigned': 'info',
    'out_for_delivery': 'active', 'delivered': 'neutral',
    'cancelled': 'danger', 'rejected': 'danger', 'failed': 'danger',
}


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _delivery_map(src):
    m = re.search(
        r"mz-status--'\+\(\{"
        r"accepted:'(\w+)',preparing:'(\w+)',ready:'(\w+)',assigned:'(\w+)',"
        r"out_for_delivery:'(\w+)',delivered:'(\w+)',cancelled:'(\w+)',"
        r"rejected:'(\w+)',failed:'(\w+)'\}\[v\.state\]\|\|'(\w+)'\)",
        src)
    if not m:
        return None, None
    keys = ['accepted', 'preparing', 'ready', 'assigned', 'out_for_delivery',
            'delivered', 'cancelled', 'rejected', 'failed']
    return dict(zip(keys, m.groups()[:9])), m.group(10)  # (map, fallback)


def _kds_map(src):
    m = re.search(
        r"\{fired:'(\w+)',accepted:'(\w+)',preparing:'(\w+)',ready:'(\w+)',served:'(\w+)'\}",
        src)
    if not m:
        return None
    return dict(zip(['fired', 'accepted', 'preparing', 'ready', 'served'], m.groups()))


def run_checks():
    failures = []
    src = _read(_POS)

    # --- Delivery stage -> canonical variant ---
    dmap, dfallback = _delivery_map(src)
    if dmap is None:
        failures.append(('delivery_map_not_found',))
    else:
        for state, want in _DELIVERY_EXPECT.items():
            got = dmap.get(state)
            if got != want:
                failures.append(('delivery_stage_semantic', state, got, want))
        if dfallback != 'neutral':          # unknown stage must fall back to neutral
            failures.append(('delivery_unknown_fallback', dfallback))

    # --- Floor: Occupied is NOT brand-as-status; Bill has a text label ---
    if re.search(r'\.table\.oc \.tabletop\{background:var\(--accent\)', src):
        failures.append(('floor_occupied_still_brand',))
    if not re.search(r'\.table\.oc \.tabletop\{background:var\(--info-soft\)', src):
        failures.append(('floor_occupied_not_info',))
    if not re.search(r'\.table\.bl \.tabletop\{[^}]*var\(--warn\)', src):
        failures.append(('floor_bill_not_warning',))
    # bill-requested must carry a non-colour label (EN 'BILL' / AR label)
    if "st==='bl')meta=" not in src or 'BILL' not in src:
        failures.append(('floor_bill_label_missing',))

    # --- Cross-surface: KDS vs Delivery shared meanings (by family) ---
    kmap = _kds_map(src)
    if kmap is None:
        failures.append(('kds_map_not_found',))
    elif dmap is not None:
        for shared in ('ready', 'preparing'):
            kf = _FAMILY.get(kmap.get(shared, ''), '?')
            df = _FAMILY.get(dmap.get(shared, ''), '?')
            if kf != df or kf == '?':
                failures.append(('cross_surface_mismatch', shared, kf, df))
        # ready must be success, preparing must be info (frozen expectation)
        if _FAMILY.get(dmap.get('ready', '')) != 'success':
            failures.append(('ready_not_success', dmap.get('ready')))
        if _FAMILY.get(dmap.get('preparing', '')) != 'info':
            failures.append(('preparing_not_info', dmap.get('preparing')))

    return failures


if __name__ == '__main__':
    fails = run_checks()
    print("Floor + Delivery status->semantic checks")
    print("  failures:", fails if fails else "none")
    print("RESULT:", "PASS" if not fails else "FAIL")
    raise SystemExit(0 if not fails else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestFloorDeliveryStatusMap(TransactionCase):
        def test_floor_delivery_status_semantics(self):
            self.assertEqual(
                run_checks(), [],
                "Floor/Delivery status->semantic mapping drifted from canonical")
except Exception:  # Odoo not present
    pass
