# -*- coding: utf-8 -*-
"""What the kitchen actually gets on paper.

Two gaps, both invisible to a branch that uses screens and both serious to one that
does not:

* the ticket printed ``qty x name`` and nothing else. The configured choices ride
  along inside ``full_product_name`` ("Burger (no onion)"), so those survived — but
  the cashier's TYPED instruction did not. "allergy - no nuts" reached the kitchen
  display and never the paper, which is the one line on the ticket that matters most;
* nothing printed on its own. The endpoint existed and somebody had to press it, and
  on a busy pass the ticket that gets forgotten is the one the kitchen never knew
  about.

The renderer now lives beside the receipt renderer for the reason the receipt does:
a live ticket and a queued one must be the same paper. So must the station ROUTING —
it moved to ``domain/station_routing`` because the controller and the print consumer
both need the answer, and two copies disagree the first time somebody adds a keyword
to one of them.

Auto-print is OFF by default. A version bump must not start driving a printer that a
branch has not asked it to.
"""
import json

from odoo.tests import TransactionCase, tagged

from .common import MezzeHttpCase
from ..domain import station_routing


@tagged('post_install', '-at_install', 'mezze_kitchen_print')
class TestStationRouting(TransactionCase):
    """The rule, with no ORM — now that two callers share it."""

    def test_01_drinks_and_food_go_to_different_stations(self):
        self.assertEqual(station_routing.station_for('Flat White'), 'Barista')
        self.assertEqual(station_routing.station_for('Fresh Orange Juice'), 'Bar')
        self.assertEqual(station_routing.station_for('Margherita Pizza'), 'Pizza')
        self.assertEqual(station_routing.station_for('Caesar Salad'), 'Salad')

    def test_02_anything_unmatched_lands_in_the_kitchen(self):
        # The safe default: a ticket at the wrong station is noticed in seconds, a
        # ticket at NO station is not noticed at all.
        self.assertEqual(station_routing.station_for('Lamb Chops'), 'Kitchen')
        self.assertEqual(station_routing.station_for(''), 'Kitchen')
        self.assertEqual(station_routing.station_for(None), 'Kitchen')

    def test_03_the_category_counts_too(self):
        """A product named nothing useful still routes by its POS category.

        Matching is on SUBSTRINGS, so a plural category works too — "Desserts"
        contains "dessert". Asserted deliberately: an earlier version of this test
        expected the plural to miss, which would have made the rule useless on every
        real menu, where categories are named in the plural.
        """
        self.assertEqual(
            station_routing.station_for('House Special', ['Mains']), 'Kitchen')
        self.assertEqual(
            station_routing.station_for('House Special', ['Dessert']), 'Pastry')
        self.assertEqual(
            station_routing.station_for('House Special', ['Desserts']), 'Pastry')


@tagged('post_install', '-at_install', 'mezze_kitchen_print')
class TestKitchenTicket(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'kp-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.dish = env['product.product'].sudo().create({
            'name': 'KP Steak', 'available_in_pos': True, 'list_price': 90.0,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _order(self, note='', seat=0):
        vals = {'product_id': self.dish.id, 'qty': 1, 'price_unit': 90.0,
                'price_subtotal': 90.0, 'price_subtotal_incl': 90.0,
                'tax_ids': [(6, 0, [])]}
        if note:
            vals['customer_note'] = note
        if seat:
            vals['mezze_seat'] = seat
        order = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, vals)],
            'amount_total': 90.0, 'amount_paid': 0.0, 'amount_tax': 0.0,
            'amount_return': 0.0})
        self.env.flush_all()
        return order

    def _paper(self, order, station=None):
        from ..models.hardware_render import kitchen_ticket
        return kitchen_ticket(order, station, 48).to_text()

    def test_10_the_dish_is_on_the_ticket(self):
        self.assertIn('KP Steak', self._paper(self._order()))

    def test_11_the_typed_instruction_reaches_the_paper(self):
        # THE gap. It reached the screen and not the print.
        paper = self._paper(self._order(note='allergy - no nuts'))
        self.assertIn('allergy - no nuts', paper,
                      'the cashier note never reached the kitchen:\n%s' % paper)

    def test_12_a_seat_reaches_the_paper(self):
        # A cook plating four covers needs to know which is which.
        paper = self._paper(self._order(seat=3))
        self.assertIn('seat 3', paper, paper)

    def test_13_an_ordinary_line_stays_uncluttered(self):
        # Guard against printing an empty marker on every line of every ticket.
        paper = self._paper(self._order())
        self.assertNotIn('!', paper)
        self.assertNotIn('seat', paper)

    def test_14_one_renderer_serves_both_paths(self):
        """A queued ticket and a live one must be the same paper.

        Asserted structurally: the controller must not carry a second renderer, or
        the two drift and the way anyone finds out is a cook working from a ticket
        missing the line the guest phoned about.
        """
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, '..', 'controllers', 'hardware.py'),
                  encoding='utf-8') as fh:
            src = fh.read()
        self.assertIn('hardware_render.kitchen_ticket', src,
                      'the controller stopped delegating to the shared renderer')


@tagged('post_install', '-at_install', 'mezze_kitchen_print')
class TestAutoPrintOnFire(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'kf-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.dish = env['product.product'].sudo().create({
            'name': 'KF Pizza', 'available_in_pos': True, 'list_price': 60.0,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        cls.printer = env['mezze.printer'].sudo().create({
            'name': 'Pass Printer', 'printer_type': 'kitchen',
            'config_id': cls.pos_config.id, 'host': '10.7.7.7', 'width': 48})
        env.flush_all()

    def _fire(self, uuid):
        r = self.url_open('/mezze/api/v1/orders/fire',
                          data=json.dumps({'token': 'kf-tok', 'uuid': uuid,
                                           'session_id': self.pos_sess.id,
                                           'lines': [{'product_id': self.dish.id,
                                                      'qty': 1}]}),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _print_events(self):
        return self.env['mezze.outbox.event'].sudo().search(
            [('event_type', '=', 'hardware.print.requested.v1')])

    def test_20_off_by_default(self):
        # A version bump must not start driving a printer nobody asked it to.
        before = len(self._print_events())
        self.assertTrue(self._fire('kf-off').get('ok'))
        self.assertEqual(len(self._print_events()), before,
                         'a fire printed on a branch that never opted in')

    def test_21_a_branch_can_turn_it_on(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.hw_auto_kitchen', '1')
        before = len(self._print_events())
        self.assertTrue(self._fire('kf-on').get('ok'))
        after = self._print_events()
        self.assertGreater(len(after), before, 'nothing was queued for the printer')
        payloads = [json.loads(e.payload or '{}') for e in after]
        kitchen = [p for p in payloads if p.get('doc_type') == 'kitchen']
        self.assertTrue(kitchen, 'the queued job is not a kitchen ticket: %r' % payloads)
        self.assertTrue(kitchen[0].get('station'), 'the job names no station')

    def test_22_the_same_fire_cannot_print_twice(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.hw_auto_kitchen', '1')
        self._fire('kf-dup')
        first = len(self._print_events())
        self._fire('kf-dup')          # same uuid — an idempotent re-fire
        self.assertEqual(len(self._print_events()), first,
                         'a re-delivered fire queued a second ticket')
