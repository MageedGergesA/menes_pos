"""S2C-3 — integrated payment terminal orchestration (HTTP contract tests).

Server-authoritative trust, forged-success rejection, one-transaction-one-payment,
idempotency, lost-response recovery, timeout/uncertain, manager-gated Force Done
with provenance + reconciliation flag, cashier Force Done rejection, and mixed
integrated + cash tender. Deterministic + hermetic (self-provisions fixtures).

The TEST simulator is the only concrete terminal adapter; a real provider
(``adyen``) is used to prove that a browser-asserted success is refused.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestIntegratedTerminal(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'trm-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        icp.set_param('mezze_bridge.terminal_simulator_enabled', '1')
        company = self.pos_config.company_id
        self.cash = self.cash_payment_method

        def _jr(code):
            return self.env['account.journal'].create({
                'name': code, 'code': code, 'type': 'bank', 'company_id': company.id}).id

        def _terminal_method(name, code, provider):
            m = self.env['pos.payment.method'].create({
                'name': name, 'company_id': company.id, 'journal_id': _jr(code),
                'mezze_mode': 'odoo_terminal', 'mezze_terminal_provider': provider,
                'mezze_allow_partial': True, 'mezze_allow_mixed': True})
            self.pos_config.write({'payment_method_ids': [(4, m.id)]})
            return m

        # simulator-backed integrated method + a device
        self.sim = _terminal_method('Card (Integrated)', 'SIMJ', 'test')
        # a REAL provider (Adyen) — used to prove forged success is refused
        self.adyen = _terminal_method('Adyen Card', 'ADYJ', 'adyen')
        self.dev = self.env['mezze.payment.device'].create({
            'name': 'Front Counter', 'code': 'FC01', 'config_id': self.pos_config.id,
            'mode': 'odoo_terminal', 'integration_type': 'odoo_terminal',
            'payment_method_ids': [(6, 0, (self.sim + self.adyen).ids)]})
        self.mgr = self.env['mezze.cashier'].create({'name': 'Mona', 'code': 'MGR9', 'role': 'manager'})
        self.mgr.set_pin('4321')
        self.csh = self.env['mezze.cashier'].create({'name': 'Sara', 'code': 'CSH9', 'role': 'cashier'})
        self.csh.set_pin('1111')
        self.env.flush_all()

    # ------------------------------------------------------------------ helpers
    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, token='trm-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def _draft(self, price=500.0):
        s = self.open_test_session()
        o = self.create_order_in_test_session(price=price, session=s)
        o.write({'state': 'draft'})
        self.env.flush_all()
        return o

    def _paycount(self, o):
        return self.env['pos.payment'].search_count([('pos_order_id', '=', o.id)])

    def _start(self, o, method=None, scenario='success', amount=None):
        body = {'uuid': o.uuid, 'payment_method_id': (method or self.sim).id,
                'device_id': self.dev.id, 'scenario': scenario}
        if amount is not None:
            body['amount'] = amount
        return self._post('/terminal/start', body)

    # ------------------------------------------------------------------ tests
    def test_sim_success_one_payment(self):
        o = self._draft(price=500.0)
        st, r = self._start(o, scenario='success')
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['state'], 'waiting_customer')
        rid = r['request_id']
        st, r = self._post('/terminal/complete', {'request_id': rid, 'outcome': 'approved'})
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['state'], 'approved')
        self.assertEqual(r['remaining'], 0.0)
        self.assertEqual(o.state, 'paid')
        self.assertEqual(self._paycount(o), 1)
        pay = o.payment_ids
        self.assertEqual(pay.mezze_confirmation_source, 'integrated')
        self.assertFalse(pay.mezze_recon_flag)
        self.assertEqual(pay.mezze_tender_key, rid)

    def test_forged_success_rejected(self):
        """MANDATORY: a browser claiming approved on a REAL provider (not wired to
        the standalone cashier) can NOT create a payment."""
        o = self._draft(price=500.0)
        st, r = self._start(o, method=self.adyen, scenario='success')
        self.assertTrue(r['ok'], r)
        rid = r['request_id']
        st, r = self._post('/terminal/complete', {'request_id': rid, 'outcome': 'approved'})
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'terminal_not_completed')
        self.assertEqual(self._paycount(o), 0)
        self.assertEqual(o.state, 'draft')

    def test_sim_decline_no_payment(self):
        o = self._draft(price=200.0)
        _, r = self._start(o, scenario='decline')
        _, r = self._post('/terminal/complete', {'request_id': r['request_id'], 'outcome': 'approved'})
        self.assertTrue(r['ok'])
        self.assertEqual(r['state'], 'declined')
        self.assertEqual(self._paycount(o), 0)
        self.assertEqual(o.state, 'draft')  # remains payable

    def test_sim_cancel_no_payment(self):
        o = self._draft(price=200.0)
        _, r = self._start(o, scenario='success')
        _, r = self._post('/terminal/cancel', {'request_id': r['request_id']})
        self.assertTrue(r['ok'])
        self.assertEqual(r['state'], 'cancelled')
        self.assertEqual(self._paycount(o), 0)

    def test_duplicate_success_idempotent(self):
        o = self._draft(price=300.0)
        _, r = self._start(o, scenario='duplicate_success')
        rid = r['request_id']
        _, r1 = self._post('/terminal/complete', {'request_id': rid, 'outcome': 'approved'})
        _, r2 = self._post('/terminal/complete', {'request_id': rid, 'outcome': 'approved'})
        _, r3 = self._post('/terminal/complete', {'request_id': rid, 'outcome': 'approved'})
        self.assertTrue(r1['ok'] and r2['ok'] and r3['ok'])
        self.assertEqual(self._paycount(o), 1)

    def test_lost_response_recovery(self):
        """Approved but the response was 'lost': /status recovers the truth and a
        retried /complete does not double-charge."""
        o = self._draft(price=250.0)
        _, r = self._start(o, scenario='success')
        rid = r['request_id']
        self._post('/terminal/complete', {'request_id': rid, 'outcome': 'approved'})
        # cashier reloads -> reads authoritative state
        _, s = self._post('/terminal/status', {'request_id': rid})
        self.assertEqual(s['state'], 'approved')
        self.assertTrue(s['has_payment'])
        # accidental retry -> idempotent
        _, again = self._post('/terminal/complete', {'request_id': rid, 'outcome': 'approved'})
        self.assertEqual(self._paycount(o), 1)

    def test_timeout_is_uncertain_not_declined(self):
        o = self._draft(price=200.0)
        _, r = self._start(o, scenario='timeout')
        _, r = self._post('/terminal/complete', {'request_id': r['request_id'], 'outcome': 'approved'})
        self.assertTrue(r['ok'])
        self.assertEqual(r['state'], 'timeout')
        self.assertTrue(r['uncertain'])
        self.assertEqual(self._paycount(o), 0)

    def test_single_in_flight(self):
        o = self._draft(price=200.0)
        _, r1 = self._start(o, scenario='success')
        self.assertTrue(r1['ok'])
        st, r2 = self._start(o, scenario='success')  # second while first is live
        self.assertEqual(st, 409)
        self.assertEqual(r2['error'], 'terminal_start_rejected')

    def test_amount_ceiling(self):
        o = self._draft(price=100.0)
        st, r = self._start(o, scenario='success', amount=o.amount_total + 50)
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'terminal_start_rejected')
        self.assertEqual(self._paycount(o), 0)

    def test_simulator_disabled_in_production(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.terminal_simulator_enabled', '0')
        o = self._draft(price=100.0)
        st, r = self._start(o, scenario='success')
        self.assertEqual(st, 403)
        self.assertEqual(r['error'], 'simulator_disabled')
        self.assertEqual(self._paycount(o), 0)

    # -- Force Done ---------------------------------------------------------
    def _error_txn(self, o):
        _, r = self._start(o, scenario='error')
        _, r = self._post('/terminal/complete', {'request_id': r['request_id'], 'outcome': 'approved'})
        self.assertEqual(r['state'], 'error')
        return r['request_id']

    def test_force_done_requires_manager(self):
        o = self._draft(price=400.0)
        rid = self._error_txn(o)
        # no manager creds
        st, r = self._post('/terminal/force_done', {'request_id': rid, 'manager_reason': 'x'})
        self.assertEqual(st, 401)
        self.assertEqual(r['error'], 'manager_required')
        self.assertEqual(self._paycount(o), 0)

    def test_cashier_cannot_force_done(self):
        o = self._draft(price=400.0)
        rid = self._error_txn(o)
        st, r = self._post('/terminal/force_done', {'request_id': rid, 'manager_code': 'CSH9',
                                                    'manager_pin': '1111', 'manager_reason': 'x'})
        self.assertEqual(st, 403)
        self.assertEqual(r['error'], 'insufficient_role')
        self.assertEqual(self._paycount(o), 0)

    def test_force_done_bad_pin(self):
        o = self._draft(price=400.0)
        rid = self._error_txn(o)
        st, r = self._post('/terminal/force_done', {'request_id': rid, 'manager_code': 'MGR9',
                                                    'manager_pin': '0000', 'manager_reason': 'x'})
        self.assertEqual(st, 403)
        self.assertEqual(r['error'], 'bad_credentials')
        self.assertEqual(self._paycount(o), 0)

    def test_manager_force_done_provenance_and_audit(self):
        o = self._draft(price=400.0)
        rid = self._error_txn(o)
        st, r = self._post('/terminal/force_done', {'request_id': rid, 'manager_code': 'MGR9',
                                                    'manager_pin': '4321',
                                                    'manager_reason': 'customer showed SMS'})
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['state'], 'approved')
        self.assertTrue(r['force_done'])
        self.assertEqual(o.state, 'paid')
        self.assertEqual(self._paycount(o), 1)
        pay = o.payment_ids
        self.assertEqual(pay.mezze_confirmation_source, 'manual_force_done')
        self.assertTrue(pay.mezze_recon_flag)
        audit = self.env['mezze.audit.log'].search([('event', '=', 'terminal.force_done')])
        self.assertTrue(audit)

    def test_force_done_requires_reason(self):
        o = self._draft(price=400.0)
        rid = self._error_txn(o)
        st, r = self._post('/terminal/force_done', {'request_id': rid, 'manager_code': 'MGR9',
                                                    'manager_pin': '4321', 'manager_reason': ''})
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'force_done_rejected')
        self.assertEqual(self._paycount(o), 0)

    def test_force_done_ineligible_on_success(self):
        o = self._draft(price=400.0)
        _, r = self._start(o, scenario='success')
        rid = r['request_id']
        self._post('/terminal/complete', {'request_id': rid, 'outcome': 'approved'})  # approved
        st, r = self._post('/terminal/force_done', {'request_id': rid, 'manager_code': 'MGR9',
                                                    'manager_pin': '4321', 'manager_reason': 'x'})
        # already approved -> idempotent success, still exactly one payment
        self.assertEqual(self._paycount(o), 1)

    # -- mixed integrated + cash -------------------------------------------
    def test_mixed_integrated_and_cash(self):
        o = self._draft(price=1000.0)
        total = o.amount_total
        _, r = self._start(o, scenario='success', amount=600)
        rid = r['request_id']
        _, r = self._post('/terminal/complete', {'request_id': rid, 'outcome': 'approved'})
        self.assertTrue(r['ok'])
        self.assertEqual(r['state'], 'approved')
        self.assertAlmostEqual(r['remaining'], round(total - 600, 2))
        self.assertEqual(o.state, 'draft')
        # cash remainder via the existing money path
        _, r2 = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.cash.id,
                                           'tender_key': 'cashrem'})
        self.assertTrue(r2['ok'])
        self.assertEqual(r2['remaining'], 0.0)
        self.assertEqual(o.state, 'paid')
        self.assertEqual(self._paycount(o), 2)
        self.assertAlmostEqual(sum(o.payment_ids.mapped('amount')), total)

    def test_failed_terminal_after_prior_cash_preserved(self):
        """Cash succeeds, then integrated errors: cash preserved, order still open."""
        o = self._draft(price=1000.0)
        total = o.amount_total
        _, rc = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.cash.id,
                                           'amount': 300, 'tender_key': 'c1'})
        self.assertTrue(rc['partial'])
        rid = self._error_txn(o)
        self.assertEqual(self._paycount(o), 1)          # cash preserved, no terminal payment
        self.assertEqual(o.state, 'draft')
        self.assertAlmostEqual(round(total - 300, 2), rc['remaining'])
