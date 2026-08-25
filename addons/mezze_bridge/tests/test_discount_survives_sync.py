# -*- coding: utf-8 -*-
"""An approved discount must still be there when the guest pays.

Found by driving a real till in a browser, not by the suite. A manager entered a
code, a PIN and a reason to authorise 50% off; the cart re-priced correctly and
the audit log recorded ``420.00 -> 210.00``. The payment screen then asked for
**420.00**, and so did the database.

The cause was a property name. A cart line carries its price as ``unit_price`` --
``addProduct`` writes it, the cart displays from it, the crash-safe draft
round-trips it -- but ``toSyncLines()`` read ``price_unit``, which nothing sets.
It was always ``undefined``, so the payload omitted the price and the server
re-priced the line at LIST on the next sync. Opening the payment screen re-syncs
the cart, so the discount was wiped on the way to the money.

The blast radius was wider than discounts: a **comp** is stored as a 100% discount
on the line (see ``_loadOrderLines``), and a manual price override is the same
mechanism, so both reverted to full price too.

What is pinned here is the invariant rather than the bug: the cart, the payment
screen and the database must agree about what is owed. That is the "three sources
of truth" shape -- a total shown in one place, computed in another, and stored in
a third -- which is where this codebase's money defects keep being found.
"""
import json

from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_discount')
class TestDiscountSurvivesSync(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'ds-tok')
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_security', 'enforce')
        cls.sess = cls._open_session_for(cls.pos_config)
        cls.mgr = env['mezze.cashier'].sudo().create(
            {'name': 'Nadia Manager', 'code': 'DSMGR', 'role': 'manager'})
        cls.mgr.set_pin('4321')
        cls.dish = env['product.product'].sudo().create({
            'name': 'DS Plate', 'available_in_pos': True, 'list_price': 100.0,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='ds-tok')),
                          headers={'Content-Type': 'application/json'})
        try:
            return r.status_code, r.json()
        except Exception:                                        # noqa: BLE001
            return r.status_code, {'raw': r.text[:200]}

    def _order(self):
        return self.env['pos.order'].sudo().search(
            [('uuid', '=', self.UUID), ('session_id', '=', self.sess.id)], limit=1)

    UUID = 'ds-order-1'

    def _cart_lines(self, unit_price=None):
        """What the browser sends. `unit_price` present = a server-restored price,
        which is exactly what the cart holds after a discount is applied."""
        line = {'product_id': self.dish.id, 'qty': 2}
        if unit_price is not None:
            line['price_unit'] = unit_price
        return [line]

    def _sync(self, lines):
        return self._post('/orders/sync', {
            'uuid': self.UUID, 'session_id': self.sess.id, 'draft': True,
            'lines': lines})

    # ── the invariant ────────────────────────────────────────────────────
    def test_01_an_approved_discount_survives_the_next_sync(self):
        """THE bug. Opening the payment screen re-syncs the cart; the discount
        must still be there afterwards."""
        self._sync(self._cart_lines())
        order = self._order()
        self.assertAlmostEqual(order.amount_total, 200.0, places=2)

        c, res = self._post('/orders/discount', {
            'session_id': self.sess.id, 'order_uuid': self.UUID,
            'scope': 'order', 'percent': 50.0, 'reason': 'service recovery',
            'manager_code': 'DSMGR', 'manager_pin': '4321'})
        self.assertTrue(res.get('ok'), res)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 100.0, places=2,
                               msg='the discount did not apply at all')

        # The cart now holds the server's EFFECTIVE price, and re-sends it. This is
        # what goToPayment() does before the payment screen reads the total.
        self._sync(self._cart_lines(unit_price=50.0))
        order.invalidate_recordset()
        self.assertAlmostEqual(
            order.amount_total, 100.0, places=2,
            msg='re-syncing the cart reverted the approved discount to list price: '
                'the guest is charged %.2f instead of 100.00' % order.amount_total)

    def test_02_a_comp_survives_the_next_sync(self):
        """Same mechanism. A comp is stored as a 100% discount on the line, so it
        was reverted to full price by the same missing property."""
        self._sync(self._cart_lines())
        order = self._order()
        c, res = self._post('/orders/discount', {
            'session_id': self.sess.id, 'order_uuid': self.UUID,
            'scope': 'order', 'percent': 100.0, 'reason': 'kitchen error',
            'manager_code': 'DSMGR', 'manager_pin': '4321'})
        self.assertTrue(res.get('ok'), res)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 0.0, places=2)

        self._sync(self._cart_lines(unit_price=0.0))
        order.invalidate_recordset()
        self.assertAlmostEqual(
            order.amount_total, 0.0, places=2,
            msg='a comped order was re-priced to %.2f on the way to payment'
                % order.amount_total)

    def test_03_a_price_the_cart_sends_is_the_price_charged(self):
        """The underlying contract, stated without reference to discounts: when the
        cart names a unit price, the server must use it and not the list price."""
        self._sync(self._cart_lines(unit_price=37.5))
        order = self._order()
        self.assertAlmostEqual(order.amount_total, 75.0, places=2,
                               msg='the server ignored the price the cart named')

    def test_04_an_ordinary_line_still_takes_the_list_price(self):
        """The guard on the fix: omitting the price must still mean 'you price it'.
        A cart that names no price must not be able to send 0 and get a free meal."""
        self._sync(self._cart_lines())
        order = self._order()
        self.assertAlmostEqual(order.amount_total, 200.0, places=2,
                               msg='a line with no stated price should cost list')


