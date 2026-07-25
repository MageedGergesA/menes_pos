"""Runtime object-authorization proof for newly-scoped Category-A routes (P6.3).

Tagged mezze_runtime. A terminal principal scoped to branch A is denied when it
targets an authoritative record (order / printer) owned by branch B — a valid
identifier from another tenant does not grant access. The own-branch request is
allowed (capability + scope both pass).
"""
import json

from odoo import fields
from odoo.tests import common, tagged

BASE = '/mezze/api/v1'
HW = '/mezze/hardware'


def _draft_order(env, cfg):
    s = (env['pos.session'].search([('config_id', '=', cfg.id), ('state', '=', 'opened')], limit=1)
         or env['pos.session'].create({'config_id': cfg.id, 'user_id': env.uid}))
    p = (env['product.product'].search([('available_in_pos', '=', True)], limit=1)
         or env['product.product'].search([], limit=1))
    return env['pos.order'].create({
        'session_id': s.id, 'company_id': cfg.company_id.id,
        'lines': [(0, 0, {'product_id': p.id, 'qty': 1, 'price_unit': 10.0,
                          'price_subtotal': 10.0, 'price_subtotal_incl': 10.0, 'tax_ids': [(6, 0, [])]})],
        'amount_total': 10.0, 'amount_paid': 0.0, 'amount_tax': 0.0, 'amount_return': 0.0,
        'pricelist_id': cfg.pricelist_id.id or False})


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestObjectScope(common.HttpCase):

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.api_security', 'enforce')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        ICP.set_param('mezze_bridge.signing_mode.terminal', 'observe')  # unsigned allowed here
        cfgs = self.env['pos.config'].search([], limit=2)
        self.cfgA, self.cfgB = cfgs[0], (cfgs[1] if len(cfgs) > 1 else cfgs[0])
        self.termA = self.env['mezze.terminal'].create({
            'name': 'A', 'identifier': 'OS-A', 'token': 'os-a-tok',
            'branch_id': self.cfgA.id, 'role': 'terminal', 'active': True})
        self.orderA = _draft_order(self.env, self.cfgA)
        self.orderB = _draft_order(self.env, self.cfgB)
        self.printerA = self.env['mezze.printer'].create({
            'name': 'PA', 'printer_type': 'receipt', 'config_id': self.cfgA.id,
            'host': '10.0.0.1', 'active': True})
        self.printerB = self.env['mezze.printer'].create({
            'name': 'PB', 'printer_type': 'receipt', 'config_id': self.cfgB.id,
            'host': '10.0.0.2', 'active': True})
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open(path, data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:150]}

    def _diff_branches(self):
        return self.cfgA.id != self.cfgB.id

    def test_print_receipt_cross_branch_denied(self):
        if not self._diff_branches():
            self.skipTest('single branch environment')
        st, b = self._post(HW + '/print/receipt',
                           {'order_id': self.orderB.id, 'token': 'os-a-tok', 'preview': True})
        self.assertEqual(b.get('error'), 'branch_mismatch')

    def test_print_receipt_own_branch_ok(self):
        st, b = self._post(HW + '/print/receipt',
                           {'order_id': self.orderA.id, 'token': 'os-a-tok', 'preview': True})
        self.assertNotIn(b.get('error'), ('branch_mismatch', 'permission_denied',
                                          'authentication_failed'))

    def test_drawer_cross_branch_denied(self):
        if not self._diff_branches():
            self.skipTest('single branch environment')
        st, b = self._post(HW + '/drawer/open',
                           {'config_id': self.cfgB.id, 'printer_id': self.printerB.id,
                            'token': 'os-a-tok'})
        self.assertEqual(b.get('error'), 'branch_mismatch')

    def test_shared_admin_crosses_branch(self):
        # the shared-admin (integration) principal is intentionally not branch-scoped
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'os-shared')
        st, b = self._post(HW + '/print/receipt',
                           {'order_id': self.orderB.id, 'token': 'os-shared', 'preview': True})
        self.assertNotIn(b.get('error'), ('branch_mismatch',))
