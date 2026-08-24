# -*- coding: utf-8 -*-
"""Accepting a delivery platform's own order shape.

The inbound webhook was already hardened — per-channel HMAC, replay-safe on the
vendor's order id, every SKU mapped before anything is created, an unmapped item
rejecting the whole order rather than half-selling it. What it could not do was
accept a payload it had not designed: it read ``external_id``, ``items[].sku`` and
``customer{}``, which is Mezze's own shape and nobody else's.

**Why this is a mapping table and not a Talabat adapter.** Talabat's and Jahez's
order APIs are partner-gated — you get the specification after you sign, and it is
not public. A module full of field names nobody here has seen would look finished,
pass its own tests, and be wrong in a way that only surfaces on the first live
order. So the vendor-specific part is DATA on the channel, and the hard shared parts
stay in one tested place.

What the mocked vendors below prove is exactly that claim: two payloads with nothing
structurally in common, ingested by one unchanged codebase. They are explicitly
*fictional shapes* — no real platform's field names are asserted anywhere, because
none are known here.
"""
import json

from odoo.tests import TransactionCase, tagged

from .common import MezzeHttpCase
from ..domain import aggregator_mapping as M


@tagged('post_install', '-at_install', 'mezze_aggregator')
class TestMappingPure(TransactionCase):
    """The translation, with no ORM and no HTTP."""

    VENDOR = {
        'order': {'reference': 'T-4471',
                  'basket': [{'menu_item_id': 'BURG', 'count': 2,
                              'unit_price': {'amount': 45.5}},
                             {'menu_item_id': 'COLA', 'count': 1,
                              'unit_price': {'amount': 8}}]},
        'client': {'full_name': 'Omar', 'contacts': [{'value': '+20100'}]},
    }
    MAP = {'external_id': 'order.reference', 'items': 'order.basket',
           'item_sku': 'menu_item_id', 'item_qty': 'count',
           'item_price': 'unit_price.amount',
           'customer_name': 'client.full_name',
           'customer_phone': 'client.contacts.0.value'}

    def test_01_a_nested_vendor_shape_becomes_mezzes(self):
        out = M.translate(self.VENDOR, self.MAP)
        self.assertEqual(out['external_id'], 'T-4471')
        self.assertEqual([i['sku'] for i in out['items']], ['BURG', 'COLA'])
        self.assertEqual(out['items'][0]['qty'], 2.0)
        self.assertEqual(out['items'][0]['price'], 45.5)
        self.assertEqual(out['customer']['phone'], '+20100')

    def test_02_mezzes_own_shape_still_works_with_no_mapping(self):
        # Every existing integration must be untouched: the native format is just
        # the default row in the table, not a special case in the code.
        native = {'external_id': 'A1',
                  'items': [{'sku': 'X', 'qty': 2, 'price': 10}],
                  'customer': {'name': 'Sara', 'phone': '1'}}
        out = M.translate(native)
        self.assertEqual(out['external_id'], 'A1')
        self.assertEqual(out['items'][0]['sku'], 'X')

    def test_03_a_list_index_is_reachable(self):
        self.assertEqual(
            M.dig({'c': {'contacts': [{'v': 'a'}, {'v': 'b'}]}}, 'c.contacts.1.v'), 'b')

    def test_04_a_missing_path_is_not_an_exception(self):
        # An omitted OPTIONAL field is normal; the required ones are named below.
        self.assertIsNone(M.dig({'a': 1}, 'a.b.c'))
        self.assertIsNone(M.dig({}, 'nope'))

    # ── refusals: never a half-translated order ──────────────────────────
    def test_10_no_order_id_is_refused(self):
        with self.assertRaises(M.MappingError) as c:
            M.translate({'order': {}}, self.MAP)
        self.assertEqual(c.exception.reason, 'missing_external_id')

    def test_11_no_items_is_refused(self):
        with self.assertRaises(M.MappingError) as c:
            M.translate({'order': {'reference': 'T-1', 'basket': []}}, self.MAP)
        self.assertEqual(c.exception.reason, 'no_items')

    def test_12_an_item_with_no_sku_is_refused(self):
        # Half-selling an order is the failure that puts food out of the door
        # against a bill that does not match what the guest paid.
        bad = {'order': {'reference': 'T-2', 'basket': [{'count': 1}]}}
        with self.assertRaises(M.MappingError) as c:
            M.translate(bad, self.MAP)
        self.assertEqual(c.exception.reason, 'missing_sku')

    def test_13_a_zero_or_negative_quantity_is_refused(self):
        for qty in (0, -1):
            bad = {'order': {'reference': 'T-3',
                             'basket': [{'menu_item_id': 'X', 'count': qty}]}}
            with self.assertRaises(M.MappingError) as c:
                M.translate(bad, self.MAP)
            self.assertEqual(c.exception.reason, 'bad_quantity')

    def test_14_a_missing_price_is_allowed(self):
        # The branch prices it. A platform that does not send prices is normal.
        out = M.translate(
            {'order': {'reference': 'T-5',
                       'basket': [{'menu_item_id': 'X', 'count': 1}]}}, self.MAP)
        self.assertNotIn('price', out['items'][0])

    # ── the mapping itself is validated when SAVED ───────────────────────
    def test_20_a_mapping_that_could_never_work_is_named(self):
        self.assertTrue(M.validate_mapping({'external_id': ''}))
        self.assertTrue(M.validate_mapping({'typo_key': 'x'}))
        self.assertEqual(M.validate_mapping({'items': 'order.basket'}), [])
        self.assertEqual(M.validate_mapping(None), [])


