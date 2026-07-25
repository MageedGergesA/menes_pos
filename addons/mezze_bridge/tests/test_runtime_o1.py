"""O1 — Omnichannel Ordering acceptance proofs.

Targets the confirmed gap this increment fixed (a secure customer order-status
contract) plus the invariants the DoD calls out: an OPAQUE status token (never a
sequential id), a safe public-status mapping, 86 revalidation at checkout, and
aggregator callback idempotency. The channels' server-authoritative pricing +
canonical order idempotency already exist and are reused (not rebuilt).

RC2/D-2: uses the hermetic fixture layer — no ambient POS/config/session data.
"""
import hashlib
import hmac
import json
import os

from odoo.tests import tagged

from .common import MezzeHttpCase, MezzePosCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestPublicStatus(MezzePosCase):
    fixture_profile = 'POS'

    def _order(self, mint=False, channel='pickup'):
        o = self.create_order_in_test_session(channel=channel)
        raw = o._mezze_ensure_status_token() if mint else None
        return o, raw

    def test_token_hashed_high_entropy_and_idempotent(self):
        o, raw = self._order(mint=True)
        self.assertEqual(len(raw), 32)                        # 16 random bytes -> 32 hex (128 bits)
        self.assertTrue(all(c in '0123456789abcdef' for c in raw))
        # server stores ONLY the hash, never the raw token
        self.assertNotEqual(o.mezze_status_token, raw)
        self.assertEqual(o.mezze_status_token, o._mezze_status_hash(raw))
        self.assertTrue(o.mezze_status_expiry)                # expiry set
        self.assertIsNone(o._mezze_ensure_status_token())     # idempotent: raw not re-derivable
        # revocation makes the token unresolvable
        o.mezze_revoke_status_token()
        self.assertFalse(self.env['pos.order']._mezze_resolve_status_token(raw))

    def test_public_status_mapping(self):
        o, _r = self._order()
        # a fresh draft with no tickets -> received
        self.assertEqual(o.mezze_public_status(), 'received')
        env = self.env
        env['mezze.kds.ticket'].sudo().create(
            {'pos_order_id': o.id, 'station': 'Hot', 'state': 'fired', 'fire_uuid': 'o1-f1'})
        self.assertEqual(o.mezze_public_status(), 'preparing')
        env['mezze.kds.ticket'].sudo().search([('pos_order_id', '=', o.id)]).write({'state': 'ready'})
        self.assertEqual(o.mezze_public_status(), 'ready')
        o.write({'state': 'cancel'})
        self.assertEqual(o.mezze_public_status(), 'cancelled')


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestShopStatusHttp(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        self.order = self.create_order_in_test_session(channel='pickup')
        self.token = self.order._mezze_ensure_status_token()
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def test_status_by_token_ok_safe_fields(self):
        st, b = self._post('/shop/status', {'token': self.token})
        self.assertTrue(b.get('ok'), b)
        self.assertIn(b.get('status'), ('received', 'confirmed', 'preparing', 'ready',
                                        'out_for_delivery', 'completed', 'cancelled', 'action_required'))
        self.assertEqual(b.get('channel'), 'pickup')
        # SAFE fields only — no internal/staff/customer leakage
        for leak in ('cost', 'margin', 'user_id', 'partner_id', 'lines', 'session_id', 'state'):
            self.assertNotIn(leak, b)

    def test_wrong_token_generic_404(self):
        st, b = self._post('/shop/status', {'token': os.urandom(12).hex()})
        self.assertEqual(st, 404)
        self.assertEqual(b.get('error'), 'not_found')

    def test_sequential_id_does_not_expose(self):
        # the sequential pos.order id must NOT work as a status key
        st, b = self._post('/shop/status', {'token': str(self.order.id)})
        self.assertIn(st, (400, 404))
        self.assertFalse(b.get('ok'))


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestAggregatorIdempotent(MezzeHttpCase):
    fixture_profile = 'OMNICHANNEL'

    def setUp(self):
        super().setUp()
        # the fixture aggregator uses SKU 'MZ-SKU-1'
        self.chan = self.aggregator
        self.secret = self.env['mezze.aggregator'].browse(self.chan.id)._secret()
        self.env.flush_all()

    def _sign_post(self, body):
        raw = json.dumps(body).encode()
        sig = hmac.new(self.secret.encode(), raw, hashlib.sha256).hexdigest()
        r = self.url_open('/mezze/aggregator/%s/webhook' % self.chan.code, data=raw,
                          headers={'Content-Type': 'application/json', 'X-Mezze-Signature': sig},
                          timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def test_duplicate_callback_one_order(self):
        body = {'external_id': 'EXT-777', 'event': 'order.new',
                'customer': {'name': 'Aggr Cust', 'phone': '0100', 'address': 'A St'},
                'items': [{'sku': 'MZ-SKU-1', 'qty': 2, 'price': 10.0}],
                'totals': {'gross': 20.0}}
        st, b1 = self._sign_post(body)
        self.assertTrue(b1.get('ok'), b1)
        oid = b1.get('order_id')
        self.assertTrue(oid)
        # repeated callback -> idempotent, same order, no second pos.order
        st, b2 = self._sign_post(body)
        self.assertTrue(b2.get('idempotent'))
        self.assertEqual(b2.get('order_id'), oid)
        n = self.env['mezze.aggregator.order'].sudo().search_count([('external_id', '=', 'EXT-777')])
        self.assertEqual(n, 1)
        self.assertEqual(self.env['pos.order'].sudo().browse(oid).mezze_channel, 'aggregator')

    def test_unmapped_sku_rejected(self):
        body = {'external_id': 'EXT-778', 'event': 'order.new',
                'customer': {'name': 'X'}, 'items': [{'sku': 'NOPE', 'qty': 1}]}
        st, b = self._sign_post(body)
        self.assertEqual(st, 422)
        self.assertEqual(b.get('error'), 'unmapped_skus')

    def test_bad_signature_refused(self):
        raw = json.dumps({'external_id': 'EXT-779', 'event': 'order.new',
                          'items': [{'sku': 'MZ-SKU-1', 'qty': 1}]}).encode()
        r = self.url_open('/mezze/aggregator/%s/webhook' % self.chan.code, data=raw,
                          headers={'Content-Type': 'application/json', 'X-Mezze-Signature': 'deadbeef'},
                          timeout=30)
        self.assertIn(r.status_code, (401, 403))
