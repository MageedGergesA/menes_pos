"""Pilot emergency-access proof (P6.5 §7). Tagged mezze_runtime.

Model: activation requires reason + approver, expiry capped at 1h, revoke +
auto-expire. HTTP: normal shared-admin rejected in production; a live activation
admits the shared token but SCOPED to its branch + narrowed to its capability list.
"""
import json
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import common, tagged

BASE = '/mezze/api/v1'


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestEmergencyModel(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.EA = self.env['mezze.emergency.access']
        self.cfg = self.env['pos.config'].search([], limit=1)

    def test_activation_requires_reason_and_approver(self):
        with self.assertRaises(UserError):
            self.EA.activate(reason=None, approver='mgr')
        with self.assertRaises(UserError):
            self.EA.activate(reason='incident', approver=None)

    def test_expiry_capped_at_one_hour(self):
        rec = self.EA.activate(reason='incident', approver='mgr', hours=8,
                               branch_id=self.cfg.id, capabilities='orders.read')
        span = (rec.expires_at - rec.activated_at).total_seconds()
        self.assertLessEqual(span, 3601)          # capped at 1h
        self.assertTrue(self.EA.is_active())

    def test_revoke_and_expire(self):
        rec = self.EA.activate(reason='x', approver='mgr', branch_id=self.cfg.id)
        self.assertTrue(self.EA.is_active())
        rec.revoke()
        self.assertFalse(self.EA.is_active())
        # a separately-expired activation is not active
        rec2 = self.EA.activate(reason='y', approver='mgr', branch_id=self.cfg.id)
        rec2.expires_at = fields.Datetime.now() - timedelta(minutes=1)
        self.assertFalse(self.EA.is_active())


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestEmergencyHttp(common.HttpCase):

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'em-shared'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'enforce')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        cfgs = self.env['pos.config'].search([], limit=2)
        self.cfgA = cfgs[0]
        self.cfgB = cfgs[1] if len(cfgs) > 1 else cfgs[0]
        self.EA = self.env['mezze.emergency.access']
        # a payable draft order in each branch
        self.orderA = self._order(self.cfgA)
        self.orderB = self._order(self.cfgB)
        self.env.flush_all()

    def _order(self, cfg):
        s = (self.env['pos.session'].search([('config_id', '=', cfg.id), ('state', '=', 'opened')], limit=1)
             or self.env['pos.session'].create({'config_id': cfg.id, 'user_id': self.env.uid}))
        p = (self.env['product.product'].search([('available_in_pos', '=', True)], limit=1)
             or self.env['product.product'].search([], limit=1))
        return self.env['pos.order'].create({
            'session_id': s.id, 'company_id': cfg.company_id.id,
            'lines': [(0, 0, {'product_id': p.id, 'qty': 1, 'price_unit': 10.0,
                              'price_subtotal': 10.0, 'price_subtotal_incl': 10.0, 'tax_ids': [(6, 0, [])]})],
            'amount_total': 10.0, 'amount_paid': 0.0, 'amount_tax': 0.0, 'amount_return': 0.0,
            'pricelist_id': cfg.pricelist_id.id or False})

    def _post(self, path, body):
        r = self.url_open(BASE + path, data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:150]}

    def test_shared_admin_rejected_in_production(self):
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.env_profile', 'production')
        st, b = self._post('/orders/pay', {'uuid': self.orderA.uuid, 'token': self.shared})
        self.assertEqual(b.get('error'), 'authentication_failed')

    def test_emergency_narrows_capabilities(self):
        # baseline (no emergency, dev): shared-admin has all caps -> refund not denied
        st, b = self._post('/orders/refund',
                           {'uuid': 'em-r0', 'session_id': self.orderA.session_id.id,
                            'original_order_id': self.orderA.id, 'token': self.shared})
        self.assertNotEqual(b.get('error'), 'permission_denied')
        # activate a NARROW emergency (orders.read only, branch A)
        self.EA.activate(reason='incident', approver='gm', hours=1,
                         branch_id=self.cfgA.id, capabilities='orders.read')
        self.env.flush_all()
        # now the shared token maps to the emergency principal: refund is denied
        st, b = self._post('/orders/refund',
                           {'uuid': 'em-r1', 'session_id': self.orderA.session_id.id,
                            'original_order_id': self.orderA.id, 'token': self.shared})
        self.assertEqual(b.get('error'), 'permission_denied')
        # a granted capability (orders.read) still works
        st, b = self._post('/orders/get', {'order_id': self.orderA.id, 'token': self.shared})
        self.assertNotEqual(b.get('error'), 'permission_denied')

    def test_emergency_is_branch_scoped(self):
        if self.cfgA.id == self.cfgB.id:
            self.skipTest('single branch environment')
        self.EA.activate(reason='incident', approver='gm', hours=1,
                         branch_id=self.cfgA.id, capabilities='orders.read,orders.pay')
        self.env.flush_all()
        # emergency scoped to branch A -> a branch-B order is denied (not admin bypass)
        st, b = self._post('/orders/pay', {'uuid': self.orderB.uuid, 'token': self.shared})
        self.assertEqual(b.get('error'), 'branch_mismatch')

    def test_expired_emergency_rejected_in_production(self):
        rec = self.EA.activate(reason='incident', approver='gm', hours=1, branch_id=self.cfgA.id,
                               capabilities='orders.read')
        rec.expires_at = fields.Datetime.now() - timedelta(minutes=1)
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.env_profile', 'production')
        self.env.flush_all()
        st, b = self._post('/orders/pay', {'uuid': self.orderA.uuid, 'token': self.shared})
        self.assertEqual(b.get('error'), 'authentication_failed')   # expired -> shared-admin disabled
