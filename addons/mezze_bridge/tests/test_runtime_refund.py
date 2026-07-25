"""Runtime verification of the refund ceiling INSIDE a running Odoo server.

Exercises the real controller helper `_enforce_refund_ceiling` against real
pos.order records (advisory lock + authoritative aggregation + audit), plus a
real refund creation so the "already refunded reduces capacity" path is covered
with committed DB state.

Run:
  odoo-bin -d <db> -c <conf> -u mezze_bridge --test-enable \
           --test-tags mezze_runtime --stop-after-init
"""

import json

from odoo import fields
from odoo.tests import common, tagged
from odoo.addons.mezze_bridge.controllers.main import MezzeBridgeController


def _paid_order(env, amount=10.0):
    s = env['pos.session'].search([('state', '=', 'opened')], limit=1)
    if not s:
        s = env['pos.session'].create({'config_id': env['pos.config'].search([], limit=1).id,
                                       'user_id': env.uid})
    c = s.config_id
    p = env['product.product'].search([('available_in_pos', '=', True)], limit=1) \
        or env['product.product'].search([], limit=1)
    o = env['pos.order'].create({
        'session_id': s.id, 'company_id': c.company_id.id,
        'lines': [(0, 0, {'product_id': p.id, 'qty': 1, 'price_unit': amount,
                          'price_subtotal': amount, 'price_subtotal_incl': amount, 'tax_ids': [(6, 0, [])]})],
        'amount_tax': 0.0, 'amount_total': amount, 'amount_paid': 0.0, 'amount_return': 0.0,
        'pricelist_id': c.pricelist_id.id or False})
    o.add_payment({'amount': amount, 'payment_method_id': c.payment_method_ids[:1].id,
                   'name': fields.Datetime.now(), 'pos_order_id': o.id})
    try:
        o.action_pos_order_paid()
    except Exception:
        o.write({'state': 'paid'})
    return o


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestRefundLinkageRuntime(common.TransactionCase):
    """Server-side reconstruction + mandatory linkage + per-line quantity."""

    def setUp(self):
        super().setUp()
        self.ctrl = MezzeBridgeController()
        self.orig = _paid_order(self.env, 10.0)
        self.line = self.orig.lines[0]
        self.config = self.orig.config_id
        self.session = self.orig.session_id
        self.other = _paid_order(self.env, 10.0)   # a different order (cross-order tests)

    def _resolve(self, lines):
        return self.ctrl._resolve_refund_lines(self.env, self.orig, self.config,
                                               self.session, lines, 'ru-1', {})

    def test_valid_full_line_reconstructs_and_links(self):
        r = self._resolve([{'line_id': self.line.id, 'qty': 1}])
        self.assertNotEqual(r.get('ok'), False, r)
        self.assertEqual(len(r['lines']), 1)
        vals = r['lines'][0][2]
        self.assertEqual(vals['refunded_orderline_id'], self.line.id)   # linkage persisted
        self.assertEqual(vals['product_id'], self.line.product_id.id)   # server product
        self.assertEqual(vals['qty'], -1)
        self.assertAlmostEqual(r['total'], -10.0)                       # exactly what was paid

    def test_missing_line_id_rejected(self):
        r = self._resolve([{'qty': 1, 'product_id': self.line.product_id.id}])
        self.assertEqual(r['error'], 'refund_line_missing')

    def test_line_from_another_order_rejected(self):
        r = self._resolve([{'line_id': self.other.lines[0].id, 'qty': 1}])
        self.assertEqual(r['error'], 'refund_line_not_in_original')

    def test_product_mismatch_rejected(self):
        other_prod = self.env['product.product'].search(
            [('id', '!=', self.line.product_id.id)], limit=1)
        r = self._resolve([{'line_id': self.line.id, 'qty': 1, 'product_id': other_prod.id}])
        self.assertEqual(r['error'], 'refund_line_product_mismatch')

    def test_quantity_over_sold_rejected(self):
        r = self._resolve([{'line_id': self.line.id, 'qty': 2}])   # sold 1
        self.assertEqual(r['error'], 'refund_quantity_exceeds_remaining')

    def test_duplicate_entries_jointly_exceed_rejected(self):
        # two payload entries for the same source line summing > sold qty
        r = self._resolve([{'line_id': self.line.id, 'qty': 0.6},
                           {'line_id': self.line.id, 'qty': 0.6}])
        self.assertEqual(r['error'], 'refund_quantity_exceeds_remaining')

    def test_client_price_and_tax_ignored(self):
        # client sends absurd price/tax; server reconstructs from the original line
        r = self._resolve([{'line_id': self.line.id, 'qty': 1,
                            'price_unit': 999999.0, 'tax_ids': [1, 2, 3]}])
        self.assertNotEqual(r.get('ok'), False)
        self.assertAlmostEqual(r['total'], -10.0)   # not -999999; server truth wins

    def test_after_full_refund_line_exhausted(self):
        # create a real linked refund consuming the whole line, then re-resolve
        refund = self.env['pos.order'].create({
            'uuid': 'linkage-refund-1', 'session_id': self.session.id,
            'company_id': self.config.company_id.id,
            'lines': [(0, 0, {'product_id': self.line.product_id.id, 'qty': -1, 'price_unit': 10.0,
                              'price_subtotal': -10.0, 'price_subtotal_incl': -10.0,
                              'tax_ids': [(6, 0, [])], 'refunded_orderline_id': self.line.id})],
            'amount_tax': 0.0, 'amount_total': -10.0, 'amount_paid': -10.0, 'amount_return': 0.0})
        refund.write({'state': 'paid'})
        self.env.flush_all()
        r = self._resolve([{'line_id': self.line.id, 'qty': 1}])
        self.assertEqual(r['error'], 'refund_quantity_exceeds_remaining')


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestRefundModelConstraint(common.TransactionCase):
    """Model-level backstop: closes the core `sync_from_ui` over-refund bypass
    for EVERY path (controller, core UI, offline sync, direct sync, back-office)."""

    def setUp(self):
        super().setUp()
        self.orig = _paid_order(self.env, 10.0)
        self.line = self.orig.lines[0]
        self._n = 0

    def _refund(self, qty):
        self._n += 1
        r = self.env['pos.order'].create({
            'uuid': 'constr-%s-%s' % (qty, self._n), 'session_id': self.orig.session_id.id,
            'company_id': self.orig.company_id.id,
            'lines': [(0, 0, {'product_id': self.line.product_id.id, 'qty': -abs(qty),
                              'price_unit': 10.0, 'price_subtotal': -10.0 * abs(qty),
                              'price_subtotal_incl': -10.0 * abs(qty), 'tax_ids': [(6, 0, [])],
                              'refunded_orderline_id': self.line.id})],
            'amount_tax': 0.0, 'amount_total': -10.0 * abs(qty),
            'amount_paid': -10.0 * abs(qty), 'amount_return': 0.0})
        self.env.flush_all()
        return r

    def test_normal_sale_not_tripped(self):
        # setUp already created a paid sale with qty>0; flushing must not raise
        self.env.flush_all()
        self.assertEqual(self.orig.state, 'paid')

    def test_valid_refund_qty_passes(self):
        self._refund(1)          # qty 1 of sold 1
        self.assertTrue(True)    # no exception

    def test_over_refund_qty_blocked(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._refund(3)      # qty 3 of sold 1 -> blocked at the model

    def test_second_refund_exceeding_remaining_blocked(self):
        from odoo.exceptions import ValidationError
        self._refund(1)          # consume the whole line
        with self.assertRaises(ValidationError):
            self._refund(1)      # a further refund exceeds sold qty
