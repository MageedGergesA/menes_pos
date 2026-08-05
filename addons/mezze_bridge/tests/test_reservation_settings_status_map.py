"""DESIGN-P3B.5 — deterministic Reservation + Settings/governance status guards.

Reservation/waitlist state -> canonical semantic (not raw hex), and the governance
invariants the P3B.5 spec requires: Locked is NOT an error (not danger), Bounded is
NOT warning, Disabled != Locked, and Hidden settings stay hidden. Parses the shipped
prototype (static/pos.html) + the design engine (static/mezze-design.js). Runs
standalone (python3) and under Odoo (mezze_invariants).
"""

import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_POS = os.path.join(_ROOT, 'static', 'pos.html')
_ENGINE = os.path.join(_ROOT, 'static', 'mezze-design.js')

_FAMILY = {
    'ok': 'success', 'success': 'success',
    'warn': 'warning', 'warning': 'warning', 'paused': 'warning',
    'accent': 'info', 'violet': 'info', 'info': 'info', 'active': 'info',
    'danger': 'danger', 'crit': 'danger',
    'neutral': 'neutral', 'offline': 'neutral', 'not-tested': 'neutral',
}

# frozen Reservation state -> canonical variant
_RSV_EXPECT = {
    'booked': 'info', 'confirmed': 'info', 'arrived': 'active', 'waiting': 'warning',
    'late': 'danger', 'seated': 'success', 'cancelled': 'neutral',
    'no_show': 'danger', 'done': 'neutral',
}


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _rsv_map(src):
    m = re.search(
        r"\{booked:'(\w+)',confirmed:'(\w+)',arrived:'(\w+)',waiting:'(\w+)',late:'(\w+)',"
        r"seated:'(\w+)',cancelled:'(\w+)',no_show:'(\w+)',done:'(\w+)'\}\[r\.state\]\|\|'(\w+)'",
        src)
    if not m:
        return None, None
    keys = ['booked', 'confirmed', 'arrived', 'waiting', 'late', 'seated',
            'cancelled', 'no_show', 'done']
    return dict(zip(keys, m.groups()[:9])), m.group(10)


def run_checks():
    failures = []
    pos = _read(_POS)
    eng = _read(_ENGINE)

    # --- Reservation state -> canonical variant ---
    rmap, rfallback = _rsv_map(pos)
    if rmap is None:
        failures.append(('reservation_map_not_found',))
    else:
        for state, want in _RSV_EXPECT.items():
            if rmap.get(state) != want:
                failures.append(('reservation_state_semantic', state, rmap.get(state), want))
        if rfallback != 'neutral':
            failures.append(('reservation_unknown_fallback', rfallback))
        # the operationally-distinct trio must not collapse to one family
        fam = lambda s: _FAMILY.get(rmap.get(s, ''), '?')
        if len({fam('arrived'), fam('waiting'), fam('seated')}) != 3:
            failures.append(('arrived_waiting_seated_not_distinct',
                             fam('arrived'), fam('waiting'), fam('seated')))
        if fam('cancelled') == fam('no_show'):          # Cancelled != No-show
            failures.append(('cancelled_equals_no_show', fam('cancelled')))

    # --- Settings / governance semantics (mezze-design.js) ---
    def rule(sel):
        m = re.search(re.escape(sel) + r'\{([^}]*)\}', eng)
        return m.group(1) if m else None

    locked = rule('.admin-badge.lock,.admin-badge.locked')
    if not locked or '--mz-danger' in locked:           # Locked is NOT an error
        failures.append(('locked_is_danger_or_missing', locked))
    if locked and 'border' not in locked:               # Locked distinguished structurally
        failures.append(('locked_no_border', locked))

    bounded = rule('.admin-badge.bounded')
    if not bounded or '--mz-warn' in bounded:           # Bounded is NOT warning
        failures.append(('bounded_is_warning_or_missing', bounded))

    pref = rule('.admin-badge.pref')                    # Disabled/unavailable
    if not pref or '--mz-warn' in pref:                 # not a warning either
        failures.append(('disabled_is_warning_or_missing', pref))
    # Disabled (dashed) must differ from Locked (solid) — not identical treatment
    if pref and locked and pref == locked:
        failures.append(('disabled_equals_locked',))
    if pref and 'dashed' not in pref:
        failures.append(('disabled_not_dashed', pref))

    # Hidden settings must stay hidden (early return in the catalog builder)
    if "d.status === 'hidden'" not in eng or 'return' not in eng:
        failures.append(('hidden_not_filtered',))

    return failures


if __name__ == '__main__':
    fails = run_checks()
    print("Reservation + Settings status->semantic checks")
    print("  failures:", fails if fails else "none")
    print("RESULT:", "PASS" if not fails else "FAIL")
    raise SystemExit(0 if not fails else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestReservationSettingsStatusMap(TransactionCase):
        def test_reservation_and_governance_semantics(self):
            self.assertEqual(
                run_checks(), [],
                "Reservation/Settings status->semantic mapping drifted from canonical")
except Exception:  # Odoo not present
    pass
