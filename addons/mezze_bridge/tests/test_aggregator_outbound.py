# -*- coding: utf-8 -*-
"""Telling the platform what happened to its order.

The inbound half was the loud gap; this is the quiet one, and it has two parts.

**Mezze pushed a callback for exactly two moments** — accepted and cancelled —
while the delivery moved through preparing, ready, assigned and out-for-delivery in
silence. For an aggregator order that is most of the point of integrating: their app
is what the customer is staring at, and a restaurant that never reports "on its way"
looks broken from the only screen the guest can see.

**And the two it did push were Mezze-shaped.** A platform wants its own field names
and its own words for a status, and it wants them independently — one may call the
field ``order.state`` and the status ``ON_THE_WAY``, another may keep a flat body and
say ``DISPATCHED``. So both are configurable per channel, and a channel with no
mapping keeps sending exactly what it always sent.

Two decisions worth stating:

* ``order_id`` is dropped from the vendor-shaped body. It is a database key of ours,
  meaningless to them, and there is no reason to hand an external party our primary
  keys.
* A status with no name of its own goes through unchanged rather than being dropped.
  A platform receiving a word it does not know will say so; silence looks identical
  to a restaurant that never bothered.
"""
import json

from odoo.tests import TransactionCase, tagged

from .common import MezzeHttpCase
from ..domain import aggregator_mapping as M


@tagged('post_install', '-at_install', 'mezze_aggregator')
class TestOutboundMappingPure(TransactionCase):
    """The shaping, with no ORM."""

    CANONICAL = {'external_id': 'T-9', 'status': 'out_for_delivery',
                 'pos_reference': 'POS/1', 'gross_total': 120.0}

    def test_01_the_native_shape_is_unchanged(self):
        body = M.build_status(self.CANONICAL)
        self.assertEqual(body['external_id'], 'T-9')
        self.assertEqual(body['status'], 'out_for_delivery')
        self.assertEqual(body['pos_reference'], 'POS/1')

    def test_02_a_vendor_shape_nests_and_renames(self):
        body = M.build_status(
            self.CANONICAL,
            {'external_id': 'order.reference', 'status': 'order.state',
             'order_ref': 'order.pos_ref', 'total': 'order.amount'},
            {'out_for_delivery': 'ON_THE_WAY'})
        self.assertEqual(body, {'order': {'reference': 'T-9', 'state': 'ON_THE_WAY',
                                          'pos_ref': 'POS/1', 'amount': 120.0}})

    def test_03_names_and_placement_are_independent(self):
        # One platform nests and keeps our words; another stays flat and renames.
        flat = M.build_status(self.CANONICAL, None, {'out_for_delivery': 'DISPATCHED'})
        self.assertEqual(flat['status'], 'DISPATCHED')
        nested = M.build_status(self.CANONICAL, {'status': 'a.b.c'})
        self.assertEqual(nested['a']['b']['c'], 'out_for_delivery')

    def test_04_an_unnamed_status_goes_through_unchanged(self):
        # Better than dropping it: a platform that does not know the word says so,
        # and silence looks identical to a restaurant that never bothered.
        body = M.build_status(dict(self.CANONICAL, status='ready'), None,
                              {'accepted': 'CONFIRMED'})
        self.assertEqual(body['status'], 'ready')

    def test_05_our_primary_key_is_never_sent(self):
        body = M.build_status(dict(self.CANONICAL, order_id=4242))
        self.assertNotIn('order_id', json.dumps(body))

    def test_06_place_builds_the_path_it_needs(self):
        self.assertEqual(M.place({}, 'a.b.c', 1), {'a': {'b': {'c': 1}}})
        # An existing non-dict on the way is replaced rather than crashing.
        self.assertEqual(M.place({'a': 5}, 'a.b', 1), {'a': {'b': 1}})

    def test_07_a_mapping_that_could_never_work_is_named(self):
        self.assertTrue(M.validate_status_mapping({'status': ''}))
        self.assertTrue(M.validate_status_mapping({'typo': 'x'}))
        self.assertEqual(M.validate_status_mapping({'status': 'order.state'}), [])
        self.assertEqual(M.validate_status_mapping(None), [])

    def test_08_the_lifecycle_vocabulary_matches_the_delivery_fsm(self):
        # If the FSM grows a state, this list has to grow with it or that state
        # silently never reaches the platform.
        from ..models.delivery import STATES
        fsm = {code for code, _label in STATES if code != 'placed'}
        self.assertFalse(fsm - set(M.STATUSES),
                         'delivery states with no outbound status: %r'
                         % (fsm - set(M.STATUSES)))


