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


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestRevisionMovesOnEveryGuardedRoute(MezzeHttpCase):
    """A route that ENFORCES the revision but never MOVES it is a dead guard.

    ``_assert_revision`` was wired into seven routes, but only sync and split/*
    ever called ``mezze_bump_revision``. On comp, tip, partial pay and merge the
    comparison was therefore always current-vs-current: the check changed, the
    version did not, and the next terminal's stale write sailed through the very
    guard that was added to stop it.

    That is the same defect the sync path had — enforcement without movement —
    and it hid in the same way, because a test that only asserts "a stale write
    is refused" passes against it. So each test here asserts the revision MOVED.
    Every one was re-run with its bump removed and observed to fail.
    """
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'revmove-shared-token'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'observe')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session(self.pos_config)
        self.mgr = self.env['mezze.cashier'].create(
            {'name': 'Mona', 'code': 'REVMGR', 'role': 'manager'})
        self.mgr.set_pin('4321')
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token=self.shared)),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _sync(self, uuid, qty=2, **extra):
        return self._post('/orders/sync', dict(
            {'uuid': uuid, 'session_id': self.session.id, 'draft': True,
             'lines': [{'product_id': self.product.id, 'qty': qty}]}, **extra))

    def _rev_of(self, uuid):
        o = self.env['pos.order'].search([('uuid', '=', uuid)], limit=1)
        o.invalidate_recordset()
        return int(o.mezze_revision or 0)

    # -- each guarded route moves the version it guards --------------------

    def test_40_comp_moves_the_revision(self):
        _, first = self._sync('revmove-comp')
        code, res = self._post('/orders/comp', {
            'session_id': self.session.id, 'order_uuid': 'revmove-comp',
            'product_id': self.product.id, 'reason': 'Guest complaint',
            'manager_code': 'REVMGR', 'manager_pin': '4321',
            'expected_revision': first['revision']})
        self.assertEqual(code, 200, res)
        self.assertGreater(self._rev_of('revmove-comp'), first['revision'],
                           "a comp changed what the guest owes without moving the version")
        self.assertIn('revision', res, "the till cannot keep its claim current")

    def test_41_a_comp_elsewhere_makes_my_next_write_stale(self):
        """The end-to-end point of the bump: another terminal comps a line, and
        the write I had queued against the old check is now refused."""
        _, mine = self._sync('revmove-comp2')
        # the OTHER terminal comps, holding the same (current) version
        code, _ = self._post('/orders/comp', {
            'session_id': self.session.id, 'order_uuid': 'revmove-comp2',
            'product_id': self.product.id, 'reason': 'Manager comp',
            'manager_code': 'REVMGR', 'manager_pin': '4321',
            'expected_revision': mine['revision']})
        self.assertEqual(code, 200)
        # my write still claims the version I read before the comp
        code, res = self._sync('revmove-comp2', qty=9,
                               expected_revision=mine['revision'])
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'stale_revision', res)

    def test_42_tip_moves_the_revision(self):
        _, first = self._sync('revmove-tip')
        code, res = self._post('/orders/tip', {
            'uuid': 'revmove-tip', 'amount': 5.0,
            'expected_revision': first['revision']})
        self.assertEqual(code, 200, res)
        self.assertGreater(self._rev_of('revmove-tip'), first['revision'],
                           "a tip changed amount_total without moving the version")
        self.assertIn('revision', res, "the till cannot keep its claim current")

    def test_43_a_partial_payment_moves_the_revision(self):
        """A part-paid check STAYS OPEN, so it can still collide — and
        amount_paid has moved. A fully settled one needs no bump: the FSM closes
        it to further mutation anyway."""
        _, first = self._sync('revmove-pay')
        method = self.pos_config.payment_method_ids[:1]
        code, res = self._post('/orders/pay', {
            'uuid': 'revmove-pay', 'payment_method_id': method.id,
            'amount': 1.0, 'tender_key': 'revmove-pay-t1',
            'expected_revision': first['revision']})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('partial'), res)
        self.assertGreater(self._rev_of('revmove-pay'), first['revision'],
                           "a part-payment left the check open at the old version")

    def test_45_every_guarded_route_reports_the_version_it_wrote(self):
        """A claim the till cannot refresh is a claim it can only make once."""
        import re as _re
        src = open(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'controllers', 'main.py'), encoding='utf-8').read()
        # every call to the guard must have a bump somewhere in the same route
        self.assertGreaterEqual(
            src.count('mezze_bump_revision()'), 6,
            "some guarded route still changes a check without moving its version")
        self.assertGreaterEqual(
            len(_re.findall(r"'revision': int\(", src)), 6,
            "some guarded route does not report the version it wrote")


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestTillDeclaresItsRevision(MezzeHttpCase):
    """The other half of S1-04: the till has to MAKE the claim.

    ``_assert_revision`` treats a missing ``expected`` as "this caller does not
    track revisions" and lets the write through. That is deliberate and right —
    a kiosk, a QR order and an aggregator push never held the check open. But it
    means the guard is only ever as live as the client: with the server enforcing
    on seven routes and the Register declaring on two (both of them Split), every
    other cashier action was still last-writer-wins, and the ONLY way to see a
    banner was to open Split.
    """
    fixture_profile = 'POS'

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _src(self, rel):
        with open(os.path.join(self.ROOT, rel), encoding='utf-8') as f:
            return f.read()

    def test_50_the_till_claims_a_version_on_every_mutation(self):
        src = self._src('static/src/cashier/root.js')
        # the sync call sites: park, send-to-table, assign, charge, persist,
        # order-type and the split entry
        self.assertEqual(
            src.count('"/orders/sync"'), 7,
            'the set of sync call sites moved — re-check that each one claims')
        claims = src.count('expected_revision')
        self.assertGreaterEqual(
            claims, 11,
            'a mutation still writes without saying which version it holds '
            '(found %d claims)' % claims)
        # The claim may be attached to the body a few lines BEFORE the call
        # (that is how /orders/pay builds its request), so look either side of
        # the call site rather than only forward from it.
        for route in ('/orders/pay', '/orders/tip', '/orders/comp', '/tables/merge'):
            i = src.index('"%s"' % route)
            window = src[max(0, i - 900):i + 900]
            self.assertIn('expected_revision', window,
                          '%s writes without a claim' % route)

    def test_51_the_claim_is_bound_to_the_order_it_came_from(self):
        """A revision is only meaningful for the order it was read from.

        The charge path mints a fresh uuid for every counter sale, and mints
        another when it finds the uuid it holds has already been settled. A
        globally-held number carried across that boundary would make the till
        claim a version of an order it has never read — and the server would
        then refuse a write that was in fact perfectly current. Worse than
        making no claim at all.
        """
        src = self._src('static/src/cashier/root.js')
        self.assertIn('_revisionClaimFor(', src,
                      'the claim is not resolved against a uuid')
        self.assertIn('orderRevisionUuid', src,
                      'nothing records WHICH order the held version belongs to')
        # the guard inside the helper: same uuid or no claim
        self.assertIn('this.state.orderRevisionUuid === uuid', src,
                      'the helper does not check the uuid matches')
        # and the spent-uuid retry must drop it
        i = src.index('if (settled(res)) {')
        self.assertIn('orderRevision = null', src[i:i + 500],
                      'a re-minted uuid inherits the old order\'s version')

    def test_52_a_cleared_cart_drops_the_claim(self):
        src = self._src('static/src/cashier/root.js')
        n_null = src.count('this.state.orderUuid = null;')
        n_drop = src.count('this.state.orderRevisionUuid = null;')
        self.assertGreaterEqual(
            n_drop, n_null,
            'a cart was cleared without dropping the version claim with it')


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestMergeMovesTheDestination(MezzeHttpCase):
    """Merge needs real tables, so it needs the RESTAURANT fixture.

    This test first lived in the POS-profile class above, where `floor_ids` is
    empty — so it SKIPPED, and a skip reads as a pass. It survived its own
    negative control that way: the bump was removed and the run still came back
    "0 failed". There is no defensive skip here on purpose. If the fixture stops
    providing tables this must fail and be looked at, not quietly stop testing.
    """
    fixture_profile = 'RESTAURANT'

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'revmerge-shared-token'
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

    def _sync(self, uuid, **extra):
        return self._post('/orders/sync', dict(
            {'uuid': uuid, 'session_id': self.session.id, 'draft': True,
             'lines': [{'product_id': self.product.id, 'qty': 2}]}, **extra))

    def _rev_of(self, uuid):
        o = self.env['pos.order'].search([('uuid', '=', uuid)], limit=1)
        o.invalidate_recordset()
        return int(o.mezze_revision or 0)

    def test_44_a_merge_moves_the_destination(self):
        """The destination is the survivor and it just grew by a whole check.
        Bumping the source would prove nothing — the merge unlinks it."""
        self.assertGreaterEqual(len(self.tables), 2,
                                'the RESTAURANT fixture must provide two tables')
        src_t, dst_t = self.tables[0], self.tables[1]
        self._sync('revmove-merge-src', table_id=src_t.id)
        _, dst = self._sync('revmove-merge-dst', table_id=dst_t.id)
        before = dst['revision']
        code, res = self._post('/tables/merge', {
            'session_id': self.session.id,
            'from_table_id': src_t.id, 'to_table_id': dst_t.id})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('merged'),
                        'this must exercise the MERGE branch, not the transfer one')
        self.assertGreater(self._rev_of('revmove-merge-dst'), before,
                           'the destination absorbed a check without moving its version')
