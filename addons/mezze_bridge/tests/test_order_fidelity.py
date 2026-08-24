"""Wave 1 — the three defects that corrupted live orders.

None of these was a missing feature. Each was a feature Mezze already had, quietly
losing or duplicating the cashier's work:

1. **Fire doubled the order.** The standalone cashier persists the whole cart, then
   sent that same whole cart to /orders/fire — whose contract is APPEND. The first
   Fire wrote every line twice and doubled ``amount_total``.
2. **Recall stripped configuration.** ``/orders/get`` returned product, qty, price
   and discount only. Resuming a table rebuilt bare lines, and because /orders/sync
   replaces lines wholesale, the next save destroyed the modifiers, the note and the
   combo structure on the server.
3. **Line notes were never written.** Accepted by the route, shown in the panel, sent
   on every sync — and absent from ``line_vals``. Only /orders/comp ever wrote the
   field.

Each test below fails on the unfixed code; the guards were disabled and re-run to
prove it, not assumed.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_fidelity')
class TestOrderFidelity(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'fid-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='fid-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _sync(self, uuid, lines, **kw):
        return self._post('/orders/sync', dict({
            'uuid': uuid, 'session_id': self.session.id,
            'lines': lines, 'draft': True}, **kw))

    def _order(self, uuid):
        return self.env['pos.order'].search([('uuid', '=', uuid)], limit=1)

    # ── 1. Fire must not double the order ────────────────────────────────────
    def test_01_fire_after_sync_does_not_double_the_order(self):
        uuid = 'fid-fire-1'
        line = {'product_id': self.product.id, 'qty': 2}
        code, _res = self._sync(uuid, [line])
        self.assertEqual(code, 200)
        order = self._order(uuid)
        lines_before = len(order.lines)
        total_before = order.amount_total
        self.assertEqual(lines_before, 1)

        code, res = self._post('/orders/fire', {
            'uuid': uuid, 'session_id': self.session.id,
            'lines': [line], 'reconcile': True})
        self.assertEqual(code, 200, res)
        order.invalidate_recordset()
        self.assertEqual(len(order.lines), lines_before,
                         'Fire added the cart to an order that already had it')
        self.assertAlmostEqual(order.amount_total, total_before, places=2,
                               msg='Fire doubled the order total')

    def test_02_fire_still_reaches_the_kitchen(self):
        # Not doubling is worthless if nothing is cooked.
        uuid = 'fid-fire-2'
        self._sync(uuid, [{'product_id': self.product.id, 'qty': 1}])
        code, res = self._post('/orders/fire', {
            'uuid': uuid, 'session_id': self.session.id,
            'lines': [{'product_id': self.product.id, 'qty': 1}], 'reconcile': True})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('tickets'), 'no KDS ticket was created')
        self.assertTrue(res.get('fired_now'), 'nothing was reported as fired')

    def test_03_adding_an_item_then_refiring_fires_only_the_new_item(self):
        uuid = 'fid-fire-3'
        self._sync(uuid, [{'product_id': self.product.id, 'qty': 1}])
        self._post('/orders/fire', {'uuid': uuid, 'session_id': self.session.id,
                                    'lines': [{'product_id': self.product.id, 'qty': 1}],
                                    'reconcile': True})
        # cashier adds one more of the same product and fires again
        self._sync(uuid, [{'product_id': self.product.id, 'qty': 2}])
        code, res = self._post('/orders/fire', {
            'uuid': uuid, 'session_id': self.session.id,
            'lines': [{'product_id': self.product.id, 'qty': 2}], 'reconcile': True})
        self.assertEqual(code, 200, res)
        fired = sum(f['qty'] for f in res.get('fired_now', []))
        self.assertAlmostEqual(fired, 1.0, places=2,
                               msg='re-fire sent the whole order to the kitchen again')

    def test_04_refiring_unchanged_fires_nothing(self):
        uuid = 'fid-fire-4'
        self._sync(uuid, [{'product_id': self.product.id, 'qty': 1}])
        body = {'uuid': uuid, 'session_id': self.session.id,
                'lines': [{'product_id': self.product.id, 'qty': 1}], 'reconcile': True}
        self._post('/orders/fire', body)
        code, res = self._post('/orders/fire', dict(body, fire_uuid='fid-fire-4:second'))
        self.assertEqual(code, 200, res)
        self.assertEqual(res.get('fired_now'), [],
                         'an unchanged order was sent to the kitchen twice')

    def test_05_the_waiter_append_path_is_untouched(self):
        # /orders/fire without reconcile must still APPEND — two waiters firing to
        # one table both add their items. Regressing this to "reconcile" would make
        # the second waiter's food vanish.
        uuid = 'fid-fire-5'
        code, _r = self._post('/orders/fire', {
            'uuid': uuid, 'session_id': self.session.id,
            'lines': [{'product_id': self.product.id, 'qty': 1}]})
        self.assertEqual(code, 200)
        order = self._order(uuid)
        first = len(order.lines)
        code, _r = self._post('/orders/fire', {
            'uuid': uuid, 'session_id': self.session.id,
            'lines': [{'product_id': self.product.id, 'qty': 1}],
            'fire_uuid': 'fid-fire-5:b'})
        self.assertEqual(code, 200)
        order.invalidate_recordset()
        self.assertGreater(len(order.lines), first,
                           'the append contract regressed — a waiter lost their items')

    # ── 2. Recall must be lossless ───────────────────────────────────────────
    def test_10_orders_get_returns_what_a_line_needs_to_be_rebuilt(self):
        uuid = 'fid-get-1'
        self._sync(uuid, [{'product_id': self.product.id, 'qty': 1, 'note': 'no ice'}])
        code, res = self._post('/orders/get', {'uuid': uuid})
        self.assertEqual(code, 200, res)
        line = res['lines'][0]
        for key in ('id', 'attribute_value_ids', 'note', 'combo_parent_id', 'full_name'):
            self.assertIn(key, line, 'a resumed line cannot be rebuilt without %r' % key)

    def test_11_a_note_survives_a_round_trip(self):
        uuid = 'fid-get-2'
        self._sync(uuid, [{'product_id': self.product.id, 'qty': 1, 'note': 'allergy - no nuts'}])
        _c, res = self._post('/orders/get', {'uuid': uuid})
        self.assertEqual(res['lines'][0]['note'], 'allergy - no nuts',
                         'the cashier instruction did not survive being read back')

    # ── 3. Notes must be durable ─────────────────────────────────────────────
    def test_20_a_line_note_is_actually_written(self):
        uuid = 'fid-note-1'
        self._sync(uuid, [{'product_id': self.product.id, 'qty': 1, 'note': 'well done'}])
        order = self._order(uuid)
        self.assertTrue(order.exists())
        self.assertEqual(order.lines[0].customer_note, 'well done',
                         'the note was accepted, displayed, transmitted — and dropped')

    def test_21_a_note_survives_a_resync(self):
        # /orders/sync replaces lines wholesale, so this is where the note used to die.
        uuid = 'fid-note-2'
        self._sync(uuid, [{'product_id': self.product.id, 'qty': 1, 'note': 'extra hot'}])
        self._sync(uuid, [{'product_id': self.product.id, 'qty': 2, 'note': 'extra hot'}])
        order = self._order(uuid)
        self.assertEqual(order.lines[0].customer_note, 'extra hot')
        self.assertAlmostEqual(order.lines[0].qty, 2.0, places=2)

    def test_22_a_note_with_no_text_writes_nothing(self):
        uuid = 'fid-note-3'
        self._sync(uuid, [{'product_id': self.product.id, 'qty': 1}])
        order = self._order(uuid)
        self.assertFalse(order.lines[0].customer_note or '')

    def test_23_the_kitchen_ticket_carries_modifiers_AND_the_note(self):
        # _line_note returned one or the other. A configured line reached the kitchen
        # with its modifiers and without the cashier's instruction, and nothing said so.
        uuid = 'fid-note-4'
        self._sync(uuid, [{'product_id': self.product.id, 'qty': 1, 'note': 'no straw'}])
        code, res = self._post('/orders/fire', {
            'uuid': uuid, 'session_id': self.session.id,
            'lines': [{'product_id': self.product.id, 'qty': 1}], 'reconcile': True})
        self.assertEqual(code, 200, res)
        notes = [f.get('note') or '' for f in res.get('fired_now', [])]
        self.assertTrue(any('no straw' in n for n in notes),
                        'the kitchen was not told the cashier instruction: %r' % notes)