@tagged('post_install', '-at_install', 'mezze_aggregator')
class TestVendorWebhook(MezzeHttpCase):
    """Two fictional platforms, one unchanged codebase."""
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.burger = env['product.product'].sudo().create({
            'name': 'AG Burger', 'available_in_pos': True, 'list_price': 45.0,
            'type': 'consu'})
        cls.burger.write({'taxes_id': [(5, 0, 0)]})
        cls.channel = env['mezze.aggregator'].sudo().create({
            'code': 'vendorx', 'name': 'Vendor X', 'config_id': cls.pos_config.id,
            'secret': 'sh-sh', 'auto_accept': True,
            'payload_mapping': json.dumps({
                'external_id': 'order.reference', 'items': 'order.basket',
                'item_sku': 'menu_item_id', 'item_qty': 'count',
                'item_price': 'unit_price.amount',
                'customer_name': 'client.full_name',
                'customer_phone': 'client.contacts.0.value'}),
        })
        env['mezze.aggregator.product.map'].sudo().create({
            'aggregator_id': cls.channel.id, 'external_sku': 'BURG',
            'product_id': cls.burger.id})
        env.flush_all()

    def _post(self, body):
        import hashlib
        import hmac
        raw = json.dumps(body).encode()
        sig = hmac.new(b'sh-sh', raw, hashlib.sha256).hexdigest()
        return self.url_open(
            '/mezze/aggregator/vendorx/webhook', data=raw,
            headers={'Content-Type': 'application/json',
                     'X-Mezze-Signature': sig})

    def test_30_a_vendor_shaped_order_is_ingested(self):
        r = self._post({'order': {'reference': 'VX-1',
                                  'basket': [{'menu_item_id': 'BURG', 'count': 2,
                                              'unit_price': {'amount': 45}}]},
                        'client': {'full_name': 'Omar',
                                   'contacts': [{'value': '+20100'}]}})
        body = r.json()
        self.assertTrue(body.get('ok'), body)
        agg = self.env['mezze.aggregator.order'].sudo().search(
            [('external_id', '=', 'VX-1')], limit=1)
        self.assertTrue(agg, 'the vendor order never landed')
        self.assertEqual(agg.customer_name, 'Omar')

    def test_31_a_payload_the_mapping_cannot_read_is_refused(self):
        r = self._post({'order': {'basket': []}, 'client': {}})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json().get('error'), 'unreadable_payload')

    def test_32_it_is_still_idempotent_on_the_vendors_id(self):
        for _ in range(2):
            self._post({'order': {'reference': 'VX-DUP',
                                  'basket': [{'menu_item_id': 'BURG', 'count': 1}]},
                        'client': {'full_name': 'Sara'}})
        self.assertEqual(
            self.env['mezze.aggregator.order'].sudo().search_count(
                [('external_id', '=', 'VX-DUP')]), 1,
            'a replayed vendor order created a second sale')

    def test_33_an_unmapped_sku_still_rejects_the_whole_order(self):
        # The rule that keeps a half-order off the pass, now reached through a
        # vendor's own shape.
        self._post({'order': {'reference': 'VX-BAD',
                              'basket': [{'menu_item_id': 'NOPE', 'count': 1}]},
                    'client': {'full_name': 'Sara'}})
        agg = self.env['mezze.aggregator.order'].sudo().search(
            [('external_id', '=', 'VX-BAD')], limit=1)
        self.assertTrue(agg)
        self.assertEqual(agg.state, 'rejected')
        self.assertEqual(agg.reject_reason, 'unmapped_skus')

    def test_34_a_bad_mapping_is_refused_when_the_channel_is_saved(self):
        # Not when the first live order arrives — that one is somebody's dinner.
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.channel.sudo().write({'payload_mapping': '{"nonsense_key": "x"}'})
        with self.assertRaises(ValidationError):
            self.channel.sudo().write({'payload_mapping': 'not json at all'})
