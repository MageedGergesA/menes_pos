# -*- coding: utf-8 -*-
"""Promising a time the branch can actually keep.

A preset that "manages orders by time" carries a capacity — ``slots_per_interval`` —
and Mezze read none of it, so a scheduled order type was a label with no schedule
behind it.

Core computes slot USAGE (``_compute_slots_usage``) and leaves the capacity decision
to its front end. That is the part worth doing differently: a capacity enforced in a
browser is not a capacity. Two tills read the same free slot, both book it, and a
kitchen that promised five orders at 19:40 has seven. The check therefore runs on the
server, under a per-preset lock, so the read and the write are one step.

The usage map is core's own, so a slot cannot look full in one product and free in
the other.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_slots')
class TestPresetSlots(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'sl-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.dish = env['product.product'].sudo().create({
            'name': 'SL Plate', 'available_in_pos': True, 'list_price': 40.0,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        Preset = env['pos.preset'].sudo()
        # Capacity of two, so the third booking is the one that must be refused.
        cls.timed = Preset.create({'name': 'SL Collection', 'use_timing': True,
                                   'slots_per_interval': 2, 'interval_time': 20})
        cls.untimed = Preset.create({'name': 'SL Walk in'})
        cls.pos_config.sudo().write({
            'use_presets': True,
            'default_preset_id': cls.untimed.id,
            'available_preset_ids': [(6, 0, (cls.timed | cls.untimed).ids)],
        })
        env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='sl-tok')),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _book(self, uuid, when, preset=None):
        return self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.pos_sess.id, 'draft': True,
            'preset_id': (preset or self.timed).id, 'preset_time': when,
            'lines': [{'product_id': self.dish.id, 'qty': 1}]})

    SLOT = '2026-08-24 19:40:00'

    # -- reading what is free ----------------------------------------------
    def test_01_a_timed_preset_reports_its_capacity(self):
        d = self._post('/preset/slots', {'preset_id': self.timed.id})
        self.assertTrue(d.get('ok'), d)
        self.assertTrue(d['use_timing'])
        self.assertEqual(d['capacity'], 2)
        self.assertEqual(d['interval_minutes'], 20)

    def test_02_an_untimed_preset_says_so_rather_than_looking_full(self):
        # An empty list would read as "fully booked".
        d = self._post('/preset/slots', {'preset_id': self.untimed.id})
        self.assertTrue(d.get('ok'), d)
        self.assertFalse(d['use_timing'])

    def test_03_a_preset_the_branch_does_not_offer_is_refused(self):
        other = self.env['pos.preset'].sudo().create({'name': 'SL Foreign'})
        self.assertEqual(
            self._post('/preset/slots', {'preset_id': other.id}).get('error'),
            'unknown_preset')

    # -- booking ------------------------------------------------------------
    def test_10_a_booking_is_recorded_on_the_order(self):
        # The slot is counted FROM orders, so a booking that lives only on a till is
        # a place nobody else knows is taken.
        d = self._book('sl-1', self.SLOT)
        self.assertTrue(d.get('ok'), d)
        self.env.invalidate_all()
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'sl-1')], limit=1)
        self.assertEqual(order.preset_id, self.timed)
        self.assertTrue(order.preset_time)

    def test_11_the_slot_shows_as_taken_afterwards(self):
        self._book('sl-2', self.SLOT)
        d = self._post('/preset/slots', {'preset_id': self.timed.id})
        taken = {s['at']: s for s in d['slots']}
        self.assertIn(self.SLOT, taken)
        self.assertEqual(taken[self.SLOT]['taken'], 1)
        self.assertEqual(taken[self.SLOT]['free'], 1)

    def test_12_a_full_slot_refuses_the_next_order(self):
        # THE rule. Capacity that is not enforced is not capacity.
        self.assertTrue(self._book('sl-3', self.SLOT).get('ok'))
        self.assertTrue(self._book('sl-4', self.SLOT).get('ok'))
        d = self._book('sl-5', self.SLOT)
        self.assertFalse(d.get('ok'), 'a third order took a slot of two: %s' % d)
        self.assertEqual(d.get('error'), 'slot_full')
        self.assertEqual(d.get('capacity'), 2)

    def test_13_re_syncing_the_same_order_does_not_use_a_second_place(self):
        # An order already holding a slot is not competing with itself — otherwise a
        # cashier adding a line to a booked order would lose the booking.
        self.assertTrue(self._book('sl-6', self.SLOT).get('ok'))
        self.assertTrue(self._book('sl-7', self.SLOT).get('ok'))
        again = self._book('sl-6', self.SLOT)
        self.assertTrue(again.get('ok'),
                        'a booked order was refused its own slot: %s' % again)

    def test_14_another_time_is_still_free(self):
        self._book('sl-8', self.SLOT)
        self._book('sl-9', self.SLOT)
        d = self._book('sl-10', '2026-08-24 20:00:00')
        self.assertTrue(d.get('ok'), 'a different slot was refused: %s' % d)

    def test_15_an_untimed_preset_has_no_limit(self):
        for i in range(4):
            d = self._post('/orders/sync', {
                'uuid': 'sl-free-%d' % i, 'session_id': self.pos_sess.id,
                'draft': True, 'preset_id': self.untimed.id,
                'preset_time': self.SLOT,
                'lines': [{'product_id': self.dish.id, 'qty': 1}]})
            self.assertTrue(d.get('ok'), d)

    def test_16_a_nonsense_time_is_refused(self):
        d = self._book('sl-bad', 'half past tea')
        self.assertEqual(d.get('error'), 'bad_preset_time')
