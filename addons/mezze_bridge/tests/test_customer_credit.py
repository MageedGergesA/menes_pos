"""S2C-6 — Customer Account / Credit.

Odoo's receivable/credit stays authoritative — these tests assert the native
accounting consequence (partner.credit, account.payment), not just pos.payment rows.
Covers: customer-required, exposure/limit, ODOO_WARNING / MANAGER_APPROVAL (+ cashier
self-approval rejected + audit) / HARD_BLOCK, partial-account charge, mixed cash +
account, concurrency, commercial partner, deposit (no revenue), settlement.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestCustomerCredit(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'cc-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        company = self.company
        company.account_use_credit_limit = True     # enable native limit checking
        self.cash = self.cash_payment_method
        # Customer Account (pay_later) method: journal blank + Identify Customer
        self.account_pm = self.env['pos.payment.method'].create({
            'name': 'Customer Account', 'company_id': company.id, 'journal_id': False,
            'split_transactions': True, 'mezze_credit_policy': 'odoo_warning'})
        self.pos_config.write({'payment_method_ids': [(4, self.account_pm.id)]})
        self.assertEqual(self.account_pm.type, 'pay_later')
        # a customer with a low limit so a normal order goes over
        self.cust = self.env['res.partner'].create({'name': 'ACME Co', 'is_company': True})
        self.cust.with_company(company).credit_limit = 500.0
        self.cust.with_company(company).use_partner_credit_limit = True
        # manager + cashier principals (reused approval framework)
        self.mgr = self.env['mezze.cashier'].create({'name': 'Mona', 'code': 'MGR6', 'role': 'manager'})
        self.mgr.set_pin('4321')
        self.csh = self.env['mezze.cashier'].create({'name': 'Sara', 'code': 'CSH6', 'role': 'cashier'})
        self.csh.set_pin('1111')
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, token='cc-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def _draft(self, price=1000.0, partner=None):
        s = self.open_test_session()
        o = self.create_order_in_test_session(price=price, session=s)
        vals = {'state': 'draft'}
        if partner:
            vals['partner_id'] = partner.id
        o.write(vals)
        self.env.flush_all()
        return o

    def _paycount(self, o):
        return self.env['pos.payment'].search_count([('pos_order_id', '=', o.id)])

    def _set_policy(self, policy):
        self.account_pm.mezze_credit_policy = policy
        self.env.flush_all()

    def _credit(self, partner=None):
        """Native partner.credit is a non-stored compute with NO @api.depends, so it
        is cached for the whole transaction. Production reads it fresh per HTTP
        request; a test in one transaction must invalidate to observe a new posting."""
        p = (partner or self.cust).with_company(self.company)
        p.invalidate_recordset(['credit'])
        return p.credit

    # -- customer required ----------------------------------------------------
    def test_customer_required(self):
        o = self._draft(price=100.0)   # no partner
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.account_pm.id,
                                           'tender_key': 'k'})
        self.assertEqual(st, 400)
        self.assertEqual(r['error'], 'customer_required')
        self.assertEqual(self._paycount(o), 0)

    # -- within limit / no limit ---------------------------------------------
    def test_within_limit_passes(self):
        self.cust.with_company(self.company).credit_limit = 10000.0
        o = self._draft(price=100.0, partner=self.cust)   # ~115 total < 10000
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.account_pm.id,
                                           'partner_id': self.cust.id, 'tender_key': 'k'})
        self.assertTrue(r['ok'], r)
        self.assertEqual(o.state, 'paid')
        self.assertEqual(self._paycount(o), 1)
        self.assertEqual(o.payment_ids.payment_method_id.type, 'pay_later')

    def test_no_limit_unlimited(self):
        self.company.account_use_credit_limit = False   # limits not enforced
        o = self._draft(price=5000.0, partner=self.cust)
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.account_pm.id,
                                           'partner_id': self.cust.id, 'tender_key': 'k'})
        self.assertTrue(r['ok'], r)
        self.assertEqual(o.state, 'paid')

    # -- ODOO_WARNING ---------------------------------------------------------
    def test_odoo_warning(self):
        self._set_policy('odoo_warning')
        o = self._draft(price=1000.0, partner=self.cust)   # over 500
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.account_pm.id,
                                           'partner_id': self.cust.id, 'tender_key': 'a'})
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'credit_warn')
        self.assertGreater(r['credit']['over'], 0)
        self.assertEqual(self._paycount(o), 0)
        # explicit continue
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.account_pm.id,
                                           'partner_id': self.cust.id, 'allow_credit': True, 'tender_key': 'b'})
        self.assertTrue(r['ok'])
        self.assertEqual(o.state, 'paid')

    # -- MANAGER_APPROVAL -----------------------------------------------------
    def test_manager_approval(self):
        self._set_policy('manager_approval')
        o = self._draft(price=1000.0, partner=self.cust)
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.account_pm.id,
                                           'partner_id': self.cust.id, 'tender_key': 'a'})
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'credit_needs_manager')
        # cashier cannot self-approve
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.account_pm.id,
                                           'partner_id': self.cust.id, 'manager_code': 'CSH6',
                                           'manager_pin': '1111', 'tender_key': 'b'})
        self.assertEqual(st, 403)
        self.assertEqual(r['error'], 'insufficient_role')
        # bad pin
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.account_pm.id,
                                           'partner_id': self.cust.id, 'manager_code': 'MGR6',
                                           'manager_pin': '0000', 'tender_key': 'c'})
        self.assertEqual(st, 403)
        self.assertEqual(r['error'], 'bad_credentials')
        self.assertEqual(self._paycount(o), 0)
        # manager approves
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.account_pm.id,
                                           'partner_id': self.cust.id, 'manager_code': 'MGR6',
                                           'manager_pin': '4321', 'manager_reason': 'trusted',
                                           'tender_key': 'd'})
        self.assertTrue(r['ok'], r)
        self.assertEqual(o.state, 'paid')
        self.assertEqual(self._paycount(o), 1)
        audit = self.env['mezze.audit.log'].search([('event', '=', 'customer_credit.approved')])
        self.assertTrue(audit)

    # -- HARD_BLOCK -----------------------------------------------------------
    def test_hard_block(self):
        self._set_policy('hard_block')
        o = self._draft(price=1000.0, partner=self.cust)
        for creds in ({}, {'manager_code': 'MGR6', 'manager_pin': '4321'}):
            st, r = self._post('/orders/pay', dict(creds, uuid=o.uuid,
                               payment_method_id=self.account_pm.id, partner_id=self.cust.id,
                               tender_key='hb'))
            self.assertEqual(st, 403)
            self.assertEqual(r['error'], 'credit_blocked')
        self.assertEqual(self._paycount(o), 0)

    # -- partial account tender: check the CHARGED amount only -----------------
    def test_partial_account_charged_only(self):
        # limit 500; order 1000; cash 600 first → remaining 400 to account (<= 500 ok)
        self._set_policy('hard_block')
        o = self._draft(price=1000.0, partner=self.cust)
        total = o.amount_total
        cash_amt = round(total - 400.0, 2)
        self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.cash.id,
                                   'amount': cash_amt, 'tender_key': 'c1'})
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.account_pm.id,
                                           'partner_id': self.cust.id, 'tender_key': 'a1'})
        self.assertTrue(r['ok'], r)   # 400 <= 500, allowed even under hard_block
        self.assertEqual(o.state, 'paid')
        self.assertEqual(self._paycount(o), 2)

    def test_mixed_cash_account(self):
        self.cust.with_company(self.company).credit_limit = 10000.0
        o = self._draft(price=1000.0, partner=self.cust)
        total = o.amount_total
        self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.cash.id,
                                   'amount': 300, 'tender_key': 'c1'})
        st, r = self._post('/orders/pay', {'uuid': o.uuid, 'payment_method_id': self.account_pm.id,
                                           'partner_id': self.cust.id, 'tender_key': 'a1'})
        self.assertTrue(r['ok'])
        self.assertEqual(o.state, 'paid')
        self.assertEqual(self._paycount(o), 2)
        acct_pay = o.payment_ids.filtered(lambda p: p.payment_method_id.type == 'pay_later')
        self.assertAlmostEqual(sum(acct_pay.mapped('amount')), round(total - 300, 2))

    # -- concurrency (serialised) --------------------------------------------
    def test_concurrency_hard_block(self):
        """Limit 1000; two 700 account sales. The second sees the first's in-session
        exposure (FOR UPDATE + re-read) → blocked. Final exposure <= limit."""
        self.cust.with_company(self.company).credit_limit = 1000.0
        self._set_policy('hard_block')
        oA = self._draft(price=1000.0, partner=self.cust)
        oB = self._draft(price=1000.0, partner=self.cust)
        # each charges exactly 700 to the account (partial tenders)
        _, rA = self._post('/orders/pay', {'uuid': oA.uuid, 'payment_method_id': self.account_pm.id,
                                           'partner_id': self.cust.id, 'amount': 700, 'tender_key': 'A'})
        stB, rB = self._post('/orders/pay', {'uuid': oB.uuid, 'payment_method_id': self.account_pm.id,
                                             'partner_id': self.cust.id, 'amount': 700, 'tender_key': 'B'})
        self.assertTrue(rA['ok'])
        self.assertEqual(stB, 403)
        self.assertEqual(rB['error'], 'credit_blocked')
        pos = self.cust._mezze_credit_position(self.company, self.pos_config)
        self.assertLessEqual(pos['exposure'], 1000.0)

    # -- deposit: native, no sales revenue -----------------------------------
    def test_deposit_no_revenue(self):
        before_orders = self.env['pos.order'].search_count([])
        pay = self.cust._mezze_customer_payment(
            self.company, 500.0, self._bank_journal(), memo='Account deposit', settle=False)
        # Odoo 19 payment states: action_post → in_process (bank) / paid (cash); the
        # journal ENTRY is posted either way (that is what moves partner.credit).
        self.assertIn(pay.state, ('in_process', 'paid'))
        self.assertEqual(pay.move_id.state, 'posted')
        # a deposit with no debt is available credit (negative exposure); no POS order,
        # no sales revenue was booked
        self.assertLessEqual(self._credit(), 0.0)
        self.assertEqual(self.env['pos.order'].search_count([]), before_orders)

    # -- settlement reduces the receivable -----------------------------------
    def test_settlement_reduces_credit(self):
        self._make_debt(1000.0)
        self.assertAlmostEqual(self._credit(), 1000.0, places=2)
        # partial
        self.cust._mezze_customer_payment(self.company, 400.0, self._bank_journal(),
                                          memo='Settlement', settle=True)
        self.assertAlmostEqual(self._credit(), 600.0, places=2)
        # full
        self.cust._mezze_customer_payment(self.company, 600.0, self._bank_journal(),
                                          memo='Settlement', settle=True)
        self.assertAlmostEqual(self._credit(), 0.0, places=2)

    # -- commercial partner ---------------------------------------------------
    def test_commercial_partner_exposure(self):
        child = self.env['res.partner'].create({'name': 'Cairo Office', 'parent_id': self.cust.id})
        self._make_debt(800.0)   # posted on commercial (parent)
        pos = child._mezze_credit_position(self.company, self.pos_config)
        self.assertEqual(pos['partner_id'], self.cust.id)          # tracked on commercial
        self.assertAlmostEqual(pos['exposure'], 800.0, places=2)

    # -- helpers --------------------------------------------------------------
    def _bank_journal(self):
        j = self.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', self.company.id)], limit=1)
        return j or self.env['account.journal'].create(
            {'name': 'CCBK', 'code': 'CCBK', 'type': 'bank', 'company_id': self.company.id})

    def _make_debt(self, amount):
        """Post a customer invoice so partner.credit == amount (a real receivable)."""
        income = self.env['account.account'].search(
            [('account_type', '=', 'income'), ('company_ids', 'in', self.company.id)], limit=1)
        inv = self.env['account.move'].with_company(self.company).create({
            'move_type': 'out_invoice', 'partner_id': self.cust.id,
            'invoice_line_ids': [(0, 0, {'name': 'On account', 'quantity': 1,
                                         'price_unit': amount, 'tax_ids': [(6, 0, [])],
                                         'account_id': income.id})]})
        inv.action_post()
        self.env.flush_all()
        return inv
