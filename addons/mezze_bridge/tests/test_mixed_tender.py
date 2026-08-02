"""S2C-2 — partial + mixed tender, per-tender idempotency, device/reference
enforcement, duplicate WARN, and inline manager-PIN approval. HTTP contract tests
against /orders/pay (the one financial path). Deterministic + hermetic."""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestMixedTender(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'mix-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        # card = external terminal, device required, reference optional, dup warn
        self.card = self.card_payment_method
        self.card.write({'mezze_mode': 'external_terminal', 'device_policy': 'required',
                         'reference_policy': 'optional', 'duplicate_policy': 'warn'})
        self.cash = self.cash_payment_method
        self.dev = self.env['mezze.payment.device'].create({
            'name': 'CIB-01', 'code': 'CIB01', 'config_id': self.pos_config.id,
            'mode': 'external_terminal', 'payment_method_ids': [(6, 0, self.card.ids)]})
        company = self.pos_config.company_id

        def _jr(code):
            return self.env['account.journal'].create({
                'name': code, 'code': code, 'type': 'bank', 'company_id': company.id}).id

        def _method(name, code, **pol):
            return self.env['pos.payment.method'].create(dict(
                pol, name=name, company_id=company.id, journal_id=_jr(code), mezze_mode='manual'))

        # a manual method with a required reference
        self.transfer = _method('InstaPay', 'IPJ9', reference_policy='required', duplicate_policy='warn')
        # a manager-approval + a block method
        self.mgr_method = _method('Loyalty Redeem', 'LRJ9', reference_policy='optional',
                                  duplicate_policy='manager_approval')
        self.block_method = _method('Gift Voucher', 'GVJ9', reference_policy='optional',
                                    duplicate_policy='block')
        self.pos_config.write({'payment_method_ids': [(4, m) for m in (
            self.transfer.id, self.mgr_method.id, self.block_method.id)]})
        # manager + cashier principals
        self.mgr = self.env['mezze.cashier'].create({'name': 'Mona', 'code': 'MGR9', 'role': 'manager'})
        self.mgr.set_pin('4321')
        self.csh = self.env['mezze.cashier'].create({'name': 'Sara', 'code': 'CSH9', 'role': 'cashier'})
        self.csh.set_pin('1111')
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, token='mix-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def _draft(self, price=1000.0):
        s = self.open_test_session()
        o = self.create_order_in_test_session(price=price, session=s)
        o.write({'state': 'draft'})
        self.env.flush_all()
        return o

    def _paycount(self, o):
        return self.env['pos.payment'].search_count([('pos_order_id', '=', o.id)])

    # -- partial + mixed ----------------------------------------------------
    def test_partial_then_mixed_settles(self):
        o = self._draft(price=1000.0)
        total = o.amount_total
        st, r1 = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.card.id,
                                            'amount': 300, 'device_id': self.dev.id,
                                            'payment_ref': 'T1', 'tender_key': 'k1'})
        self.assertTrue(r1['ok'] and r1['partial'])
        self.assertAlmostEqual(r1['remaining'], round(total - 300, 2))
        self.assertEqual(o.state, 'draft')
        st, r2 = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.cash.id,
                                            'tender_key': 'k2'})  # completes remaining
        self.assertTrue(r2['ok'])
        self.assertEqual(r2['remaining'], 0.0)
        self.assertEqual(o.state, 'paid')
        self.assertEqual(self._paycount(o), 2)
        self.assertAlmostEqual(sum(o.payment_ids.mapped('amount')), total)

    def test_overpay_rejected(self):
        o = self._draft(price=100.0)
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.cash.id,
                                           'amount': o.amount_total + 50, 'tender_key': 'ov'})
        self.assertEqual(st, 400)
        self.assertEqual(r['error'], 'overpay')
        self.assertEqual(self._paycount(o), 0)

    def test_tender_key_idempotent(self):
        o = self._draft(price=100.0)
        b = {'uuid': o.uuid, 'payment_method_id': self.cash.id, 'tender_key': 'same'}
        st1, r1 = self._post('/orders/pay', b)
        st2, r2 = self._post('/orders/pay', b)
        self.assertTrue(r1['ok'])
        self.assertTrue(r2.get('idempotent'))
        self.assertEqual(self._paycount(o), 1)

    # -- policy enforcement BEFORE financial effect -------------------------
    def test_device_required_blocks(self):
        o = self._draft(price=100.0)
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.card.id,
                                           'tender_key': 'nod'})  # no device
        self.assertEqual(st, 400)
        self.assertEqual(r['error'], 'payment_rejected')
        self.assertEqual(self._paycount(o), 0)

    def test_reference_required_blocks(self):
        o = self._draft(price=100.0)
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.transfer.id,
                                           'tender_key': 'nor'})  # no reference
        self.assertEqual(st, 400)
        self.assertEqual(r['error'], 'payment_rejected')
        self.assertEqual(self._paycount(o), 0)

    # -- duplicate policies -------------------------------------------------
    def test_duplicate_warn(self):
        o1 = self._draft(price=100.0)
        self._post('/orders/pay', {'uuid': o1.uuid, 'payment_method_id': self.transfer.id,
                                   'payment_ref': 'DUP1', 'tender_key': 'a'})
        o2 = self._draft(price=100.0)
        st, r = self._post('/orders/pay', {'uuid': o2.uuid, 'payment_method_id': self.transfer.id,
                                           'payment_ref': 'DUP1', 'tender_key': 'b'})
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'duplicate_reference_warn')
        self.assertTrue(r['duplicate'][0]['ref_masked'].endswith('DUP1') or '••' in r['duplicate'][0]['ref_masked'])
        # continue with override
        st2, r2 = self._post('/orders/pay', {'uuid': o2.uuid, 'payment_method_id': self.transfer.id,
                                             'payment_ref': 'DUP1', 'allow_duplicate': True, 'tender_key': 'c'})
        self.assertTrue(r2['ok'])

    def test_block_no_bypass_in_flow(self):
        o1 = self._draft(price=100.0)
        self._post('/orders/pay', {'uuid': o1.uuid, 'payment_method_id': self.block_method.id,
                                   'payment_ref': 'BLK1', 'tender_key': 'a'})
        o2 = self._draft(price=100.0)
        st, r = self._post('/orders/pay', {'uuid': o2.uuid, 'payment_method_id': self.block_method.id,
                                           'payment_ref': 'BLK1', 'tender_key': 'b'})
        self.assertEqual(st, 400)
        self.assertEqual(r['error'], 'payment_rejected')
        self.assertEqual(self._paycount(o2), 0)

    # -- manager approval (inline PIN) --------------------------------------
    def test_manager_approval_flow(self):
        o1 = self._draft(price=100.0)
        self._post('/orders/pay', {'uuid': o1.uuid, 'payment_method_id': self.mgr_method.id,
                                   'payment_ref': 'MG1', 'tender_key': 'a'})
        o2 = self._draft(price=100.0)
        # needs manager
        st, r = self._post('/orders/pay', {'uuid': o2.uuid, 'payment_method_id': self.mgr_method.id,
                                           'payment_ref': 'MG1', 'tender_key': 'b'})
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'duplicate_reference_needs_manager')
        # cashier cannot self-approve
        st, r = self._post('/orders/pay', {'uuid': o2.uuid, 'payment_method_id': self.mgr_method.id,
                                           'payment_ref': 'MG1', 'manager_code': 'CSH9',
                                           'manager_pin': '1111', 'tender_key': 'c'})
        self.assertEqual(st, 403)
        self.assertEqual(r['error'], 'insufficient_role')
        # wrong pin
        st, r = self._post('/orders/pay', {'uuid': o2.uuid, 'payment_method_id': self.mgr_method.id,
                                           'payment_ref': 'MG1', 'manager_code': 'MGR9',
                                           'manager_pin': '0000', 'tender_key': 'd'})
        self.assertEqual(st, 403)
        self.assertEqual(r['error'], 'bad_credentials')
        self.assertEqual(self._paycount(o2), 0)
        # manager approves -> exactly one payment + audit
        st, r = self._post('/orders/pay', {'uuid': o2.uuid, 'payment_method_id': self.mgr_method.id,
                                           'payment_ref': 'MG1', 'manager_code': 'MGR9',
                                           'manager_pin': '4321', 'manager_reason': 'ok', 'tender_key': 'e'})
        self.assertTrue(r['ok'])
        self.assertEqual(self._paycount(o2), 1)
        audit = self.env['mezze.audit.log'].search([('event', '=', 'payment.duplicate_approved')])
        self.assertTrue(audit)
