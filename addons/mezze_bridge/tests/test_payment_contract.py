"""S2 Slice 2B — HTTP contract tests for the cashier-payment UI endpoints.
Verifies payloads are stable and free of card/provider secrets. (Browser/UX rendering
is NOT executed here — no in-repo JS harness — and is reported honestly as such.)"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestPaymentContract(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'pay-tok')
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_security', 'observe')
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.env_profile', 'development')
        self.dev = self.env['mezze.payment.device'].create({
            'name': 'CIB-01', 'code': 'CIB01', 'config_id': self.pos_config.id,
            'mode': 'external_terminal', 'payment_method_ids': [(6, 0, self.card_payment_method.ids)]})
        self.env.flush_all()

    def _post(self, path, body):
        body = dict(body, token='pay-tok')
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def _paid_order(self, amount=80.0, ref='TERMINAL-8421'):
        s = self.open_test_session()
        o = self.create_order_in_test_session(price=amount)
        self.env['pos.payment'].create({
            'pos_order_id': o.id, 'session_id': s.id, 'payment_method_id': self.card_payment_method.id,
            'amount': amount, 'payment_ref_no': ref, 'mezze_device_id': self.dev.id})
        o.write({'state': 'paid'})
        self.env.flush_all()
        return s, o

    def test_device_list_scoped(self):
        st, b = self._post('/payment/devices', {'config_id': self.pos_config.id,
                                                'payment_method_id': self.card_payment_method.id})
        self.assertEqual(st, 200)
        self.assertTrue(b['ok'])
        self.assertIn('CIB-01', [d['name'] for d in b['devices']])

    def test_breakdown_masks_reference_no_secrets(self):
        _s, o = self._paid_order(ref='TERMINAL-8421')
        st, b = self._post('/payment/breakdown', {'uuid': o.uuid})
        self.assertTrue(b['ok'])
        line = b['payments'][0]
        self.assertEqual(line['method'], self.card_payment_method.name)  # configured name, not mode
        self.assertTrue(line['ref_masked'].endswith('8421'))
        self.assertTrue(line['ref_masked'].startswith('••••'))
        blob = json.dumps(b).lower()
        for leak in ('cvv', 'pin', 'password', 'secret', 'pan', 'external_terminal', 'mezze_mode'):
            self.assertNotIn(leak, blob)

    def test_reconciliation_summary_accurate(self):
        s, _ = self._paid_order(amount=80.0)
        st, b = self._post('/reconciliation/summary', {'session_id': s.id})
        self.assertTrue(b['ok'])
        line = [l for l in b['lines'] if l['method'] == self.card_payment_method.name][0]
        self.assertAlmostEqual(line['expected'], 80.0)
        self.assertEqual(line['status'], 'missing_settlement')

    def test_settlement_then_matched(self):
        s, _ = self._paid_order(amount=80.0)
        _st, summ = self._post('/reconciliation/summary', {'session_id': s.id})
        line_id = [l['line_id'] for l in summ['lines'] if l['method'] == self.card_payment_method.name][0]
        st, b = self._post('/reconciliation/settlement', {'line_id': line_id, 'amount': 80.0, 'reference': 'SET-1'})
        self.assertTrue(b['ok'])
        self.assertEqual(b['status'], 'matched')
        self.assertAlmostEqual(b['difference'], 0.0)

    def test_finalize_needs_manager_over_tolerance(self):
        self.card_payment_method.reconciliation_tolerance = 5.0
        s, _ = self._paid_order(amount=80.0)
        _st, summ = self._post('/reconciliation/summary', {'session_id': s.id})
        line_id = [l['line_id'] for l in summ['lines'] if l['method'] == self.card_payment_method.name][0]
        self._post('/reconciliation/settlement', {'line_id': line_id, 'amount': 50.0, 'reference': 'S'})
        st, b = self._post('/reconciliation/finalize', {'reconciliation_id': summ['reconciliation_id']})
        self.assertEqual(st, 409)
        self.assertEqual(b['error'], 'needs_manager_approval')
        st2, b2 = self._post('/reconciliation/finalize',
                             {'reconciliation_id': summ['reconciliation_id'], 'approved_by': self.manager_user.id})
        self.assertTrue(b2['ok'])
        self.assertEqual(b2['state'], 'finalized')

    def test_external_refund_confirm_contract(self):
        s = self.open_test_session()
        o = self.create_order_in_test_session(price=30.0)
        p = self.env['pos.payment'].create({
            'pos_order_id': o.id, 'session_id': s.id, 'payment_method_id': self.card_payment_method.id,
            'amount': 30.0, 'mezze_external_refund_status': 'pending_external'})
        self.env.flush_all()
        st, b = self._post('/payment/external_refund/confirm', {'payment_id': p.id, 'reference': 'RF-1'})
        self.assertTrue(b['ok'])
        self.assertEqual(b['external_refund_status'], 'confirmed_external')

    def test_report_totals(self):
        s, _ = self._paid_order(amount=80.0)
        st, b = self._post('/payment/report', {'session_id': s.id})
        self.assertTrue(b['ok'])
        self.assertAlmostEqual(b['by_method'].get(self.card_payment_method.name, 0), 80.0)
        self.assertIn('CIB-01', b['by_device'])

    def test_unauthorized_rejected(self):
        r = self.url_open('/mezze/api/v1/payment/devices',
                          data=json.dumps({'token': 'WRONG'}),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        self.assertIn(r.status_code, (401, 403))
