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
import os

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


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestConflictBanner(MezzeHttpCase):
    """The Register half of the collision (design v3, screen 01 POS).

    The guard can only be reached if the client HOLDS a revision, so the sync
    response has to carry one; and the banner can only name a difference if the
    refusal carries the other side's lines. Both are contracts, not conveniences.
    """
    fixture_profile = 'POS'

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'conflict-shared-token'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'observe')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session(self.pos_config)
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token=self.shared)),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _src(self, rel):
        with open(os.path.join(self.ROOT, rel), encoding='utf-8') as f:
            return f.read()

    def test_30_sync_returns_the_revision_it_wrote(self):
        """Without this the client can never send expected_revision, and the
        whole guard stays dormant however well it is written."""
        code, res = self._post('/orders/sync', {
            'uuid': 'conflict-rev-1', 'session_id': self.session.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': 1}]})
        self.assertEqual(code, 200, res)
        self.assertIn('revision', res, "the client has no version to hold")
        self.assertIsInstance(res['revision'], int)

    def test_31_a_second_sync_reports_the_moved_revision(self):
        _, first = self._post('/orders/sync', {
            'uuid': 'conflict-rev-2', 'session_id': self.session.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': 1}]})
        _, second = self._post('/orders/sync', {
            'uuid': 'conflict-rev-2', 'session_id': self.session.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': 2}],
            'expected_revision': first['revision']})
        self.assertGreater(second['revision'], first['revision'],
                           "the revision did not move, so nothing can ever be stale")

    def test_32_the_client_sends_and_holds_the_revision(self):
        src = self._src('static/src/cashier/root.js')
        self.assertIn('expected_revision', src, "the till never sends its version")
        self.assertIn('orderRevision', src, "the till never holds a version")

    def test_33_charge_and_fast_pay_are_both_blocked(self):
        """"Charge is disabled until resolved" — and fast pay IS charging.
        Blocking only the Charge button left a second door onto a stale check."""
        xml = self._src('static/src/cashier/components/cart.xml')
        self.assertEqual(xml.count('props.conflicted'), 2,
                         "both the Charge button and the fast-pay row must block")
        js = self._src('static/src/cashier/components/cart.js')
        self.assertIn('Resolve conflict to charge', js,
                      "a disabled button with its usual label reads as broken")

    def test_34_the_banner_offers_the_designs_three_ways_out(self):
        xml = self._src('static/src/cashier/root.xml')
        for label in ('Keep mine', 'Keep theirs', 'Review'):
            self.assertIn(label, xml, "the banner is missing %r" % label)
        self.assertIn('role="alert"', xml, "a conflict must be announced")

    def test_35_the_resolutions_are_translated(self):
        po = self._src('i18n/ar.po')
        for en in ('Keep mine', 'Keep theirs', 'Review',
                   'Resolve conflict to charge'):
            self.assertIn('msgid "%s"' % en, po, "%r has no Arabic" % en)
