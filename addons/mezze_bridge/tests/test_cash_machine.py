"""S2C-7 — automated cash-machine orchestration (HTTP contract tests).

Server-authoritative amount, forged-success rejection (arbitrary claim AND real
device), one-transaction-one-payment idempotency, inserted != payment when change is
returned, cancel / connection-failure = no payment, duplicate + concurrent result,
lost-response recovery, mixed tender, uncertain + manager Force Done, simulator
production rejection, credential non-exposure, validator. Deterministic + hermetic.

The TEST simulator is the only concrete cash-machine adapter; a real Glory provider
proves a browser-asserted success is refused (adapter PENDING). No device protocol is
implemented — this certifies the Mezze orchestration software only.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestCashMachine(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'cm-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        icp.set_param('mezze_bridge.cashmachine_simulator_enabled', '1')
        company = self.pos_config.company_id
        self.cash = self.cash_payment_method

        def _jr(code):
            return self.env['account.journal'].create({
                'name': code, 'code': code, 'type': 'bank', 'company_id': company.id}).id

        def _cm_method(name, code, provider):
            m = self.env['pos.payment.method'].create({
                'name': name, 'company_id': company.id, 'journal_id': _jr(code),
                'mezze_mode': 'cash_machine', 'mezze_terminal_provider': provider,
                'mezze_allow_partial': True, 'mezze_allow_mixed': True})
            self.pos_config.write({'payment_method_ids': [(4, m.id)]})
            return m

        self.sim = _cm_method('Cash Machine 01', 'CMSIM', 'test')
        self.glory = _cm_method('Glory CI-10', 'CMGLR', 'glory')  # real → refused
        self.mgr = self.env['mezze.cashier'].create({'name': 'Mona', 'code': 'MGRC', 'role': 'manager'})
        self.mgr.set_pin('4321')
        self.csh = self.env['mezze.cashier'].create({'name': 'Sara', 'code': 'CSHC', 'role': 'cashier'})
        self.csh.set_pin('1111')
        self.env.flush_all()

    # ------------------------------------------------------------------ helpers
    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, token='cm-tok')),
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

    def _start(self, o, method=None, **kw):
        return self._post('/cashmachine/start', dict(
            {'uuid': o.uuid, 'payment_method_id': (method or self.sim).id}, **kw))

    # ------------------------------------------------------------------ tests
    def test_configured_method_and_mode(self):
        self.assertEqual(self.sim.mezze_mode, 'cash_machine')
        o = self._draft()
        st, r = self._start(o, scenario='success_exact')
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['kind'], 'cash_machine')
        self.assertEqual(r['state'], 'waiting_customer')

    def test_authoritative_amount(self):
        o = self._draft(price=100.0)
        total = o.amount_total
        # browser cannot inflate beyond the remaining balance
        st, r = self._start(o, amount=total + 500, scenario='success_exact')
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'cashmachine_start_rejected')
        # full = remaining
        st, r = self._start(o, scenario='success_exact')
        self.assertAlmostEqual(r['amount'], round(total, 2), places=2)

    def test_forged_success_real_device_refused(self):
        o = self._draft()
        st, r = self._start(o, method=self.glory, scenario='success_exact')
        self.assertTrue(r['ok'], r)
        rid = r['request_id']
        # a browser claim of success cannot mint a payment for a real (pending) device
        st, r = self._post('/cashmachine/complete', {'request_id': rid, 'outcome': 'approved'})
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'cashmachine_not_completed')
        self.assertEqual(self._paycount(o), 0)
        self.assertEqual(r['state'], 'error')

    def test_forged_arbitrary_claim_ignored(self):
        # scenario is CANCEL; a browser claim of 'approved' must be ignored
        o = self._draft()
        _, r = self._start(o, scenario='cancel')
        rid = r['request_id']
        st, r = self._post('/cashmachine/complete', {'request_id': rid, 'outcome': 'approved'})
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['state'], 'cancelled')
        self.assertEqual(self._paycount(o), 0)

    def test_success_exact_one_payment(self):
        o = self._draft(price=800.0)
        total = o.amount_total
        _, r = self._start(o, scenario='success_exact')
        rid = r['request_id']
        st, r = self._post('/cashmachine/complete', {'request_id': rid})
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['state'], 'approved')
        self.assertEqual(self._paycount(o), 1)
        pay = self.env['pos.order'].browse(o.id).payment_ids
        self.assertAlmostEqual(sum(pay.mapped('amount')), round(total, 2), places=2)
        self.assertAlmostEqual(r['change'], 0.0, places=2)
        self.assertEqual(o.state, 'paid')

    def test_change_inserted_is_not_payment(self):
        # due 850 charged to the machine; inserted 1000; change 150; payment == 850
        o = self._draft(price=2000.0)   # remaining big enough for an 850 partial
        _, r = self._start(o, amount=850.0, scenario='success_with_change', sim_inserted=1000.0)
        rid = r['request_id']
        st, r = self._post('/cashmachine/complete', {'request_id': rid})
        self.assertTrue(r['ok'], r)
        self.assertAlmostEqual(r['inserted'], 1000.0, places=2)
        self.assertAlmostEqual(r['change'], 150.0, places=2)
        pay = self.env['pos.order'].browse(o.id).payment_ids
        self.assertAlmostEqual(sum(pay.mapped('amount')), 850.0, places=2)   # NOT 1000
        # invariant: pos.payment <= amount due
        self.assertLessEqual(sum(pay.mapped('amount')), o.amount_total + 0.01)

    def test_cancel_zero_payment(self):
        o = self._draft()
        _, r = self._start(o, scenario='success_exact')
        rid = r['request_id']
        st, r = self._post('/cashmachine/cancel', {'request_id': rid})
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['state'], 'cancelled')
        self.assertEqual(self._paycount(o), 0)
        self.assertEqual(o.state, 'draft')   # still payable

    def test_connection_failure(self):
        o = self._draft()
        _, r = self._start(o, scenario='connection_error')
        rid = r['request_id']
        st, r = self._post('/cashmachine/complete', {'request_id': rid})
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['state'], 'cancelled')
        self.assertEqual(r['error_code'], 'connection_error')
        self.assertEqual(self._paycount(o), 0)
        self.assertEqual(o.state, 'draft')   # order remains payable

    def test_duplicate_result_one_payment(self):
        o = self._draft(price=600.0)
        _, r = self._start(o, scenario='duplicate_success')
        rid = r['request_id']
        for _ in range(10):
            st, r = self._post('/cashmachine/complete', {'request_id': rid})
            self.assertTrue(r['ok'], r)
        self.assertEqual(self._paycount(o), 1)

    def test_lost_response_recovery(self):
        o = self._draft(price=600.0)
        _, r = self._start(o, scenario='success_exact')
        rid = r['request_id']
        self._post('/cashmachine/complete', {'request_id': rid})   # processed
        # browser "lost" the response and reloads → reads status, no re-charge
        st, r = self._post('/cashmachine/status', {'request_id': rid})
        self.assertEqual(r['state'], 'approved')
        self.assertTrue(r['has_payment'])
        self.assertEqual(self._paycount(o), 1)

    def test_mixed_cash_and_machine(self):
        o = self._draft(price=1000.0)
        total = o.amount_total
        self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.cash.id,
                                   'amount': 300, 'tender_key': 'c1'})
        _, r = self._start(o, scenario='success_exact')   # amount defaults to remaining
        rid = r['request_id']
        self.assertAlmostEqual(r['amount'], round(total - 300, 2), places=2)   # 700, not 1000
        st, r = self._post('/cashmachine/complete', {'request_id': rid})
        self.assertTrue(r['ok'], r)
        self.assertEqual(self._paycount(o), 2)
        pay = self.env['pos.order'].browse(o.id).payment_ids
        self.assertAlmostEqual(sum(pay.mapped('amount')), round(total, 2), places=2)
        self.assertEqual(o.state, 'paid')

    def test_uncertain_then_manager_force_done(self):
        o = self._draft(price=500.0)
        _, r = self._start(o, scenario='unknown')
        rid = r['request_id']
        st, r = self._post('/cashmachine/complete', {'request_id': rid})
        self.assertEqual(r['state'], 'unknown')
        self.assertTrue(r['uncertain'])
        self.assertEqual(self._paycount(o), 0)   # never auto-paid
        # cashier cannot self-force
        st, r = self._post('/cashmachine/force_done', {'request_id': rid,
                           'manager_code': 'CSHC', 'manager_pin': '1111', 'manager_reason': 'x'})
        self.assertEqual(st, 403)
        self.assertEqual(r['error'], 'insufficient_role')
        self.assertEqual(self._paycount(o), 0)
        # manager forces → one payment, force-done provenance
        st, r = self._post('/cashmachine/force_done', {'request_id': rid,
                           'manager_code': 'MGRC', 'manager_pin': '4321', 'manager_reason': 'verified machine'})
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['state'], 'approved')
        self.assertTrue(r['force_done'])
        self.assertEqual(self._paycount(o), 1)
        pay = self.env['pos.order'].browse(o.id).payment_ids
        self.assertEqual(pay.mezze_confirmation_source, 'manual_force_done')
        self.assertTrue(pay.mezze_recon_flag)

    def test_simulator_production_rejection(self):
        # disable the simulator → the 'test' method must be refused, 0 payment
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.cashmachine_simulator_enabled', '0')
        o = self._draft()
        st, r = self._start(o, scenario='success_exact')
        self.assertEqual(st, 403)
        self.assertEqual(r['error'], 'simulator_disabled')
        self.assertEqual(self._paycount(o), 0)

    def test_credential_non_exposure(self):
        # the cashier-facing payload never carries machine credentials
        o = self._draft()
        _, r = self._start(o, scenario='success_exact')
        for k in ('glory_username', 'glory_password', 'glory_websocket_address', 'username', 'password'):
            self.assertNotIn(k, r)
        # bootstrap payment-method projection must not leak credential fields either
        st, boot = self._post('/bootstrap', {'config_id': self.pos_config.id})
        blob = json.dumps(boot)
        self.assertNotIn('glory_password', blob)
        self.assertNotIn('glory_username', blob)

    def test_concurrent_result_one_payment(self):
        # sequential proxy for two workers settling the same request: request_id +
        # FOR UPDATE + unique tender_key => exactly one payment.
        o = self._draft(price=600.0)
        _, r = self._start(o, scenario='success_exact')
        rid = r['request_id']
        r1 = self._post('/cashmachine/complete', {'request_id': rid})[1]
        r2 = self._post('/cashmachine/complete', {'request_id': rid})[1]
        self.assertTrue(r1['ok'] and r2['ok'])
        self.assertEqual(self._paycount(o), 1)

    def test_validator_flags_simulator_and_physical(self):
        report = self.env['mezze.golive.validator'].sudo().run()
        checks = {c['name']: c for c in report['checks']}
        self.assertIn('cash_machine_simulator_absent', checks)
        self.assertEqual(checks['cash_machine_simulator_absent']['status'], 'FAIL')  # test method present
        self.assertIn('cash_machine_physical', checks)
        self.assertEqual(checks['cash_machine_physical']['status'], 'N/A')
