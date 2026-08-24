"""Orders Mezze writes must be readable by the NATIVE Odoo POS client.

Both tills write to the same `pos.order` table, so "works in Mezze" is only half
the contract. A cashier who opens Register from the Odoo backend loads every
draft on the branch, and one malformed row there stops the whole app — not the
one order, the app.

That is not hypothetical. It happened.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_native_interop')
class TestNativePosInterop(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'interop-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        icp.set_param('mezze_bridge.default_branch_id', str(self.pos_config.id))
        self.session = self.open_test_session()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='interop-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        return r.status_code, r.json()

    def test_01_a_mezze_order_carries_the_shape_native_pos_parses(self):
        """`'{}'` is TRUTHY, and that is the whole bug.

        native `pos_order.js` builds its own default only when the field is
        FALSY. Given the string `'{}'` it takes the JSON.parse branch instead and
        ends up with a bare object that has no `lines` key. `getOrderChanges`
        then reads `.lines` and hands undefined to `Object.entries`:

            TypeError: Cannot convert undefined or null to object
                at getOrderChanges
                at FloorScreen.getChangeCount

        The floor screen calls that for every table on every render, so a single
        Mezze order stopped the native register from opening at all — and native
        caches loaded orders in IndexedDB, so cancelling the order server-side did
        not rescue a browser that had already read it.
        """
        code, res = self._post('/orders/sync', {
            'uuid': 'interop-1', 'session_id': self.session.id,
            'lines': [{'product_id': self.product.id, 'qty': 1}], 'draft': True})
        self.assertEqual(code, 200, res)
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'interop-1')], limit=1)
        self.assertTrue(order)

        raw = order.last_order_preparation_change
        self.assertTrue(raw, 'the field is written, not left empty')
        parsed = json.loads(raw)
        # `lines` is the key getOrderChanges dereferences without checking.
        self.assertIn('lines', parsed, 'native reads .lines off this object')
        self.assertEqual(parsed['lines'], {}, 'nothing has been fired yet')
        # the rest of native's default, so no other getter meets undefined either
        for key in ('metadata', 'general_customer_note', 'internal_note', 'sittingMode'):
            self.assertIn(key, parsed, 'native default key %r is present' % key)

    def test_02_every_order_mezze_creates_has_it(self):
        """Not just the draft path — every route that mints a pos.order.

        The string was written in nine places across four controllers. A test that
        only covered /orders/sync would have left eight of them able to poison the
        native register.
        """
        from odoo.addons.mezze_bridge.domain.preparation import (
            PREPARATION_DEFAULT, empty_preparation_change)

        parsed = json.loads(empty_preparation_change())
        self.assertEqual(parsed, PREPARATION_DEFAULT)
        # A fresh string per call: this goes into ORM write payloads, and a shared
        # mutable default is how two orders end up pointing at one dict.
        self.assertIsNot(json.loads(empty_preparation_change()), parsed)

        import os
        import re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        offenders = []
        for folder in ('controllers', 'models'):
            path = os.path.join(root, folder)
            for name in sorted(os.listdir(path)):
                if not name.endswith('.py'):
                    continue
                with open(os.path.join(path, name), encoding='utf-8') as fh:
                    body = fh.read()
                if re.search(r"'last_order_preparation_change':\s*'\{\}'", body):
                    offenders.append('%s/%s' % (folder, name))
        self.assertFalse(
            offenders,
            "these still write the bare '{}' native cannot parse: %s" % offenders)


@tagged('post_install', '-at_install', 'mezze_void_closes')
class TestVoidActuallyVoids(MezzeHttpCase):
    """A voided order must stop being an open bill.

    /orders/void cancelled the kitchen tickets, wrote an audit row, answered 200 —
    and left `pos.order.state` on 'draft', still bound to its table. The Register
    clears the cashier's screen on that 200, so the check stayed live, payable and
    counted as occupancy while the one person who could have noticed was looking at
    an empty till.
    """
    # RESTAURANT: without a table there is no seat for a void to release, and
    # test_02 skipped — so "a voided order does not go on holding a seat" was an
    # assertion nobody had ever run.
    fixture_profile = 'RESTAURANT'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'void-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='void-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        return r.status_code, r.json()

    def _draft(self, uuid, table=None):
        body = {'uuid': uuid, 'session_id': self.session.id,
                'lines': [{'product_id': self.product.id, 'qty': 2}], 'draft': True}
        if table:
            body['table_id'] = table.id
        code, res = self._post('/orders/sync', body)
        self.assertEqual(code, 200, res)
        order = self.env['pos.order'].sudo().search([('uuid', '=', uuid)], limit=1)
        self.assertTrue(order and order.state == 'draft', 'the fixture starts open')
        return order

    def test_01_void_leaves_no_open_bill(self):
        order = self._draft('void-me-1')
        code, res = self._post('/orders/void', {
            'session_id': self.session.id, 'order_uuid': order.uuid,
            'reason': 'guest left'})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)
        order.invalidate_recordset()
        self.assertEqual(order.state, 'cancel',
                         'the order the cashier voided is no longer an open bill')

    def test_02_void_releases_the_table(self):
        """A voided order does not go on holding a seat."""
        Table = self.env['restaurant.table'].sudo()
        table = Table.search([], limit=1)
        order = self._draft('void-me-2', table=table)
        self.assertEqual(order.table_id, table, 'the fixture seats it first')

        code, res = self._post('/orders/void', {
            'session_id': self.session.id, 'order_uuid': order.uuid,
            'reason': 'walked out'})
        self.assertEqual(code, 200, res)
        order.invalidate_recordset()
        self.assertEqual(order.state, 'cancel')
        self.assertFalse(order.table_id, 'the table is free for the next guests')

    def test_03_a_paid_bill_is_still_refused(self):
        """Void is for an OPEN check. After payment the answer is a refund, and
        this must not become a way to erase a settled sale."""
        code, res = self._post('/orders/sync', {
            'uuid': 'void-me-3', 'session_id': self.session.id,
            'lines': [{'product_id': self.product.id, 'qty': 1}]})
        self.assertEqual(code, 200, res)
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'void-me-3')], limit=1)
        self.assertNotEqual(order.state, 'draft', 'the fixture is settled')

        code, res = self._post('/orders/void', {
            'session_id': self.session.id, 'order_uuid': order.uuid, 'reason': 'nope'})
        self.assertEqual(code, 400, res)
        order.invalidate_recordset()
        self.assertNotEqual(order.state, 'cancel', 'a paid sale is untouched')
