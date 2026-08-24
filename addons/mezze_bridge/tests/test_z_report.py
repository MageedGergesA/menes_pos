# -*- coding: utf-8 -*-
"""The shift's Z report.

Mezze had none. The only thing in the repository that looked like one was the design
prototype in ``static/pos.html``, whose figures are literals::

    <div class="zrow"><span>Gross sales</span><b class="num">EGP 38,940</b></div>

A picture of a report, not a report — and it is on a surface the product does not
ship, so no till could reach it either.

What matters most in these tests is that the numbers are the BRANCH's, and that the
two halves of the day are reported separately. A Z report that nets refunds into
sales lets a day of heavy returns read as a quiet day, which is the single thing the
shift report exists to prevent. So: gross, refunds and net are asserted independently
against orders built for the purpose.

The arithmetic itself is Odoo's ``report.point_of_sale.report_saledetails``, reused
rather than reimplemented — it already splits refunds from sales, reports tax per
rate, and reports the cash count with its difference.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_zreport')
class TestZReport(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'z-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.tax = env['account.tax'].sudo().create({
            'name': 'Z Tax 10%', 'amount': 10.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'price_include_override': 'tax_excluded',
            'company_id': cls.pos_config.company_id.id})
        cls.dish = env['product.product'].sudo().create({
            'name': 'Z Plate', 'available_in_pos': True, 'list_price': 100.0,
            'type': 'consu', 'taxes_id': [(6, 0, cls.tax.ids)]})
        env.flush_all()

    # -- helpers ---------------------------------------------------------
    def _sold(self, qty=1, sign=1):
        """A settled order. ``sign=-1`` makes it a refund (negative totals)."""
        net = 100.0 * qty * sign
        tax = 10.0 * qty * sign
        total = net + tax
        order = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {
                'product_id': self.dish.id, 'qty': qty * sign, 'price_unit': 100.0,
                'price_subtotal': net, 'price_subtotal_incl': total,
                'tax_ids': [(6, 0, self.tax.ids)]})],
            'amount_total': total, 'amount_paid': total,
            'amount_tax': tax, 'amount_return': 0.0,
        })
        self.env['pos.payment'].sudo().create({
            'pos_order_id': order.id, 'amount': total,
            'payment_method_id': self.cash.id})
        order.sudo().write({'state': 'paid'})
        self.env.flush_all()
        return order

    def _z(self, session=None):
        sid = (session or self.pos_sess).id
        r = self.url_open(
            '/mezze/api/v1/sessions/%s/z_report' % sid,
            data=json.dumps({'token': 'z-tok'}),
            headers={'Content-Type': 'application/json'})
        return r.json()

    # -- the report exists at all ---------------------------------------
    def test_01_the_endpoint_answers(self):
        d = self._z()
        self.assertTrue(d.get('ok'), 'there is no Z report: %s' % d)
        self.assertEqual(d.get('session'), self.pos_sess.name)

    def test_02_it_names_the_branch_and_currency(self):
        d = self._z()
        self.assertEqual((d.get('branch') or {}).get('name'), self.pos_config.name)
        self.assertEqual(d.get('currency'), self.pos_config.currency_id.name)
        self.assertTrue(d.get('company'), 'the report does not name the company')

    # -- the figures are real -------------------------------------------
    def test_03_gross_is_the_days_sales(self):
        self._sold(); self._sold()
        d = self._z()
        self.assertAlmostEqual(d['gross'], 220.0, places=2)
        self.assertEqual(d['orders'], 2)

    def test_04_refunds_are_reported_separately_not_netted(self):
        # THE property. Two sales and one refund must not read as "one quiet sale".
        self._sold(); self._sold()
        self._sold(sign=-1)
        d = self._z()
        self.assertAlmostEqual(d['gross'], 220.0, places=2,
                               msg='refunds have been netted into gross')
        self.assertAlmostEqual(d['refunds'], 110.0, places=2,
                               msg='the day\'s returns are not reported')
        self.assertAlmostEqual(d['net'], 110.0, places=2)
        self.assertEqual(d['refund_orders'], 1)

    def test_05_tax_is_reported_per_rate(self):
        self._sold()
        d = self._z()
        self.assertAlmostEqual(d['tax'], 10.0, places=2)
        names = [t['name'] for t in d.get('taxes') or []]
        self.assertIn('Z Tax 10%', names,
                      'tax must be named by rate, not blended: %s' % d.get('taxes'))

    def test_06_takings_are_broken_down_by_tender(self):
        self._sold()
        d = self._z()
        self.assertTrue(d.get('payments'), 'no per-tender breakdown')
        cash_rows = [p for p in d['payments'] if p.get('is_cash_count')]
        self.assertTrue(cash_rows, 'the cash drawer is not reported')

    def test_07_nothing_in_the_report_is_hardcoded(self):
        # The prototype's figures. If any of them appear, something is still reading
        # from the mock rather than from the session.
        d = self._z()
        blob = json.dumps(d)
        for literal in ('38940', '38,940', '4701', '12180', '21410', '4740'):
            self.assertNotIn(literal, blob,
                             'the Z report is echoing the prototype literal %r' % literal)

    def test_08_an_empty_shift_reports_zero_not_nothing(self):
        # A shift that sold nothing is a legitimate answer and must still print.
        cfg = self.pos_config.copy({'name': 'Z Empty Branch'})
        sess = self._open_session_for(cfg)
        d = self._z(sess)
        self.assertTrue(d.get('ok'), d)
        self.assertAlmostEqual(d['gross'], 0.0, places=2)
        self.assertAlmostEqual(d['net'], 0.0, places=2)
        self.assertEqual(d['orders'], 0)

    def test_09_an_unknown_session_is_refused(self):
        r = self.url_open(
            '/mezze/api/v1/sessions/99999999/z_report',
            data=json.dumps({'token': 'z-tok'}),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(r.json().get('error'), 'unknown_session')

    # -- it prints -------------------------------------------------------
    def test_10_it_renders_to_paper_from_the_same_figures(self):
        self._sold(); self._sold(sign=-1)
        from ..models.hardware_render import z_report_ticket
        d = self._z()
        text = z_report_ticket(d).to_text()
        self.assertIn('Z REPORT', text)
        self.assertIn('Gross', text)
        self.assertIn('Refunds', text, 'paper must show the returns, not just the net')
        self.assertIn('110.00', text, 'the net is missing from the paper:\n%s' % text)
        self.assertIn(self.pos_sess.name, text)

    def test_11_paper_omits_a_tax_section_when_nothing_was_taxed(self):
        cfg = self.pos_config.copy({'name': 'Z Untaxed Branch'})
        sess = self._open_session_for(cfg)
        from ..models.hardware_render import z_report_ticket
        text = z_report_ticket(self._z(sess)).to_text()
        self.assertNotIn('TAX', text,
                         'a branch that charged no tax must not get a tax section')


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_zreport')
class TestZReportReachable(MezzeHttpCase):
    """A report nothing can open is not a report.

    This is the lesson the Refund gap taught: ``/orders/refund`` was the best code in
    the module and no button reached it, so the capability did not exist as far as any
    cashier was concerned. The endpoint tests above would all pass with the Z report
    unreachable from every surface that ships, so this drives the real close screen.
    """
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.env.flush_all()

    def test_20_the_till_can_open_the_shift_report(self):
        self.browser_js('/mezze/pos?ws=close', r"""
            const $ = (s) => document.querySelector(s);
            async function waitFor(fn, label, ms=20000){
              const t0 = Date.now();
              while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){} 
                await new Promise(r=>setTimeout(r,120)); }
              throw new Error('timeout waiting for: ' + label);
            }
            function assert(c,m){ if(!c) throw new Error('assert failed: ' + m); }
            (async () => {
                await waitFor(() => $('[data-testid="mz-z-load"]'),
                              'the close screen offers a shift report');
                $('[data-testid="mz-z-load"]').click();
                await waitFor(() => $('[data-testid="mz-z-table"]')
                                 || $('[data-testid="mz-z-error"]'), 'the report or a reason');
                assert($('[data-testid="mz-z-table"]'),
                       'the shift report did not load: ' +
                       (($('[data-testid="mz-z-error"]')||{}).textContent || ''));
                const gross = $('[data-testid="mz-z-gross"]');
                const net = $('[data-testid="mz-z-net"]');
                assert(gross && net, 'gross and net must both be shown');
                // and a way to put it on paper
                assert($('[data-testid="mz-z-print"]'), 'the report cannot be printed');
                console.log('test successful');
            })().catch(e => { console.error(e.message || e); });
        """, login='admin')
