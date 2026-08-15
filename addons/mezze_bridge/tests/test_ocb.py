"""DT-UX6 — the customer's order confirmation board.

The OCB exists to catch a wrong item before it is cooked, so the tests are about two
things and in this order: the customer must never see somebody else's order, and the
order they do see must be the one the operator is typing.

Everything here goes through the real endpoints. The customer read is a public route
whose only input is an opaque credential — there is deliberately no lane, no id and
no order reference to substitute — and several tests exist purely to keep it that way.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime', 'mezze_ocb')
class TestOcb(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'ocb-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()
        self.products = self.env['product.product'].search(
            [('available_in_pos', '=', True)], limit=3)
        self.assertTrue(self.products, 'the fixture needs sellable products')
        Display = self.env['mezze.ocb.display']
        Display.sudo().search([]).unlink()
        self.d1, self.tok1 = Display._provision(self.pos_config, lane=1)
        self.d2, self.tok2 = Display._provision(self.pos_config, lane=2)
        self.env.flush_all()

    # ---- helpers ------------------------------------------------------------
    def _post(self, path, body, token='ocb-tok'):
        payload = dict(body)
        if token:
            payload['token'] = token
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(payload),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:                                        # noqa: BLE001
            return r.status_code, {'_raw': r.text[:200]}

    def _state(self, display_token):
        """The customer read — the display credential is the ONLY input."""
        r = self.url_open('/mezze/api/v1/ocb/state',
                          data=json.dumps({'token': display_token}),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:                                        # noqa: BLE001
            return r.status_code, {'_raw': r.text[:200]}

    def _publish(self, lane, lines, action=None):
        body = {'config_id': self.pos_config.id, 'lane': lane,
                'lines': [{'product_id': p.id, 'qty': q} for p, q in lines]}
        if action:
            body['action'] = action
        return self._post('/ocb/publish', body)

    # ==================================================================
    # security — the credential is the whole boundary
    # ==================================================================
    def test_01_an_unknown_token_is_refused(self):
        code, res = self._state('x' * 40)
        self.assertEqual(code, 404, res)
        self.assertEqual(res.get('error'), 'display_unavailable')

    def test_02_a_short_or_empty_token_is_refused(self):
        for bad in ('', 'abc', None):
            code, _res = self._state(bad)
            self.assertEqual(code, 404, 'token %r must not resolve' % (bad,))

    def test_03_a_disabled_display_stops_answering(self):
        self.d1.sudo().write({'active': False})
        self.env.flush_all()
        code, res = self._state(self.tok1)
        self.assertEqual(code, 404, res)
        self.assertEqual(res.get('error'), 'display_unavailable',
                         'and says the same thing an unknown token gets, so a prober '
                         'cannot tell which guesses were closer')

    def test_04_a_revoked_terminal_stops_answering(self):
        self.d1.terminal_id.sudo().write({'active': False})
        self.env.flush_all()
        self.assertEqual(self._state(self.tok1)[0], 404)

    def test_05_the_read_endpoint_accepts_no_lane_or_id_to_substitute(self):
        # THE isolation gate. A Lane 1 credential cannot express a request for Lane 2,
        # because there is nothing in the contract to override.
        self._publish(1, [(self.products[0], 1)])
        self._publish(2, [(self.products[1], 5)])
        self.env.flush_all()
        r = self.url_open('/mezze/api/v1/ocb/state',
                          data=json.dumps({'token': self.tok1, 'lane': 2,
                                           'display_id': self.d2.id,
                                           'config_id': self.pos_config.id,
                                           'order_id': 1}),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        res = r.json()
        self.assertEqual(res['display']['lane'], 1,
                         'injected parameters cannot move a display to another lane')
        names = [l['name'] for l in res['order']['lines']]
        self.assertIn(self.products[0].name, names)
        self.assertNotIn(self.products[1].name, names, 'lane 2 content leaked')

    def test_06_the_page_is_not_cached(self):
        r = self.url_open('/mezze/ocb/%s' % self.tok1, timeout=30)
        self.assertEqual(r.status_code, 200)
        cache = r.headers.get('Cache-Control', '')
        self.assertIn('no-store', cache)
        self.assertIn('private', cache)

    def test_07_an_invalid_page_token_is_a_404_not_a_hint(self):
        r = self.url_open('/mezze/ocb/%s' % ('z' * 40), timeout=30)
        self.assertEqual(r.status_code, 404)

    def test_08_no_staff_or_internal_data_reaches_the_customer(self):
        self._publish(1, [(self.products[0], 2)])
        self.env.flush_all()
        _code, res = self._state(self.tok1)
        blob = json.dumps(res).lower()
        for leak in ('token', 'terminal', 'cashier', 'user_id', 'employee',
                     'product_id', 'config_id', 'session_id', 'cost', 'margin',
                     'tax_id', 'station', 'kds', 'vehicle', 'uuid', 'fingerprint'):
            self.assertNotIn(leak, blob, 'customer payload leaks %r: %s' % (leak, blob))
        # and the shape is the small contract, not a serialized pos.order
        self.assertEqual(sorted(res), ['display', 'ok', 'order', 'revision', 'state'])
        self.assertEqual(sorted(res['display']), ['lane', 'lang', 'name'])

    def test_09_the_page_never_stores_the_order_in_the_browser(self):
        path = __file__.rsplit('/tests/', 1)[0] + '/static/ocb.html'
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        self.assertNotIn('localStorage', src)
        self.assertNotIn('sessionStorage', src)

    # ==================================================================
    # the live order
    # ==================================================================
    def test_10_idle_until_something_is_ordered(self):
        code, res = self._state(self.tok1)
        self.assertEqual(code, 200, res)
        self.assertEqual(res['state'], 'idle')
        self.assertIsNone(res['order'])
        self.assertEqual(res['display']['lane'], 1)

    def test_11_the_first_item_moves_the_display_to_ordering(self):
        self._publish(1, [(self.products[0], 1)])
        _code, res = self._state(self.tok1)
        self.assertEqual(res['state'], 'ordering')
        self.assertEqual(len(res['order']['lines']), 1)
        self.assertEqual(res['order']['lines'][0]['name'], self.products[0].name)
        self.assertEqual(res['order']['lines'][0]['qty'], 1)

    def test_12_a_quantity_change_is_reflected(self):
        self._publish(1, [(self.products[0], 1)])
        first = self._state(self.tok1)[1]['order']['money']['total']
        self._publish(1, [(self.products[0], 2)])
        res = self._state(self.tok1)[1]
        self.assertEqual(res['order']['lines'][0]['qty'], 2)
        self.assertGreater(res['order']['money']['total'], first,
                           'two of a thing costs more than one of it')

    def test_13_removing_a_line_removes_it_from_the_customer_screen(self):
        self._publish(1, [(self.products[0], 1), (self.products[1], 1)])
        self.assertEqual(len(self._state(self.tok1)[1]['order']['lines']), 2)
        self._publish(1, [(self.products[0], 1)])
        res = self._state(self.tok1)[1]
        self.assertEqual(len(res['order']['lines']), 1)
        self.assertNotIn(self.products[1].name,
                         [l['name'] for l in res['order']['lines']],
                         'a removed line must not linger')

    def test_14_modifiers_are_shown_under_their_line_and_replaced_not_appended(self):
        # The drive-thru order taker collects no modifiers today (see the data-flow
        # audit), but the contract carries them and the display renders them, so the
        # capability is certified rather than assumed.
        self._post('/ocb/publish', {
            'config_id': self.pos_config.id, 'lane': 1,
            'lines': [{'product_id': self.products[0].id, 'qty': 1,
                       'modifiers': ['No onion', 'Extra cheese']}]})
        res = self._state(self.tok1)[1]
        self.assertEqual(res['order']['lines'][0]['modifiers'],
                         ['No onion', 'Extra cheese'])
        self._post('/ocb/publish', {
            'config_id': self.pos_config.id, 'lane': 1,
            'lines': [{'product_id': self.products[0].id, 'qty': 1,
                       'modifiers': ['Extra onion']}]})
        res = self._state(self.tok1)[1]
        self.assertEqual(res['order']['lines'][0]['modifiers'], ['Extra onion'],
                         'the old modifier is gone, not duplicated')

    def test_15_money_comes_from_the_server_and_adds_up(self):
        self._publish(1, [(self.products[0], 2)])
        money = self._state(self.tok1)[1]['order']['money']
        for key in ('subtotal', 'tax', 'total'):
            self.assertIn(key, money)
        self.assertAlmostEqual(money['total'], money['subtotal'] + money['tax'], 2,
                               'the total is the parts, not an independent number')
        lines = self._state(self.tok1)[1]['order']['lines']
        self.assertAlmostEqual(sum(l['line_total'] for l in lines), money['total'], 2,
                               'and the lines add up to it')

    def test_16_currency_is_the_branch_currency(self):
        self._publish(1, [(self.products[0], 1)])
        cur = self._state(self.tok1)[1]['order']['currency']
        self.assertEqual(cur['name'], self.pos_config.company_id.currency_id.name)

    def test_17_clearing_returns_the_display_to_idle(self):
        self._publish(1, [(self.products[0], 1)])
        self._publish(1, [], action='clear')
        res = self._state(self.tok1)[1]
        self.assertEqual(res['state'], 'idle')
        self.assertIsNone(res['order'],
                          "the previous customer's order is gone, not merely hidden")

    def test_18_an_emptied_cart_is_the_same_as_a_cleared_one(self):
        self._publish(1, [(self.products[0], 1)])
        self._publish(1, [])
        self.assertEqual(self._state(self.tok1)[1]['state'], 'idle')

    def test_19_confirming_shows_a_thank_you_then_returns_to_idle(self):
        self._publish(1, [(self.products[0], 1)])
        self._post('/ocb/publish', {'config_id': self.pos_config.id, 'lane': 1,
                                    'action': 'confirm'})
        res = self._state(self.tok1)[1]
        self.assertEqual(res['state'], 'confirmed')
        self.assertEqual(res['order']['lines'], [],
                         'the confirmation shows no items — the order is done')
        # and it does not sit there for the next guest
        from odoo import fields as odoo_fields
        from datetime import timedelta
        self.d1.sudo().write({
            'payload_at': odoo_fields.Datetime.now() - timedelta(seconds=60)})
        self.env.flush_all()
        self.assertEqual(self._state(self.tok1)[1]['state'], 'idle')

    # ==================================================================
    # two lanes
    # ==================================================================
    def test_20_two_lanes_never_see_each_other(self):
        self._publish(1, [(self.products[0], 1)])
        self._publish(2, [(self.products[1], 3)])
        one = self._state(self.tok1)[1]
        two = self._state(self.tok2)[1]
        self.assertEqual(one['display']['lane'], 1)
        self.assertEqual(two['display']['lane'], 2)
        self.assertEqual([l['name'] for l in one['order']['lines']],
                         [self.products[0].name])
        self.assertEqual([l['name'] for l in two['order']['lines']],
                         [self.products[1].name])
        self.assertNotEqual(one['order']['money']['total'],
                            two['order']['money']['total'])

    def test_21_clearing_one_lane_leaves_the_other_alone(self):
        self._publish(1, [(self.products[0], 1)])
        self._publish(2, [(self.products[1], 1)])
        self._publish(1, [], action='clear')
        self.assertEqual(self._state(self.tok1)[1]['state'], 'idle')
        self.assertEqual(self._state(self.tok2)[1]['state'], 'ordering',
                         'lane 2 was still taking an order')

    def test_22_a_new_customer_never_inherits_the_previous_order(self):
        # The switch the brief calls out: order A ends, vehicle B begins, and B must
        # never see A's items under B's heading.
        self._publish(1, [(self.products[0], 4)])
        self._publish(1, [], action='clear')
        self._publish(1, [(self.products[1], 1)])
        res = self._state(self.tok1)[1]
        names = [l['name'] for l in res['order']['lines']]
        self.assertEqual(names, [self.products[1].name])
        self.assertNotIn(self.products[0].name, names)

    # ==================================================================
    # revision / staleness
    # ==================================================================
    def test_23_the_revision_only_goes_forward(self):
        seen = []
        for qty in (1, 2, 3):
            self._publish(1, [(self.products[0], qty)])
            seen.append(self._state(self.tok1)[1]['revision'])
        self.assertEqual(seen, sorted(seen), 'revisions must be monotonic: %s' % seen)
        self.assertEqual(len(set(seen)), 3, 'every change is a new revision')

    def test_24_clearing_and_confirming_also_advance_the_revision(self):
        self._publish(1, [(self.products[0], 1)])
        a = self._state(self.tok1)[1]['revision']
        self._publish(1, [], action='clear')
        b = self._state(self.tok1)[1]['revision']
        self.assertGreater(b, a, 'a display polling across a clear must see it as newer')

    # ==================================================================
    # operator side
    # ==================================================================
    def test_25_a_lane_with_no_display_does_not_stop_order_taking(self):
        self.d2.sudo().unlink()
        self.env.flush_all()
        code, res = self._publish(2, [(self.products[0], 1)])
        self.assertEqual(code, 200, res)
        self.assertTrue(res['ok'])
        self.assertFalse(res['display'], 'reported as absent, and nothing raised')

    def test_26_the_operator_is_told_whether_the_board_is_alive(self):
        code, res = self._post('/ocb/status', {'config_id': self.pos_config.id, 'lane': 1})
        self.assertEqual(code, 200, res)
        self.assertTrue(res['configured'])
        self.assertFalse(res['online'], 'it has never polled')
        self._state(self.tok1)                       # the display checks in
        res = self._post('/ocb/status', {'config_id': self.pos_config.id, 'lane': 1})[1]
        self.assertTrue(res['online'], 'and now it is online')

    def test_27_publishing_requires_staff_authentication(self):
        r = self.url_open('/mezze/api/v1/ocb/publish',
                          data=json.dumps({'config_id': self.pos_config.id, 'lane': 1,
                                           'lines': []}),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        self.assertIn(r.status_code, (401, 403),
                      'the customer read is public; publishing is not')

    # ==================================================================
    # long orders and performance
    # ==================================================================
    def test_28_a_long_order_is_carried_whole(self):
        lines = [(self.products[i % len(self.products)], (i % 3) + 1) for i in range(20)]
        self._publish(1, lines)
        res = self._state(self.tok1)[1]
        # products repeat in the fixture, so assert the money rather than the count
        self.assertTrue(res['order']['lines'])
        self.assertGreater(res['order']['money']['total'], 0)
        self.assertAlmostEqual(
            sum(l['line_total'] for l in res['order']['lines']),
            res['order']['money']['total'], 2)

    def test_29_pricing_does_not_scale_with_the_number_of_lines(self):
        # A customer screen polls constantly, so a per-line product or pricelist read
        # would be an N+1 on the hottest request in the product.
        #
        # The gate is DOUBLING: 20 lines and 40 lines of the same products must cost
        # the same, because the work is bounded by how many distinct products and tax
        # groups exist, not by how much the operator typed. An absolute count would
        # only pin today's ORM.
        import re
        pattern = re.compile(r'product_product|product_template|account_tax|product_pricelist')

        def queries_for(n):
            lines = [{'product_id': self.products[i % len(self.products)].id, 'qty': 1}
                     for i in range(n)]
            self.env.invalidate_all()
            seen = []
            cr = self.env.cr
            original = cr.execute

            def spy(query, params=None, log_exceptions=True):
                seen.append(str(getattr(query, 'code', query)))
                return original(query, params, log_exceptions)

            cr.execute = spy
            try:
                self.d1._price_lines(lines)
            finally:
                cr.execute = original
            return len([q for q in seen if pattern.search(q)])

        one, twenty, forty = queries_for(1), queries_for(20), queries_for(40)
        self.assertEqual(twenty, forty,
                         'doubling the lines changed the query count %d -> %d, which '
                         'is the shape of an N+1' % (twenty, forty))
        self.assertLessEqual(twenty, one + 8,
                             'a long order costs a little more than a short one '
                             '(products and taxes), not proportionally more '
                             '(%d vs %d)' % (twenty, one))

    def test_30_the_state_read_is_a_single_row_lookup(self):
        self._publish(1, [(self.products[0], 3)])
        seen = []
        cr = self.env.cr
        original = cr.execute

        def spy(query, params=None, log_exceptions=True):
            seen.append(str(getattr(query, 'code', query)))
            return original(query, params, log_exceptions)

        self.env.invalidate_all()
        cr.execute = spy
        try:
            self.d1._snapshot()
        finally:
            cr.execute = original
        touched = [q for q in seen if 'mezze_ocb_display' in q]
        self.assertLessEqual(len(touched), 2,
                             'rendering the snapshot reads the display row, not a join '
                             'of everything (%d)' % len(touched))
