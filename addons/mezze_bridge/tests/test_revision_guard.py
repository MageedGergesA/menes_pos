"""Optimistic concurrency on a check — every mutation, not just split/commit.

Two terminals may hold one table open. ``pos.order.mezze_revision`` and its
one-place bump already existed, and ``split/commit`` had checked it since it was
written — but every OTHER way of changing a check accepted a stale write in
silence. A cashier's quantities could be replaced by a view of the bill taken
minutes earlier, with nothing said.

The design (`Mezze POS v3.dc.html`, Register) draws that collision as a banner
naming the difference — "Kofta quantity differs (yours 4 · theirs 3)" — with
Charge disabled until it is resolved. A banner needs facts, so the refusal
returns the CURRENT lines, not just a version number: the client knows what it
had, the server knows what is there now.

`expected_revision=None` deliberately passes. A kiosk, a QR order or an
aggregator push never held the check open and is not lying about a version;
enforcing on them would break every client that does not track one.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestRevisionGuard(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'revision-shared-token'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'observe')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session(self.pos_config)
        self.order = self.create_order_in_test_session()
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token=self.shared)),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    @property
    def rev(self):
        self.order.invalidate_recordset()
        return int(self.order.mezze_revision or 0)

    # -- the helper's own contract ----------------------------------------
    def test_01_a_current_revision_is_accepted(self):
        code, res = self._post('/orders/tip', {
            'order_id': self.order.id, 'amount': 5.0, 'expected_revision': self.rev})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)

    def test_02_a_stale_revision_is_refused_with_409(self):
        stale = self.rev - 1
        code, res = self._post('/orders/tip', {
            'order_id': self.order.id, 'amount': 5.0, 'expected_revision': stale})
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'stale_revision')

    def test_03_the_refusal_carries_what_the_banner_needs(self):
        """Only a revision number lets a client say "something changed" and no
        more. The design names the differing line, so the lines come back."""
        code, res = self._post('/orders/tip', {
            'order_id': self.order.id, 'amount': 5.0, 'expected_revision': self.rev - 1})
        self.assertEqual(code, 409, res)
        self.assertIn('lines', res, "the client cannot show a difference")
        self.assertTrue(res['lines'], "the current composition is empty")
        first = res['lines'][0]
        for key in ('id', 'product_id', 'name', 'qty', 'price_unit'):
            self.assertIn(key, first, "a line is missing %r" % key)
        self.assertEqual(res.get('revision'), self.rev, "the client cannot catch up")
        self.assertEqual(res.get('expected'), self.rev - 1, "the refusal is unexplained")

    def test_04_omitting_it_is_allowed(self):
        """A client that never held the check open is not lying about a version."""
        code, res = self._post('/orders/tip', {'order_id': self.order.id, 'amount': 3.0})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)

    def test_05_a_nonsense_revision_is_a_bad_request(self):
        code, res = self._post('/orders/tip', {
            'order_id': self.order.id, 'amount': 5.0, 'expected_revision': 'soon'})
        self.assertEqual(code, 400, res)
        self.assertEqual(res.get('error'), 'bad_revision')

    # -- the money path ----------------------------------------------------
    def test_06_a_stale_check_cannot_be_charged(self):
        """The design: "Charge is disabled until resolved." Paying a stale check
        settles a total the guest was never shown."""
        pm = self.cash_payment_method
        code, res = self._post('/orders/pay', {
            'order_id': self.order.id, 'payment_method_id': pm.id,
            'amount': self.order.amount_total, 'expected_revision': self.rev - 1})
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'stale_revision')
        self.order.invalidate_recordset()
        self.assertEqual(self.order.state, 'draft', "a stale check was settled")
        self.assertFalse(self.order.payment_ids, "money moved on a stale check")

    # -- the composition path ---------------------------------------------
    def test_07_a_stale_sync_cannot_replace_the_lines(self):
        before = len(self.order.lines)
        code, res = self._post('/orders/sync', {
            'uuid': self.order.uuid, 'session_id': self.session.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': 99}],
            'expected_revision': self.rev - 1})
        self.assertEqual(code, 409, res)
        self.order.invalidate_recordset()
        self.assertEqual(len(self.order.lines), before,
                         "a stale sync rewrote somebody else's quantities")

    def test_08_the_revision_moves_when_the_check_does(self):
        """A guard on a number that never changes would refuse nothing."""
        start = self.rev
        self.order.mezze_bump_revision()
        self.assertEqual(self.rev, start + 1)