@tagged('post_install', '-at_install', 'mezze_discount')
class TestCartPayloadCarriesItsPrice(TransactionCase):
    """The client half, guarded structurally rather than in a browser.

    The defect was not logic — it was two names for one thing. A cart line stores
    its price as ``unit_price``; the payload builder read ``price_unit``, a property
    nothing ever assigns, so it silently read ``undefined`` and omitted the price.
    No amount of exercising the cart would fail if the same typo were reintroduced
    under a different name, but reading the source will.

    A structural check is the honest tool here: it names the exact invariant (the
    payload must read the property the cart writes) and it cannot pass vacuously.
    """

    def _source(self):
        with file_open('mezze_bridge/static/src/cashier/order_store.js', 'r') as fh:
            return fh.read()

    def _to_sync_lines(self):
        src = self._source()
        start = src.index('toSyncLines()')
        # to the end of that method: the next method at the same indentation
        end = src.index('\n    }', start)
        return src[start:end]

    def test_10_the_payload_reads_both_places_a_price_can_live(self):
        """A line carries a price two ways and the payload must honour both.

        `price_unit` is a price the cashier TYPED; `unit_price` is one RESTORED
        from the server, which is how a discount and a comp come back. Reading
        either one alone silently drops the other.
        """
        src = self._source()
        self.assertIn('fresh.unit_price = opts.unitPrice', src,
                      'addProduct no longer stores the restored price as unit_price '
                      '— this guard needs updating with it')
        self.assertIn('line.price_unit = n', src,
                      'setPrice no longer stores the typed price as price_unit '
                      '— this guard needs updating with it')
        body = self._to_sync_lines()
        self.assertIn('l.price_unit', body,
                      'toSyncLines ignores a TYPED price: the cashier quotes one '
                      'figure and the server charges another')
        self.assertIn('l.unit_price', body,
                      'toSyncLines ignores a RESTORED price, so an approved discount '
                      'or a comp is re-priced at list on the next sync')

    def test_11_the_typed_price_wins_as_it_does_on_screen(self):
        """The precedence must match `unitPrice()`, the function the cart displays
        from — otherwise the payload and the screen can disagree about the money."""
        src = self._source()
        display = src[src.index('unitPrice(line) {'):]
        display = display[:display.index('\n    }')]
        self.assertLess(display.index('line.price_unit'), display.index('line.unit_price'),
                        'the display no longer prefers the typed price')
        body = self._to_sync_lines()
        self.assertLess(body.index('l.price_unit'), body.index('l.unit_price'),
                        'the payload does not prefer the typed price the way the '
                        'screen does')

    def test_12_the_wire_name_is_still_what_the_server_expects(self):
        """The other half of the rename: whatever the cart calls it internally, the
        payload key must stay `price_unit`, because that is what /orders/sync reads."""
        body = self._to_sync_lines()
        self.assertIn('price_unit:', body,
                      'the payload no longer carries a price_unit key at all')
        self.assertIn('out.price_unit', body,
                      'the emitted payload key changed; /orders/sync reads price_unit')
