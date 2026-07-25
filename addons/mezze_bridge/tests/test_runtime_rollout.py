"""Runtime proof that the canonical gate is LIVE on the migrated endpoints.

Tagged ``mezze_runtime``. Real HTTP in enforce mode against endpoints that used
to run on legacy auth (w1 finance/reports, hardware drawer). Proves the ONE gate
now authenticates + capability-checks them: least-privilege denials, admin pass,
missing/wrong token — the same mechanism already proven exhaustively on
/orders/pay (test_runtime_security), here shown active across controllers.
"""

import json

from odoo.tests import common, tagged

W1 = '/mezze/w1'
HW = '/mezze/hardware'

_SEC_ERRORS = {'authentication_required', 'authentication_failed', 'permission_denied',
               'branch_mismatch', 'company_mismatch', 'terminal_mismatch', 'terminal_revoked'}


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestSecurityRollout(common.HttpCase):

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'rollout-shared-token'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'enforce')
        ICP.set_param('mezze_bridge.env_profile', 'development')  # baseline: shared-admin allowed
        Cash = self.env['mezze.cashier']
        # cashier: no finance.read, no hardware.drawer | supervisor: +hardware.drawer
        # | manager: +finance.read +hardware.drawer  (per authz.ROLE_CAPS)
        self.cashier = Cash.create({'name': 'Cash', 'code': 'RC1', 'role': 'cashier', 'active': True})
        self.supervisor = Cash.create({'name': 'Sup', 'code': 'RS1', 'role': 'supervisor', 'active': True})
        self.manager = Cash.create({'name': 'Mgr', 'code': 'RM1', 'role': 'manager', 'active': True})
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open(path, data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=60)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    # -- authentication (baseline, enforced everywhere) -----------------------
    def test_missing_token_denied(self):
        st, b = self._post(W1 + '/reports/summary', {})
        self.assertEqual(b.get('error'), 'authentication_required')

    def test_wrong_token_denied(self):
        st, b = self._post(W1 + '/reports/summary', {'token': 'nope'})
        self.assertEqual(b.get('error'), 'authentication_failed')

    # -- capability least-privilege (per role) --------------------------------
    def test_cashier_denied_finance_endpoint(self):
        st, b = self._post(W1 + '/gl/summary', {'token': self.shared, 'cashier_id': self.cashier.id})
        self.assertEqual(b.get('error'), 'permission_denied')

    def test_cashier_denied_hardware_drawer(self):
        st, b = self._post(HW + '/drawer/open', {'token': self.shared, 'cashier_id': self.cashier.id})
        self.assertEqual(b.get('error'), 'permission_denied')

    def test_supervisor_denied_finance_endpoint(self):
        # supervisor lacks finance.read
        st, b = self._post(W1 + '/gl/summary', {'token': self.shared, 'cashier_id': self.supervisor.id})
        self.assertEqual(b.get('error'), 'permission_denied')

    def test_supervisor_allowed_hardware_drawer(self):
        # supervisor HAS hardware.drawer -> gate passes; endpoint then fails on a
        # business condition (no configured drawer printer), NOT on security.
        st, b = self._post(HW + '/drawer/open', {'token': self.shared, 'cashier_id': self.supervisor.id})
        self.assertNotIn(b.get('error'), _SEC_ERRORS)

    def test_manager_allowed_finance_endpoint(self):
        st, b = self._post(W1 + '/gl/summary', {'token': self.shared, 'cashier_id': self.manager.id})
        self.assertNotIn(b.get('error'), _SEC_ERRORS)

    def test_shared_admin_allowed(self):
        st, b = self._post(W1 + '/gl/summary', {'token': self.shared})
        self.assertNotIn(b.get('error'), _SEC_ERRORS)
