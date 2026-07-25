"""End-to-end HTTP proof that a real payment publishes to the outbox.

Tagged ``mezze_runtime``. Drives the REAL ``/orders/pay`` endpoint over HTTP (no
mocks) and asserts that the payment published ``order.paid.v1`` transactionally,
that the dispatcher's consumer delivers it, and that a duplicate pay maps to ONE
logical event.

Note on the harness: HttpCase runs the whole test in ONE transaction (the HTTP
request uses a TestCursor over the test connection and TestCursor *clears*
post-commit hooks), so the automatic post-commit dispatch does not fire here and
the event is read via ``self.env`` (same transaction). The automatic post-commit
firing on a REAL commit is proven separately by
``tests/concurrency/adoption_postcommit.py``.

Proves here:
  * real HTTP pay -> order.paid.v1 published exactly once (transactional)
  * the dispatcher's consumer delivers it (status done + projection written)
  * duplicate pay -> one logical event
"""

import json

from odoo.tests import tagged

from .common import MezzeHttpCase

BASE = '/mezze/api/v1'


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestHttpAdoption(MezzeHttpCase):

    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'adopt-shared-token'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'observe')   # default; token accepted
        ICP.set_param('mezze_bridge.env_profile', 'development')  # shared-admin allowed
        self.cfg = self.pos_config
        self.order = self.create_order_in_test_session()
        self.uuid = self.order.uuid
        self.Event = self.env['mezze.outbox.event']
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open(BASE + path, data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=60)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:300]}

    def _paid_events(self):
        self.env.invalidate_all()
        return self.Event.search([('idempotency_key', '=', 'order.paid:%s' % self.uuid)])

    def test_pay_publishes_and_consumer_delivers(self):
        st, b = self._post('/orders/pay', {'uuid': self.uuid, 'token': self.shared})
        self.assertTrue(b.get('ok'), "pay failed: %s" % b)
        self.assertEqual(b.get('state'), 'paid')

        # published transactionally by the real HTTP payment
        ev = self._paid_events()
        self.assertEqual(len(ev), 1, "order.paid.v1 not published exactly once")
        self.assertEqual(ev.event_type, 'order.paid.v1')

        # the dispatcher's consumer delivers it (post-commit hook is cleared under
        # TestCursor, so drive the dispatcher explicitly here)
        for _ in range(5):
            if self.Event._dispatch_batch(commit=False)['claimed'] == 0:
                break
        ev.invalidate_recordset(['status'])
        self.assertEqual(ev.status, 'done', "consumer did not deliver the event")
        proj = self.env['mezze.audit.log'].sudo().search_count(
            [('event', '=', 'outbox.projected'), ('res_uuid', '=', ev.event_id)])
        self.assertGreaterEqual(proj, 1, "projection consumer did not run")

    def test_duplicate_pay_one_logical_event(self):
        st1, b1 = self._post('/orders/pay', {'uuid': self.uuid, 'token': self.shared})
        self.assertTrue(b1.get('ok'))
        st2, b2 = self._post('/orders/pay', {'uuid': self.uuid, 'token': self.shared})
        self.assertTrue(b2.get('ok'))
        self.assertTrue(b2.get('already'), "second pay should be idempotent 'already'")
        self.assertEqual(len(self._paid_events()), 1,
                         "duplicate payment created more than one logical event")
