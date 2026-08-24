# -*- coding: utf-8 -*-
"""Laying out the floor from the product.

The only write Mezze ever made to ``restaurant.table`` was the QR token, so
arranging a room meant leaving the product for the Odoo backend — during service, on
a tablet, which is exactly when a floor actually changes: two tables pushed together
for a party of eight, a terrace opened because the weather turned.

Three properties matter more than the geometry:

* it edits CORE's own fields, so a floor authored here is the floor the native POS
  and the backend see. A parallel layout would be a second truth about one room;
* a table is DEACTIVATED, never deleted — past orders point at it, and a table that
  vanishes takes their history with it; and
* a table with an open order cannot be taken off the floor. Removing it then is how a
  table's money becomes unreachable from the floor it was taken on.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_floorplan')
class TestFloorEditing(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'fl-tok')
        # CREATE the floor rather than skip without one. An earlier version of this
        # file guarded every test with `skipTest('no floor on this branch')` and the
        # whole suite passed while skipping nine of eleven — the feature needs a
        # floor, so the fixture provides one.
        #
        # BEFORE the session opens: Odoo refuses to change "Is a Bar/Restaurant"
        # while one is open, which is the same class of ordering constraint that put
        # the gift-card payment method into an install-time hook.
        cls.floor = cls.pos_config.floor_ids[:1]
        if not cls.floor:
            if not cls.pos_config.module_pos_restaurant:
                cls.pos_config.sudo().write({'module_pos_restaurant': True})
            cls.floor = env['restaurant.floor'].sudo().create({
                'name': 'FL Main room',
                'pos_config_ids': [(6, 0, cls.pos_config.ids)]})
            cls.pos_config.invalidate_recordset()
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.dish = env['product.product'].sudo().create({
            'name': 'FL Plate', 'available_in_pos': True, 'list_price': 25.0,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='fl-tok')),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _save(self, **kw):
        return self._post('/floor/table/save', kw)

    # -- creating ----------------------------------------------------------
    def test_01_a_table_can_be_created(self):
        d = self._save(floor_id=self.floor.id, seats=4, width=60, height=60)
        self.assertTrue(d.get('ok'), d)
        self.assertEqual(d['action'], 'created')
        self.assertEqual(d['table']['seats'], 4)

    def test_02_it_is_numbered_without_being_asked(self):
        # Guests read table numbers aloud; a duplicate is an operational problem.
        first = self._save(floor_id=self.floor.id)['table']['table_number']
        second = self._save(floor_id=self.floor.id)['table']['table_number']
        self.assertNotEqual(first, second)

    def test_03_it_uses_core_geometry(self):
        # So the native POS and the backend see the same floor.
        d = self._save(floor_id=self.floor.id, position_h=120.5, position_v=88.0,
                       shape='round')
        tbl = self.env['restaurant.table'].sudo().browse(d['table']['id'])
        self.assertAlmostEqual(tbl.position_h, 120.5, places=2)
        self.assertAlmostEqual(tbl.position_v, 88.0, places=2)
        self.assertEqual(tbl.shape, 'round')

    # -- moving ------------------------------------------------------------
    def test_10_a_table_can_be_moved_and_resized(self):
        tid = self._save(floor_id=self.floor.id)['table']['id']
        d = self._save(table_id=tid, position_h=300, position_v=250,
                       width=90, height=45)
        self.assertEqual(d['action'], 'moved')
        tbl = self.env['restaurant.table'].sudo().browse(tid)
        self.assertAlmostEqual(tbl.position_h, 300.0, places=2)
        self.assertAlmostEqual(tbl.width, 90.0, places=2)

    def test_11_a_zero_sized_table_is_refused(self):
        # One nobody can tap.
        tid = self._save(floor_id=self.floor.id)['table']['id']
        d = self._save(table_id=tid, width=0)
        self.assertEqual(d.get('error'), 'bad_geometry')

    def test_12_nonsense_geometry_is_refused(self):
        tid = self._save(floor_id=self.floor.id)['table']['id']
        self.assertEqual(self._save(table_id=tid, width='wide').get('error'),
                         'bad_geometry')
        self.assertEqual(self._save(table_id=tid, seats=-2).get('error'),
                         'bad_geometry')

    def test_13_an_unknown_table_is_refused(self):
        self.assertEqual(self._save(table_id=99999999).get('error'), 'unknown_table')

    # -- removing ----------------------------------------------------------
    def test_20_a_removed_table_is_deactivated_not_deleted(self):
        # Past orders point at it.
        tid = self._save(floor_id=self.floor.id)['table']['id']
        d = self._post('/floor/table/remove', {'table_id': tid})
        self.assertTrue(d.get('ok'), d)
        tbl = self.env['restaurant.table'].sudo().with_context(
            active_test=False).browse(tid)
        self.assertTrue(tbl.exists(), 'the table was deleted, taking its history')
        self.assertFalse(tbl.active)

    def test_21_a_table_with_an_open_order_cannot_be_removed(self):
        # THE rule. Otherwise a table's money becomes unreachable from the floor.
        tid = self._save(floor_id=self.floor.id)['table']['id']
        self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'table_id': tid,
            'lines': [(0, 0, {'product_id': self.dish.id, 'qty': 1,
                              'price_unit': 25.0, 'price_subtotal': 25.0,
                              'price_subtotal_incl': 25.0, 'tax_ids': [(6, 0, [])]})],
            'amount_total': 25.0, 'amount_paid': 0.0,
            'amount_tax': 0.0, 'amount_return': 0.0})
        self.env.flush_all()
        d = self._post('/floor/table/remove', {'table_id': tid})
        self.assertFalse(d.get('ok'))
        self.assertEqual(d.get('error'), 'table_in_use')
        self.assertTrue(self.env['restaurant.table'].sudo().browse(tid).active,
                        'a table with a live bill was taken off the floor')

    def test_22_removal_is_audited(self):
        tid = self._save(floor_id=self.floor.id)['table']['id']
        self._post('/floor/table/remove', {'table_id': tid})
        row = self.env['mezze.audit.log'].sudo().search(
            [('event', '=', 'floor.table_removed')], order='id desc', limit=1)
        self.assertTrue(row, 'taking a table off the floor was not recorded')
        self.assertEqual(row.severity, 'warning')
