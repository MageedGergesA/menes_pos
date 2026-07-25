"""P1 — go-live readiness: the config validator runs and returns a structured,
launch-blocking report; the hardened status-token lifecycle is enforced.

RC2/D-2: uses the hermetic fixture layer — no ambient POS/config/session data.
"""
from odoo.tests import tagged

from .common import MezzePosCase


@tagged('post_install', '-at_install', 'mezze_invariants')
class TestGoLiveValidator(MezzePosCase):
    fixture_profile = 'POS'

    def test_validator_runs_structured(self):
        r = self.env['mezze.golive.validator'].run()
        self.assertIn(r['overall'], ('PASS', 'WARNING', 'FAIL'))
        self.assertGreaterEqual(r['total'], 10)
        names = {c['name'] for c in r['checks']}
        for expect in ('master_key_present', 'status_token_ttl', 'shared_admin_disabled',
                       'pos_config_present', 'payment_methods', 'settings_catalog'):
            self.assertIn(expect, names)
        for c in r['checks']:
            self.assertIn(c['status'], ('PASS', 'WARNING', 'FAIL', 'N/A'))

    def test_report_text(self):
        txt = self.env['mezze.golive.validator'].report_text()
        self.assertIn('MEZZE GO-LIVE CONFIG VALIDATOR', txt)
        self.assertIn('status_token_ttl', txt)


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestStatusTokenLifecycle(MezzePosCase):
    fixture_profile = 'POS'

    def _order(self):
        return self.create_order_in_test_session(channel='pickup')

    def test_hash_stored_not_raw(self):
        o = self._order()
        raw = o._mezze_ensure_status_token()
        self.assertEqual(len(raw), 32)
        self.assertNotEqual(o.mezze_status_token, raw)     # only the hash is stored
        self.assertTrue(self.env['pos.order']._mezze_resolve_status_token(raw))

    def test_expiry_and_revocation(self):
        from datetime import timedelta
        from odoo import fields
        o = self._order()
        raw = o._mezze_ensure_status_token()
        # expired token no longer resolves
        o.mezze_status_expiry = fields.Datetime.now() - timedelta(minutes=1)
        self.assertFalse(self.env['pos.order']._mezze_resolve_status_token(raw))
        # fresh token, then revoke
        o2 = self._order()
        raw2 = o2._mezze_ensure_status_token()
        self.assertTrue(self.env['pos.order']._mezze_resolve_status_token(raw2))
        o2.mezze_revoke_status_token()
        self.assertFalse(self.env['pos.order']._mezze_resolve_status_token(raw2))
