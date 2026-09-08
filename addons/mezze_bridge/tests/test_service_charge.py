"""The branch's service charge, and the one thing that must never be true of it.

The design's totals read Subtotal / Discount / **Service charge 12%** / VAT /
TOTAL. We had no service-charge concept at all.

The temptation is to add a row to the panel. That is precisely what must not
happen: a charge that exists only in the browser shows the guest a figure nobody
bills, reaches neither the receipt nor the journal nor ETA, and disappears on a
refund or a split. It is the same fabrication the customer display was making
with its invented 12%, which is why that one was deleted rather than fixed.

So the charge is a real priced LINE the server adds while pricing the order, and
these tests are about that: the money on the order, and the till agreeing with it.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestServiceCharge(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.token = 'svc-tok'
        ICP.set_param('mezze_bridge.api_token', cls.token)
        ICP.set_param('mezze_bridge.api_security', 'observe')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        ICP.set_param('mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.product.write({'available_in_pos': True, 'list_price': 100.0,
                           'taxes_id': [(5, 0, 0)]})
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.env.flush_all()

    def _sync(self, uuid, qty=1):
        r = self.url_open('/mezze/api/v1/orders/sync',
                          data=json.dumps({
                              'token': self.token, 'uuid': uuid,
                              'session_id': self.pos_sess.id, 'draft': True,
                              'lines': [{'product_id': self.product.id, 'qty': qty}]}),
                          headers={'Content-Type': 'application/json'}, timeout=40)
        body = r.json()
        self.assertTrue(body.get('ok'), body)
        return self.env['pos.order'].search([('uuid', '=', uuid)], limit=1)

    def test_01_no_charge_when_the_branch_levies_none(self):
        """The default. A branch that charges no service must get no line — not a
        zero one, which would print an empty row on every bill."""
        self.pos_config.write({'mezze_service_pct': 0.0})
        self.env.flush_all()
        order = self._sync('svc-off-1')
        names = order.lines.mapped('product_id.default_code')
        self.assertNotIn('SERVICE', names, 'a service line appeared on a branch that levies none')

    def test_02_the_charge_is_a_real_line_on_the_order(self):
        self.pos_config.write({'mezze_service_pct': 12.0})
        self.env.flush_all()
        order = self._sync('svc-on-1')
        svc = order.lines.filtered(lambda l: l.product_id.default_code == 'SERVICE')
        self.assertTrue(svc, 'the service charge never reached the order')
        self.assertAlmostEqual(svc.price_unit, 12.0, places=2,
                               msg='a 12 per cent charge on a 100 basket is 12, got %s'
                                   % svc.price_unit)

    def test_03_it_is_charged_on_the_food_and_moves_with_it(self):
        self.pos_config.write({'mezze_service_pct': 10.0})
        self.env.flush_all()
        one = self._sync('svc-qty-1', qty=1)
        three = self._sync('svc-qty-3', qty=3)
        la = one.lines.filtered(lambda l: l.product_id.default_code == 'SERVICE')
        lb = three.lines.filtered(lambda l: l.product_id.default_code == 'SERVICE')
        # Assert the lines EXIST before comparing them. `.price_unit` on an empty
        # recordset is 0.0, so `0 == 0 * 3` — this test passed against a build with
        # the whole charge removed until it checked.
        self.assertTrue(la and lb, 'no service line on either order')
        self.assertAlmostEqual(lb.price_unit, la.price_unit * 3, places=2,
                               msg='the charge does not follow the basket: %s vs %s'
                                   % (la.price_unit, lb.price_unit))

    def test_04_the_order_total_includes_it(self):
        """The point of it being a line: the tender has to cover it."""
        self.pos_config.write({'mezze_service_pct': 12.0})
        self.env.flush_all()
        order = self._sync('svc-total-1')
        self.assertAlmostEqual(order.amount_total, 112.0, places=2,
                               msg='the total does not carry the service charge: %s'
                                   % order.amount_total)

    def test_05_a_silly_rate_cannot_double_the_bill(self):
        """Clamped: a negative charge is a discount wearing the wrong name, and a
        rate above 100 is a typo that would otherwise more than double a bill."""
        self.pos_config.write({'mezze_service_pct': -5.0})
        self.env.flush_all()
        self.assertEqual(self.pos_config.mezze_service_rate(), 0.0)
        self.pos_config.write({'mezze_service_pct': 400.0})
        self.env.flush_all()
        self.assertEqual(self.pos_config.mezze_service_rate(), 1.0)

    def test_06_the_till_is_told_the_rate_and_its_tax(self):
        """The panel names the charge before the server prices it, so the two must
        be working from the same numbers. Without the tax rate a branch that taxes
        service would show a Charge button quoting less than the server bills."""
        self.pos_config.write({'mezze_service_pct': 12.0})
        self.env.flush_all()
        r = self.url_open('/mezze/api/v1/bootstrap',
                          data=json.dumps({'token': self.token,
                                           'config_id': self.pos_config.id}),
                          headers={'Content-Type': 'application/json'}, timeout=40)
        cfg = r.json().get('config') or {}
        self.assertAlmostEqual(cfg.get('service_pct'), 12.0, places=2,
                               msg='the till is not told the rate: %r' % cfg)
        self.assertIn('service_tax_pct', cfg,
                      'the till is not told what the charge is taxed at: %r' % cfg)

    def test_07_a_taxed_service_charge_is_taxed_on_the_order(self):
        """Whether service is taxable is a jurisdiction question, so it is a
        property of the product rather than a branch in the code."""
        self.pos_config.write({'mezze_service_pct': 10.0})
        self.env.flush_all()
        order = self._sync('svc-tax-seed')          # provisions the product
        prod = self.pos_config.mezze_service_product_id
        self.assertTrue(prod, 'the service product was never provisioned')
        tax = self.env['account.tax'].create({
            'name': 'VAT 14%', 'amount': 14.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'company_id': self.pos_config.company_id.id})
        prod.write({'taxes_id': [(6, 0, [tax.id])]})
        self.env.flush_all()
        order = self._sync('svc-tax-1')
        svc = order.lines.filtered(lambda l: l.product_id.default_code == 'SERVICE')
        self.assertTrue(svc.tax_ids, 'the service line carries no tax')
        r = self.url_open('/mezze/api/v1/bootstrap',
                          data=json.dumps({'token': self.token,
                                           'config_id': self.pos_config.id}),
                          headers={'Content-Type': 'application/json'}, timeout=40)
        self.assertAlmostEqual((r.json().get('config') or {}).get('service_tax_pct'),
                               14.0, places=1,
                               msg='the till would compute a different tax to the server')
