"""V2C Phase 0 — KDS domain gate: fired-order VOID cascades to the kitchen.

Closes the V2B finding that voiding a fired order left its live kitchen tickets
active. cancel_for_order() must cancel every LIVE ticket exactly once, leave
terminal (served/cancel) tickets untouched, and be idempotent under repeat/void
races (row-locked). Pure domain (no HTTP) so it runs in the headless suite.
"""
from odoo.tests import tagged

from .common import MezzePosCase


@tagged('post_install', '-at_install', 'mezze_invariants')
class TestKdsVoidCascade(MezzePosCase):
    fixture_profile = 'POS'

    def _order_with_tickets(self):
        order = self.create_order_in_test_session()
        T = self.env['mezze.kds.ticket']
        fired = T.create({'pos_order_id': order.id, 'station': 'Kitchen', 'state': 'fired'})
        prep = T.create({'pos_order_id': order.id, 'station': 'Bar', 'state': 'preparing'})
        served = T.create({'pos_order_id': order.id, 'station': 'Pastry', 'state': 'served'})
        return order, fired, prep, served

    def test_void_cancels_live_tickets_and_spares_served(self):
        order, fired, prep, served = self._order_with_tickets()
        cancelled = self.env['mezze.kds.ticket'].cancel_for_order(order)
        self.assertEqual(set(cancelled.ids), {fired.id, prep.id},
                         'both LIVE tickets (fired + preparing) are cancelled')
        self.assertEqual(fired.state, 'cancel')
        self.assertEqual(prep.state, 'cancel')
        self.assertEqual(served.state, 'served',
                         'a served ticket (food already made) is NOT retroactively cancelled')

    def test_void_is_idempotent(self):
        order, fired, prep, served = self._order_with_tickets()
        first = self.env['mezze.kds.ticket'].cancel_for_order(order)
        self.assertEqual(len(first), 2)
        again = self.env['mezze.kds.ticket'].cancel_for_order(order)
        self.assertEqual(len(again), 0, 'a repeat void cancels nothing new (idempotent)')
        self.assertEqual(fired.state, 'cancel')

    def test_cancel_is_terminal(self):
        # a cancelled ticket cannot be advanced back into the workflow
        order, fired, prep, served = self._order_with_tickets()
        self.env['mezze.kds.ticket'].cancel_for_order(order)
        changed, reason = fired._set_state('preparing')
        self.assertFalse(changed)
        self.assertEqual(reason, 'terminal')
        self.assertEqual(fired.state, 'cancel')

    def test_no_tickets_is_safe(self):
        order = self.create_order_in_test_session()
        self.assertEqual(len(self.env['mezze.kds.ticket'].cancel_for_order(order)), 0)
