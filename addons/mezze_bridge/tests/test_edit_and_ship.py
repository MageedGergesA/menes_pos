# -*- coding: utf-8 -*-
"""Two core switches Mezze read and then ignored.

**Order edit tracking.** ``pos.order.is_edited`` and ``has_deleted_line`` drive
Odoo's own "this changed after it was sent" reporting and the order printer's change
slips. Mezze already knew the answer — ``mezze_fired`` is a cumulative snapshot of
what the kitchen has been told — and never wrote it down, so every Mezze order looked
pristine to core no matter how many times a guest changed their mind after firing.

The comparison is per PRODUCT, the granularity the snapshot has. A quantity going UP
is deliberately not an edit: more food is a new fire and the kitchen hears about it
as its own ticket. What counts is a quantity going DOWN or a fired product vanishing
— the ones nobody downstream would otherwise notice.

**Ship later.** ``pos.config.ship_later`` reached the boot payload and nothing acted
on it, so a till could offer the option and nothing would come of it. A shipping date
is a promise about stock, so a branch that has not enabled it gets a refusal rather
than a silent drop: a date that quietly does nothing is worse than one the cashier is
told they cannot set.
"""
import json
from datetime import date, timedelta

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_edit_ship')
class TestEditTrackingAndShipLater(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'es-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.soup = env['product.product'].sudo().create({
            'name': 'ES Soup', 'available_in_pos': True, 'list_price': 30.0,
            'type': 'consu'})
        cls.steak = env['product.product'].sudo().create({
            'name': 'ES Steak', 'available_in_pos': True, 'list_price': 90.0,
            'type': 'consu'})
        (cls.soup | cls.steak).write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='es-tok')),
                          headers={'Content-Type': 'application/json'})
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'raw': r.text[:200]}

    def _fire(self, uuid, lines):
        return self._post('/orders/fire', {
            'uuid': uuid, 'session_id': self.pos_sess.id, 'lines': lines})

    def _order(self, uuid):
        self.env.invalidate_all()
        return self.env['pos.order'].sudo().search([('uuid', '=', uuid)], limit=1)

    # ── edit tracking ────────────────────────────────────────────────────
    def test_01_an_untouched_order_is_not_edited(self):
        # Guard against flagging every order the moment it is fired.
        self._fire('es-clean', [{'product_id': self.soup.id, 'qty': 2}])
        order = self._order('es-clean')
        self.assertFalse(order.is_edited, 'a fired-once order was marked edited')
        self.assertFalse(order.has_deleted_line)

    def test_02_more_food_is_not_an_edit(self):
        # It is a NEW fire; the kitchen already gets its own ticket.
        self._fire('es-more', [{'product_id': self.soup.id, 'qty': 1}])
        self._fire('es-more', [{'product_id': self.soup.id, 'qty': 2}])
        self.assertFalse(self._order('es-more').is_edited,
                         'adding to an order was reported as an edit')

    def test_03_cutting_a_quantity_marks_the_line(self):
        # THE case core reports on and Mezze silently swallowed.
        self._fire('es-less', [{'product_id': self.soup.id, 'qty': 3}])
        order = self._order('es-less')
        order.lines.filtered(lambda l: l.product_id == self.soup).sudo().write({'qty': 1})
        self.env.flush_all()
        self._fire('es-less', [{'product_id': self.steak.id, 'qty': 1}])
        order = self._order('es-less')
        self.assertTrue(order.is_edited,
                        'a quantity cut after firing left no trace for core')

    def test_04_removing_a_fired_dish_marks_the_order(self):
        self._fire('es-gone', [{'product_id': self.soup.id, 'qty': 1},
                               {'product_id': self.steak.id, 'qty': 1}])
        order = self._order('es-gone')
        order.lines.filtered(lambda l: l.product_id == self.soup).sudo().unlink()
        self.env.flush_all()
        self._fire('es-gone', [{'product_id': self.steak.id, 'qty': 1}])
        order = self._order('es-gone')
        self.assertTrue(order.has_deleted_line,
                        'a dish that was cooked and then removed left no trace')

    # ── ship later ───────────────────────────────────────────────────────
    def test_10_a_branch_that_does_not_deliver_later_refuses_a_date(self):
        # Better than accepting a date that quietly does nothing.
        self.pos_config.sudo().write({'ship_later': False})
        code, res = self._post('/orders/sync', {
            'uuid': 'es-noship', 'session_id': self.pos_sess.id, 'draft': True,
            'lines': [{'product_id': self.soup.id, 'qty': 1}],
            'shipping_date': str(date.today() + timedelta(days=2))})
        self.assertEqual(code, 400, res)
        self.assertEqual(res.get('error'), 'ship_later_disabled')

    def test_11_a_branch_that_does_can_set_one(self):
        self.pos_config.sudo().write({'ship_later': True})
        when = date.today() + timedelta(days=3)
        code, res = self._post('/orders/sync', {
            'uuid': 'es-ship', 'session_id': self.pos_sess.id, 'draft': True,
            'lines': [{'product_id': self.soup.id, 'qty': 1}],
            'shipping_date': str(when)})
        self.assertEqual(code, 200, res)
        self.assertEqual(self._order('es-ship').shipping_date, when)

    def test_12_a_date_in_the_past_is_refused(self):
        # A delivery promised for yesterday is a promise nobody can keep.
        self.pos_config.sudo().write({'ship_later': True})
        code, res = self._post('/orders/sync', {
            'uuid': 'es-past', 'session_id': self.pos_sess.id, 'draft': True,
            'lines': [{'product_id': self.soup.id, 'qty': 1}],
            'shipping_date': str(date.today() - timedelta(days=1))})
        self.assertEqual(code, 400, res)
        self.assertEqual(res.get('error'), 'shipping_date_in_the_past')

    def test_13_nonsense_is_refused(self):
        self.pos_config.sudo().write({'ship_later': True})
        code, res = self._post('/orders/sync', {
            'uuid': 'es-junk', 'session_id': self.pos_sess.id, 'draft': True,
            'lines': [{'product_id': self.soup.id, 'qty': 1}],
            'shipping_date': 'next tuesday-ish'})
        self.assertEqual(code, 400, res)
        self.assertEqual(res.get('error'), 'bad_shipping_date')

    def test_14_an_ordinary_order_is_unaffected(self):
        # Guard against making shipping_date mandatory by accident.
        self.pos_config.sudo().write({'ship_later': True})
        code, res = self._post('/orders/sync', {
            'uuid': 'es-plain', 'session_id': self.pos_sess.id, 'draft': True,
            'lines': [{'product_id': self.soup.id, 'qty': 1}]})
        self.assertEqual(code, 200, res)
        self.assertFalse(self._order('es-plain').shipping_date)