@tagged('post_install', '-at_install', 'mezze_aggregator')
class TestOutboundLifecycle(MezzeHttpCase):
    """The whole journey reaches the platform, not just two moments of it."""
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.channel = env['mezze.aggregator'].sudo().create({
            'code': 'vendory', 'name': 'Vendor Y', 'config_id': cls.pos_config.id,
            'secret': 'sh', 'notify_url': 'https://vendor.example/status',
            'status_mapping': json.dumps({'external_id': 'order.reference',
                                          'status': 'order.state'}),
            'status_names': json.dumps({'out_for_delivery': 'ON_THE_WAY',
                                        'ready': 'READY_FOR_PICKUP'}),
        })
        cls.order = env['pos.order'].sudo().create({
            'session_id': cls.pos_sess.id,
            'company_id': cls.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': cls.product.id, 'qty': 1,
                              'price_unit': 30.0, 'price_subtotal': 30.0,
                              'price_subtotal_incl': 30.0, 'tax_ids': [(6, 0, [])]})],
            'amount_total': 30.0, 'amount_paid': 30.0, 'amount_tax': 0.0,
            'amount_return': 0.0})
        cls.delivery = env['mezze.delivery'].sudo().create({
            'pos_order_id': cls.order.id, 'config_id': cls.pos_config.id,
            'customer_name': 'Omar', 'phone': '1', 'address': 'somewhere',
            'state': 'accepted'})
        cls.agg = env['mezze.aggregator.order'].sudo().create({
            'aggregator_id': cls.channel.id, 'external_id': 'VY-1',
            'pos_order_id': cls.order.id, 'delivery_id': cls.delivery.id,
            'state': 'received'})
        env.flush_all()

    def _events(self):
        return self.env['mezze.outbox.event'].sudo().search(
            [('event_type', '=', 'integration.webhook.deliver.v1')], order='id')

    def _payloads(self):
        out = []
        for e in self._events():
            try:
                out.append(json.loads(e.payload or '{}'))
            except ValueError:
                pass
        return out

    def test_20_a_state_change_reaches_the_platform(self):
        """THE gap: preparing/ready/out-for-delivery were never reported."""
        before = len(self._events())
        self.delivery.sudo()._transition('start_prep')
        self.assertGreater(len(self._events()), before,
                           'the platform was never told the food was being made')

    def test_21_the_whole_journey_is_reported(self):
        before = len(self._events())
        for action in ('start_prep', 'ready'):
            self.delivery.sudo()._transition(action)
        self.assertGreaterEqual(len(self._events()) - before, 2,
                                'the lifecycle went out in silence')

    def test_22_the_callback_is_vendor_shaped(self):
        self.delivery.sudo()._transition('start_prep')
        bodies = [p.get('payload') or {} for p in self._payloads()]
        nested = [b for b in bodies if isinstance(b.get('order'), dict)]
        self.assertTrue(nested, 'the callback kept Mezze\'s own shape: %r' % bodies)
        self.assertEqual(nested[-1]['order']['reference'], 'VY-1')

    def test_23_a_status_is_renamed_where_the_platform_wants_it(self):
        self.delivery.sudo()._transition('start_prep')
        self.delivery.sudo()._transition('ready')
        states = [(p.get('payload') or {}).get('order', {}).get('state')
                  for p in self._payloads()]
        self.assertIn('READY_FOR_PICKUP', states,
                      'the platform got our word, not theirs: %r' % states)

    def test_24_an_unnamed_status_still_goes(self):
        self.delivery.sudo()._transition('start_prep')
        states = [(p.get('payload') or {}).get('order', {}).get('state')
                  for p in self._payloads()]
        self.assertIn('preparing', states,
                      'a status with no vendor name was dropped: %r' % states)

    def test_25_a_delivery_with_no_channel_notifies_nobody(self):
        # An ordinary in-house delivery must not start calling an external API.
        plain_order = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1,
                              'price_unit': 10.0, 'price_subtotal': 10.0,
                              'price_subtotal_incl': 10.0, 'tax_ids': [(6, 0, [])]})],
            'amount_total': 10.0, 'amount_paid': 10.0, 'amount_tax': 0.0,
            'amount_return': 0.0})
        plain = self.env['mezze.delivery'].sudo().create({
            'pos_order_id': plain_order.id, 'config_id': self.pos_config.id,
            'customer_name': 'Sara', 'phone': '2', 'address': 'here',
            'state': 'accepted'})
        self.env.flush_all()
        before = len(self._events())
        plain.sudo()._transition('start_prep')
        self.assertEqual(len(self._events()), before,
                         'an in-house delivery called an external API')

    def test_26_a_platform_being_down_cannot_stop_the_floor(self):
        """A courier does not un-leave because an API timed out."""
        self.channel.sudo().write({'notify_url': False})
        self.delivery.sudo()._transition('start_prep')
        self.delivery.invalidate_recordset()
        self.assertEqual(self.delivery.state, 'preparing',
                         'a failed callback rolled back a real state change')

    def test_27_a_bad_status_mapping_is_refused_when_saved(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.channel.sudo().write({'status_mapping': '{"nonsense": "x"}'})
        with self.assertRaises(ValidationError):
            self.channel.sudo().write({'status_names': 'not json'})
