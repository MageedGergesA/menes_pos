"""R2A CP5 — Table → Register contract (authenticated).

Covers the production transition /mezze/floor → /mezze/pos?table_id=<id>:
  * an AVAILABLE table resolves a branch-scoped context (no order yet);
  * an OCCUPIED table resumes the authoritative draft (order_uuid + guests);
  * an INVALID / cross-branch table id is refused safely (no exposure, no crash);
  * repeated send/charge with the table's STABLE uuid never duplicates the order.

The server stays authoritative for which order sits on a table; the page only mirrors
it. No order/table/reservation FSM is touched here.
"""
import json
import re
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import MezzeHttpCase

_BOOT_RE = re.compile(
    r'<script[^>]*id="mezze-boot"[^>]*>(.*?)</script>', re.DOTALL)


def _js_body(body):
    """Wrap a browser_js assertion body in an async IIFE that reports errors."""
    return "(async () => {\n" + body + "\n})().catch(e => console.error(e.message || e));"


@tagged('post_install', '-at_install', 'mezze_floor')
class TestFloorRegister(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product.write({'available_in_pos': True, 'list_price': 42.0, 'taxes_id': [(5, 0, 0)]})
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        # ensure ONE fully-open session (the fixture provisions none) so orders can bind
        sess = cls.pos_config.current_session_id
        if not sess or sess.state not in ('opened', 'opening_control'):
            sess = cls.env['pos.session'].create(
                {'config_id': cls.pos_config.id, 'user_id': cls.env.uid})
        if sess.state == 'opening_control':
            try:
                sess.set_opening_control(0, None)
            except Exception:  # noqa: BLE001
                pass
        cls.table = cls.tables[0]  # table_number 1

    # -- helpers -----------------------------------------------------------
    def _boot(self, url):
        """GET an authenticated cashier page and return its parsed boot payload."""
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        m = _BOOT_RE.search(resp.text)
        self.assertTrue(m, "boot payload present in %s" % url)
        return json.loads(m.group(1).replace('\\u003c', '<'))

    def _api(self, path, params, token):
        return self.url_open(
            '/mezze/api/v1' + path,
            data=json.dumps({**params, 'token': token}),
            headers={'Content-Type': 'application/json'})

    # -- tests -------------------------------------------------------------
    def test_01_available_table_context(self):
        self.authenticate('admin', 'admin')
        boot = self._boot('/mezze/pos?table_id=%d' % self.table.id)
        t = boot.get('table')
        self.assertTrue(t and not t.get('error'), 'available table resolves a context')
        self.assertEqual(t['id'], self.table.id)
        self.assertEqual(str(t['name']), str(self.table.table_number))
        self.assertEqual(t['floor'], self.table.floor_id.name)
        self.assertIsNone(t['order_uuid'], 'an available table has no order to resume')

    def test_02_invalid_table_blocked(self):
        self.authenticate('admin', 'admin')
        boot = self._boot('/mezze/pos?table_id=999999')
        self.assertEqual((boot.get('table') or {}).get('error'), 'invalid_table',
                         'a stale/unknown table id is refused safely')
        # counter mode still boots (no crash, no wrong-table fallback)
        self.assertTrue(boot.get('ok'))

    def test_03_counter_mode_no_table(self):
        self.authenticate('admin', 'admin')
        boot = self._boot('/mezze/pos')
        self.assertIsNone(boot.get('table'), 'no table_id => counter mode (table is None)')

    def test_04_occupied_table_resumes_authoritative_order(self):
        # a draft order sitting on the table must be the one the Register resumes
        order = self.env['pos.order'].create({
            'session_id': self.pos_config.current_session_id.id,
            'config_id': self.pos_config.id, 'company_id': self.pos_config.company_id.id,
            'table_id': self.table.id, 'state': 'draft',
            'amount_total': 84.0, 'amount_tax': 0.0, 'amount_paid': 0.0, 'amount_return': 0.0,
            'customer_count': 4,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 2,
                              'price_unit': 42.0, 'price_subtotal': 84.0, 'price_subtotal_incl': 84.0})],
        })
        self.authenticate('admin', 'admin')
        boot = self._boot('/mezze/pos?table_id=%d' % self.table.id)
        t = boot['table']
        self.assertEqual(t['order_uuid'], order.uuid, 'resumes the authoritative draft on the table')
        self.assertEqual(t['guests'], 4, 'guest count matches the order')
        order.unlink()

    def test_05_stable_uuid_never_duplicates(self):
        self.authenticate('admin', 'admin')
        boot = self._boot('/mezze/pos?table_id=%d' % self.table.id)
        token = boot['token']
        sid = self.pos_config.current_session_id.id
        uuid = 'cp5-stable-uuid-1'
        body = {'uuid': uuid, 'session_id': sid, 'draft': True,
                'table_id': self.table.id,
                'lines': [{'product_id': self.product.id, 'qty': 1}]}
        # two sends with the SAME stable uuid (as the table-bound Register does)
        self._api('/orders/sync', body, token)
        self._api('/orders/sync', dict(body, lines=[{'product_id': self.product.id, 'qty': 2}]), token)
        orders = self.env['pos.order'].search(
            [('table_id', '=', self.table.id), ('state', '=', 'draft'),
             ('config_id', '=', self.pos_config.id)])
        self.assertEqual(len(orders), 1, 'repeated send with the stable uuid => ONE order, no duplicate')
        self.assertEqual(orders.uuid, uuid)
        # NOT duplicating is only half of it: the second send must also be HONOURED.
        # It was not — the endpoint short-circuited on the uuid and kept the older
        # lines — and because the payment screen takes its total from that response,
        # a cashier who added items to a table's bill was shown, and collected, the
        # amount from before they were added.
        self.assertEqual(sum(orders.lines.mapped('qty')), 2,
                         'the second send REPLACED the draft: not discarded (1) and '
                         'not appended (3)')

    def test_05b_a_draft_that_changes_is_re_priced_not_ignored(self):
        """The money the till offers must be the money the cart shows.

        A table-bound Register keeps ONE uuid for the life of the bill, so every
        save after the first was a repeat of a uuid the server had already seen.
        Treating that as a duplicate submission is right for a payment and wrong
        for a cart: the draft kept its original lines while the cashier went on
        adding to it, and /orders/sync answered with the stale amount_total that
        the payment screen then quoted to the guest.

        Reproduced here as money, not as line counts, because that is how it
        reached the floor.
        """
        self.authenticate('admin', 'admin')
        boot = self._boot('/mezze/pos?table_id=%d' % self.table.id)
        token = boot['token']
        sid = self.pos_config.current_session_id.id
        uuid = 'cp5-reprice-1'
        base = {'uuid': uuid, 'session_id': sid, 'draft': True,
                'table_id': self.table.id}

        first = self._api('/orders/sync', dict(
            base, lines=[{'product_id': self.product.id, 'qty': 1}]), token).json()
        one_item = first['amount_total']

        second = self._api('/orders/sync', dict(
            base, lines=[{'product_id': self.product.id, 'qty': 3}]), token).json()

        self.assertIn('amount_total', second, 'second sync answered: %s' % (second,))
        self.assertGreater(second['amount_total'], one_item,
                           'adding two more of the same product must cost more, '
                           'got %s then %s' % (one_item, second['amount_total']))
        order = self.env['pos.order'].search([('uuid', '=', uuid)])
        self.assertEqual(len(order), 1)
        self.assertEqual(sum(order.lines.mapped('qty')), 3)
        self.assertAlmostEqual(second['amount_total'], order.amount_total, 2,
                               'the quoted total is the order the server holds')

    def test_05c_a_paid_order_is_still_protected_from_a_repeat(self):
        """Letting DRAFTS change must not weaken the double-charge guard.

        The idempotent short-circuit exists so a retried submission — a tap that
        looked like it failed, a network that dropped after the write — cannot
        take the money twice. That protection is about orders that are no longer
        drafts, and it stays exactly as it was.
        """
        self.authenticate('admin', 'admin')
        boot = self._boot('/mezze/pos?table_id=%d' % self.table.id)
        token = boot['token']
        sid = self.pos_config.current_session_id.id
        uuid = 'cp5-paid-guard-1'
        self._api('/orders/sync', {
            'uuid': uuid, 'session_id': sid, 'draft': True,
            'table_id': self.table.id,
            'lines': [{'product_id': self.product.id, 'qty': 1}]}, token)
        order = self.env['pos.order'].search([('uuid', '=', uuid)])
        order.sudo().write({'state': 'paid'})
        self.env.flush_all()

        again = self._api('/orders/sync', {
            'uuid': uuid, 'session_id': sid, 'draft': True,
            'table_id': self.table.id,
            'lines': [{'product_id': self.product.id, 'qty': 9}]}, token).json()

        self.assertTrue(again.get('duplicate'),
                        'a settled order must still answer as a duplicate')
        order.invalidate_recordset()
        self.assertEqual(sum(order.lines.mapped('qty')), 1,
                         'a paid order must not be rewritten by a late repeat')

    # ---- CP6: reverse workflow — counter order → assign table + guest count ----
    def _counter_draft(self, token, uuid, qty=2):
        """Persist a counter draft (no table) via the real /orders/sync path."""
        self._api('/orders/sync', {
            'uuid': uuid, 'session_id': self.pos_config.current_session_id.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': qty}]}, token)
        return self.env['pos.order'].search([('uuid', '=', uuid)], limit=1)

    def test_06_counter_assign_to_available_keeps_uuid(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        uuid = 'cp6-counter-1'
        order = self._counter_draft(token, uuid, qty=2)
        self.assertTrue(order, 'counter draft created')
        self.assertFalse(order.table_id, 'counter draft has no table yet')
        total_before, lines_before = order.amount_total, len(order.lines)
        target = self.tables[1]  # table_number 2 (available)
        r = self._api('/orders/assign_table',
                      {'uuid': uuid, 'table_id': target.id, 'config_id': self.pos_config.id}, token)
        self.assertEqual(r.json().get('ok'), True, r.text)
        order.invalidate_recordset()
        self.assertEqual(order.table_id.id, target.id, 'order now bound to the chosen table')
        self.assertEqual(order.uuid, uuid, 'SAME authoritative uuid preserved')
        self.assertEqual(order.amount_total, total_before, 'total unchanged by assignment')
        self.assertEqual(len(order.lines), lines_before, 'lines unchanged by assignment')
        dupes = self.env['pos.order'].search([('uuid', '=', uuid)])
        self.assertEqual(len(dupes), 1, 'no duplicate order created')

    def test_07_assign_to_occupied_blocked(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        target = self.tables[2]  # table_number 3
        # an existing draft occupies the target
        occ = self._counter_draft(token, 'cp6-occ-existing', qty=1)
        occ.write({'table_id': target.id})
        # a separate counter order tries to assign to the same (occupied) table
        mine = self._counter_draft(token, 'cp6-occ-mine', qty=2)
        r = self._api('/orders/assign_table',
                      {'uuid': 'cp6-occ-mine', 'table_id': target.id, 'config_id': self.pos_config.id}, token)
        self.assertEqual(r.json().get('error'), 'table_occupied', 'occupied target refused')
        mine.invalidate_recordset(); occ.invalidate_recordset()
        self.assertFalse(mine.table_id, 'my order NOT bound to the occupied table')
        self.assertEqual(occ.table_id.id, target.id, 'existing order on the table untouched')
        on_table = self.env['pos.order'].search(
            [('table_id', '=', target.id), ('state', '=', 'draft')])
        self.assertEqual(len(on_table), 1, 'no merge/duplicate on the occupied table')

    def test_08_assign_to_reserved_blocked(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        target = self.tables[1]  # table_number 2
        if 'mezze.reservation' in self.env:
            self.env['mezze.reservation'].create({
                'table_id': target.id, 'config_id': self.pos_config.id, 'guests': 2,
                'state': 'booked', 'customer_name': 'Reserved Guest',
                'start': fields.Datetime.to_string(fields.Datetime.now() + __import__('datetime').timedelta(minutes=10)),
            })
            mine = self._counter_draft(token, 'cp6-res-mine', qty=1)
            r = self._api('/orders/assign_table',
                          {'uuid': 'cp6-res-mine', 'table_id': target.id, 'config_id': self.pos_config.id}, token)
            self.assertEqual(r.json().get('error'), 'table_reserved',
                             'reserved target refused (no seating bypass)')
            mine.invalidate_recordset()
            self.assertFalse(mine.table_id, 'no assignment onto a reserved table')

    def test_09_assign_invalid_table_blocked(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        self._counter_draft(token, 'cp6-inv-mine', qty=1)
        r = self._api('/orders/assign_table',
                      {'uuid': 'cp6-inv-mine', 'table_id': 999999, 'config_id': self.pos_config.id}, token)
        self.assertEqual(r.json().get('error'), 'invalid_table', 'unknown/cross-branch table refused')

    def test_10_guest_count_persists(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        uuid = 'cp6-guests-1'
        order = self._counter_draft(token, uuid, qty=1)
        order.write({'table_id': self.tables[0].id})
        # set 4, then attempt 0 -> clamped to the minimum (>=1)
        self._api('/orders/set_guests', {'uuid': uuid, 'guests': 4, 'config_id': self.pos_config.id}, token)
        order.invalidate_recordset()
        self.assertEqual(order.customer_count, 4, 'guest count is authoritative on the order')
        self._api('/orders/set_guests', {'uuid': uuid, 'guests': 0, 'config_id': self.pos_config.id}, token)
        order.invalidate_recordset()
        self.assertEqual(order.customer_count, 1, 'guest count never drops below 1')
        # a reopen resolves the persisted guest count back into the boot context
        boot = self._boot('/mezze/pos?table_id=%d' % self.tables[0].id)
        self.assertEqual(boot['table']['guests'], 1)

    # ---- CP6 UI renders (fresh headless browser — authoritative) ----
    def test_11_cp6_controls_render(self):
        prelude = (
            "const $=s=>document.querySelector(s);"
            "async function waitFor(f,l,ms=15000){const t0=Date.now();"
            "while(Date.now()-t0<ms){try{if(f())return true;}catch(e){}"
            "await new Promise(r=>setTimeout(r,100));}throw new Error('timeout: '+l);}"
            "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
            "const ok=()=>console.log('test successful');")
        # counter order → the "Assign table" control appears
        self.browser_js('/mezze/pos', prelude + _js_body(r"""
            await waitFor(() => document.querySelectorAll('.mz-tile').length > 0, 'menu');
            document.querySelector('.mz-tile').click();
            await waitFor(() => document.querySelector('.mz-line'), 'item added');
            await waitFor(() => [...document.querySelectorAll('.mz-cart button')]
                .some(b => /assign table/i.test(b.textContent)), 'Assign table button renders');
            ok();
        """), login='admin')
        # table-bound Register → guest stepper + "Send to table" + "Move table" render
        self.browser_js('/mezze/pos?table_id=%d' % self.tables[0].id, prelude + _js_body(r"""
            await waitFor(() => document.querySelector('.mz-ctx--table'), 'table chip renders');
            assert(document.querySelectorAll('.mz-guest .mz-stepper__btn').length === 2, 'guest +/- steppers render');
            await waitFor(() => [...document.querySelectorAll('.mz-cart button')]
                .some(b => /send to table/i.test(b.textContent)), 'Send to table button renders');
            await waitFor(() => [...document.querySelectorAll('.mz-cart button')]
                .some(b => /move table/i.test(b.textContent)), 'Move table button renders (CP7)');
            ok();
        """), login='admin')

    # ---- CP7: transfer / merge contract (authenticated) ----
    def _table_draft(self, token, uuid, table, qty=1, guests=0, paid=0.0):
        self._api('/orders/sync', {
            'uuid': uuid, 'session_id': self.pos_config.current_session_id.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': qty}]}, token)
        o = self.env['pos.order'].search([('uuid', '=', uuid)], limit=1)
        vals = {'table_id': table.id}
        if guests and 'customer_count' in o._fields:
            vals['customer_count'] = guests
        if paid:
            vals['amount_paid'] = paid
        o.write(vals)
        return o

    def test_12_transfer_to_free_table(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        src, dst = self.tables[0], self.tables[1]  # T1 -> T2 (free)
        o = self._table_draft(token, 'cp7-xfer', src, qty=2, guests=4)
        uuid_before, lines_before, total_before = o.uuid, len(o.lines), o.amount_total
        r = self._api('/tables/transfer', {
            'session_id': self.pos_config.current_session_id.id,
            'from_table_id': src.id, 'to_table_id': dst.id, 'order_uuid': o.uuid}, token)
        self.assertEqual(r.json().get('ok'), True, r.text)
        o.invalidate_recordset()
        self.assertEqual(o.table_id.id, dst.id, 'order moved to destination')
        self.assertEqual(o.uuid, uuid_before, 'SAME order uuid preserved')
        self.assertEqual(len(o.lines), lines_before, 'lines preserved')
        self.assertEqual(o.amount_total, total_before, 'total preserved')
        self.assertFalse(self.env['pos.order'].search(
            [('table_id', '=', src.id), ('state', '=', 'draft')]), 'source table now free')
        self.assertEqual(len(self.env['pos.order'].search([('uuid', '=', uuid_before)])), 1, 'no duplicate')

    def test_13_transfer_to_occupied_blocked(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        src, dst = self.tables[0], self.tables[2]  # T1 -> T3 (occupied)
        o = self._table_draft(token, 'cp7-xfer-src', src, qty=1)
        occ = self._table_draft(token, 'cp7-xfer-dstocc', dst, qty=1)
        r = self._api('/tables/transfer', {
            'session_id': self.pos_config.current_session_id.id,
            'from_table_id': src.id, 'to_table_id': dst.id, 'order_uuid': o.uuid}, token)
        self.assertEqual(r.json().get('error'), 'transfer_failed', 'transfer onto occupied refused')
        o.invalidate_recordset()
        self.assertEqual(o.table_id.id, src.id, 'source order unchanged (still on src)')

    def test_14_merge_unpaid_combines(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        src, dst = self.tables[0], self.tables[1]
        s = self._table_draft(token, 'cp7-merge-src', src, qty=2, guests=2)
        d = self._table_draft(token, 'cp7-merge-dst', dst, qty=1, guests=3)
        s_lines, d_lines = len(s.lines), len(d.lines)
        r = self._api('/tables/merge', {
            'session_id': self.pos_config.current_session_id.id,
            'from_table_id': src.id, 'to_table_id': dst.id}, token)
        body = r.json()
        self.assertTrue(body.get('ok') and body.get('merged'), r.text)
        d.invalidate_recordset()
        self.assertEqual(len(d.lines), s_lines + d_lines, 'destination has combined lines')
        if 'customer_count' in d._fields:
            self.assertEqual(d.customer_count, 5, 'guest counts add up (2+3)')
        self.assertFalse(self.env['pos.order'].search([('uuid', '=', 'cp7-merge-src')]),
                         'emptied source draft removed (no duplicate)')

    def test_15_merge_with_payment_blocked(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        src, dst = self.tables[0], self.tables[1]
        s = self._table_draft(token, 'cp7-pay-src', src, qty=2, paid=10.0)  # financial state
        d = self._table_draft(token, 'cp7-pay-dst', dst, qty=1)
        r = self._api('/tables/merge', {
            'session_id': self.pos_config.current_session_id.id,
            'from_table_id': src.id, 'to_table_id': dst.id}, token)  # NO combine_confirm
        self.assertEqual(r.json().get('error'), 'merge_blocked_payments',
                         'financial safeguard blocks the merge')
        # both orders preserved, nothing moved
        self.assertTrue(self.env['pos.order'].search([('uuid', '=', 'cp7-pay-src')]), 'source preserved')
        d.invalidate_recordset()
        self.assertEqual(len(d.lines), 1, 'destination lines unchanged (nothing moved)')

    def test_16_move_picker_source_labeled_current(self):
        # CP7 polish: in move mode the source tile reads "Current table" (not "Occupied ·
        # merge"); other occupied = merge, free = transfer, reserved = disabled.
        src, occ, res_t = self.tables[0], self.tables[1], self.tables[2]
        free_t = self.env['restaurant.table'].create(
            {'table_number': 4, 'floor_id': self.floor.id, 'seats': 4})
        sess = self.pos_config.current_session_id.id

        def mk(table):
            return self.env['pos.order'].create({
                'session_id': sess, 'config_id': self.pos_config.id,
                'company_id': self.pos_config.company_id.id, 'table_id': table.id, 'state': 'draft',
                'amount_total': 42.0, 'amount_tax': 0.0, 'amount_paid': 0.0, 'amount_return': 0.0,
                'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1, 'price_unit': 42.0,
                                  'price_subtotal': 42.0, 'price_subtotal_incl': 42.0})]})
        mk(src)
        mk(occ)
        if 'mezze.reservation' in self.env:
            self.env['mezze.reservation'].create({
                'table_id': res_t.id, 'config_id': self.pos_config.id, 'guests': 2, 'state': 'booked',
                'customer_name': 'Held', 'start': fields.Datetime.to_string(fields.Datetime.now() + timedelta(minutes=10))})
        prelude = (
            "async function waitFor(f,l,ms=15000){const t0=Date.now();"
            "while(Date.now()-t0<ms){try{if(f())return true;}catch(e){}"
            "await new Promise(r=>setTimeout(r,100));}throw new Error('timeout: '+l);}"
            "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
            "function tile(n){return [...document.querySelectorAll('.mz-assign__t')].find(b=>{"
            "const x=b.querySelector('.mz-assign__num');return x&&x.textContent.trim()===n;});}"
            "function meta(n){const t=tile(n);return t?t.querySelector('.mz-assign__meta').textContent.replace(/\\s+/g,' ').trim():null;}"
            "const ok=()=>console.log('test successful');")
        self.browser_js('/mezze/pos?table_id=%d' % src.id, prelude + _js_body(r"""
            await waitFor(() => document.querySelectorAll('.mz-tile').length > 0, 'menu');
            const moveBtn = [...document.querySelectorAll('.mz-cart button')].find(b=>/move table/i.test(b.textContent));
            assert(moveBtn, 'Move table button present');
            moveBtn.click();
            await waitFor(() => document.querySelector('.mz-assign__t'), 'picker open');
            // source tile: labelled "Current table" AND disabled (never "Occupied · merge")
            assert(tile('%(src)d') && tile('%(src)d').disabled, 'source tile disabled');
            assert(meta('%(src)d') === 'Current table', 'source meta=Current table, got: ' + meta('%(src)d'));
            // another occupied table: still the merge target
            assert(tile('%(occ)d') && !tile('%(occ)d').disabled, 'occupied dest selectable');
            assert(/Occupied . merge/.test(meta('%(occ)d')), 'occupied meta=Occupied · merge, got: ' + meta('%(occ)d'));
            // free table: transfer target
            assert(tile('%(free)d') && !tile('%(free)d').disabled, 'free dest selectable');
            assert(/Open/.test(meta('%(free)d')), 'free meta=Open, got: ' + meta('%(free)d'));
            // reserved table: disabled
            assert(tile('%(res)d') && tile('%(res)d').disabled, 'reserved disabled');
            assert(meta('%(res)d') === 'Reserved', 'reserved meta=Reserved, got: ' + meta('%(res)d'));
            ok();
        """ % {'src': src.table_number, 'occ': occ.table_number,
               'free': free_t.table_number, 'res': res_t.table_number}), login='admin')

    # =====================================================================
    # CP8 — SAFE TABLE RELEASE
    #
    # The backend has NO stored table-occupancy state and NO release endpoint:
    # a table is "occupied" iff a *draft* pos.order is bound to it (floors()
    # keys off state=='draft'). Release is therefore an emergent side-effect of
    # the order leaving 'draft' — which only happens on full payment settlement
    # (action_pos_order_paid) or a money-guarded transfer/merge. These tests
    # prove that lifecycle end-to-end through the REAL /orders/pay path.
    # =====================================================================
    def _floor_status(self, token, table_id, config_id=None):
        """Return the status the Floor app would render for one table."""
        r = self._api('/floors', {'config_id': config_id or self.pos_config.id}, token)
        payload = r.json()
        for fl in payload.get('floors', []):
            for t in fl.get('tables', []):
                if t.get('id') == table_id:
                    return t.get('status')
        return None

    def test_17_unpaid_table_cannot_release(self):
        # An unpaid, positive-balance draft on a table stays Occupied — there is
        # no lifecycle action (short of payment) that frees it, and re-reading the
        # floor never flips it to available.
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        table = self.tables[0]
        o = self._table_draft(token, 'cp8-unpaid', table, qty=2, guests=3)
        self.assertGreater(o.amount_total, 0.0, 'positive balance')
        self.assertEqual(o.state, 'draft')
        self.assertEqual(self._floor_status(token, table.id), 'occupied',
                         'unpaid table is occupied')
        # re-read the floor twice more (a "refresh"/reopen) — still occupied
        self._api('/floors', {'config_id': self.pos_config.id}, token)
        self.assertEqual(self._floor_status(token, table.id), 'occupied',
                         'refresh preserves occupied (no drift to available)')
        o.invalidate_recordset()
        self.assertEqual(o.state, 'draft', 'order still open')
        self.assertEqual(o.table_id.id, table.id, 'order still bound to the table')
        self.assertEqual(o.amount_paid, 0.0, 'balance unchanged')
        # structural: no endpoint capable of freeing it without payment (see test_23)

    def test_18_partial_payment_keeps_table_occupied(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        table = self.tables[0]
        o = self._table_draft(token, 'cp8-partial', table, qty=2)  # total = 84.0
        total = round(o.amount_total, 2)
        self.assertGreater(total, 50.0)
        r = self._api('/orders/pay',
                      {'uuid': 'cp8-partial', 'amount': 50.0, 'tender_key': 'cp8-partial-t1'}, token)
        body = r.json()
        self.assertTrue(body.get('ok') and body.get('partial'), r.text)
        self.assertAlmostEqual(body.get('amount_paid'), 50.0, places=2)
        self.assertAlmostEqual(body.get('remaining'), round(total - 50.0, 2), places=2)
        o.invalidate_recordset()
        self.assertEqual(o.state, 'draft', 'partial keeps the order open')
        self.assertAlmostEqual(o.amount_paid, 50.0, places=2)
        self.assertEqual(o.table_id.id, table.id, 'binding intact')
        self.assertEqual(self._floor_status(token, table.id), 'occupied',
                         'partially-paid table stays occupied (never flips Open)')

    def test_19_full_payment_releases_table_once(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        table = self.tables[0]
        o = self._table_draft(token, 'cp8-full', table, qty=2)
        oid, ouuid = o.id, o.uuid
        self.assertEqual(self._floor_status(token, table.id), 'occupied')
        # full tender (amount omitted => full remaining)
        r = self._api('/orders/pay', {'uuid': 'cp8-full', 'tender_key': 'cp8-full-t1'}, token)
        body = r.json()
        self.assertTrue(body.get('ok'), r.text)
        self.assertAlmostEqual(body.get('remaining'), 0.0, places=2)
        o.invalidate_recordset()
        self.assertIn(o.state, ('paid', 'done', 'invoiced'), 'order reached a completed state')
        # table released: no draft remains on it, floor reports available
        self.assertFalse(self.env['pos.order'].search(
            [('table_id', '=', table.id), ('state', '=', 'draft')]),
            'no active draft on the table')
        self.assertEqual(self._floor_status(token, table.id), 'available',
                         'fully-paid table becomes available')
        # order preserved historically, exactly once, one payment, no orphan/dupe
        same = self.env['pos.order'].search([('uuid', '=', ouuid)])
        self.assertEqual(len(same), 1, 'the paid order is preserved, not duplicated')
        self.assertEqual(same.id, oid, 'same order record')
        self.assertEqual(len(same.payment_ids), 1, 'exactly one payment effect')

    def test_20_payment_retry_does_not_double_release(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        table = self.tables[0]
        o = self._table_draft(token, 'cp8-retry', table, qty=2)
        ouuid = o.uuid
        key = 'cp8-retry-t1'
        r1 = self._api('/orders/pay', {'uuid': 'cp8-retry', 'tender_key': key}, token).json()
        self.assertTrue(r1.get('ok') and not r1.get('partial'), r1)
        # same logical tender retried (lost response / double submit) — SAME tender_key
        r2 = self._api('/orders/pay', {'uuid': 'cp8-retry', 'tender_key': key}, token).json()
        self.assertTrue(r2.get('idempotent'), 'retry converges to the existing result')
        o.invalidate_recordset()
        self.assertIn(o.state, ('paid', 'done', 'invoiced'))
        self.assertEqual(len(o.payment_ids), 1, 'no second payment effect on retry')
        self.assertEqual(len(self.env['pos.order'].search([('uuid', '=', ouuid)])), 1,
                         'still one order (no double-release into a new draft)')
        self.assertEqual(self._floor_status(token, table.id), 'available',
                         'table released exactly once, stays available')

    def test_21_failed_payment_keeps_table_occupied(self):
        # The subject here is the TABLE, not the tender: a payment that fails must
        # leave the table occupied. It needs some deterministic rejection to stand on.
        #
        # That used to be a cash overpay, which the till refused outright. Cash overpay
        # is now accepted and returns change (see TestChangeAndOvertender), so the same
        # request would settle the order and legitimately free the table. The failure
        # is therefore taken on a CARD, which still cannot be over-paid — a card cannot
        # hand coins back — and the assertion below is unchanged in substance.
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        table = self.tables[0]
        o = self._table_draft(token, 'cp8-fail', table, qty=1)  # total = 42.0
        r = self._api('/orders/pay',
                      {'uuid': 'cp8-fail', 'amount': 999.0, 'tender_key': 'cp8-fail-t1',
                       'payment_method_id': self.card_payment_method.id}, token)
        self.assertEqual(r.json().get('error'), 'overpay_not_cash',
                         'an over-paid card is rejected, no settlement')
        o.invalidate_recordset()
        self.assertEqual(o.state, 'draft', 'order still open after failed payment')
        self.assertEqual(len(o.payment_ids), 0, 'no payment recorded')
        self.assertEqual(o.table_id.id, table.id, 'binding intact')
        self.assertEqual(self._floor_status(token, table.id), 'occupied',
                         'failed payment must NOT release the table')

    def test_22_full_payment_drops_stale_table_context_in_ui(self):
        # CP8 UX guarantee #13: after a full payment on a table-bound Register the
        # cashier must NOT stay attached to the now-freed table. Starting a new
        # order returns to counter mode (no table chip, "Assign table" not "Send").
        self.authenticate('admin', 'admin')
        table = self.tables[0]
        prelude = (
            "const $=s=>document.querySelector(s);const $$=s=>[...document.querySelectorAll(s)];"
            "const phase=()=>($('.mz-app')?$('.mz-app').dataset.phase:null);"
            "async function waitFor(f,l,ms=15000){const t0=Date.now();"
            "while(Date.now()-t0<ms){try{if(f())return true;}catch(e){}"
            "await new Promise(r=>setTimeout(r,100));}throw new Error('timeout: '+l+' (phase='+phase()+')');}"
            "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
            "const foot=re=>$$('.mz-cart button').some(b=>re.test(b.textContent));"
            "const ok=()=>console.log('test successful');")
        self.browser_js('/mezze/pos?table_id=%d' % table.id, prelude + _js_body(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            assert($('.mz-ctx--table'), 'starts table-bound (table chip present)');
            assert(foot(/send to table/i), 'table-bound: Send to table present');
            document.querySelector('.mz-tile').click();
            await waitFor(() => $('.mz-line'), 'item added');
            $('.mz-btn--charge').click();
            await waitFor(() => phase() === 'payment', 'payment');
            const cash = $('.mz-method[data-method-mode="cash"]');
            assert(cash, 'cash method'); cash.click();
            await waitFor(() => $('.mz-tender'), 'cash tender');
            const exact = $$('.mz-quick').find(b => /exact/i.test(b.textContent));
            assert(exact, 'Exact quick-cash'); exact.click();
            $('.mz-btn--confirm').click();
            await waitFor(() => phase() === 'receipt', 'receipt');
            // start the next order — it must be DETACHED from the now-freed table.
            const nb = $$('.mz-btn, button').find(b => /new order/i.test(b.textContent));
            assert(nb, 'New order button'); nb.click();
            await waitFor(() => phase() === 'menu', 'back to menu');
            // The table binding is gone: no table chip, and the table-only actions
            // (Send/Move — rendered whenever the Register is table-bound, independent
            // of cart contents) are absent. The next order is a plain counter order.
            assert(!$('.mz-ctx--table'), 'stale table chip is GONE after payment');
            assert(!foot(/send to table/i), 'no longer bound: Send to table absent');
            assert(!foot(/move table/i), 'no longer bound: Move table absent');
            // and the Register is usable for the next sale (a line can be added)
            document.querySelector('.mz-tile:not(.mz-tile--out)').click();
            await waitFor(() => $('.mz-line'), 'next order accepts items');
            ok();
        """), login='admin')
        # DB truth: the paid order released the table (no draft left on it)
        self.assertFalse(self.env['pos.order'].search(
            [('table_id', '=', table.id), ('state', '=', 'draft')]),
            'table freed on the backend after full payment')

    def test_23_no_unsafe_release_bypass_route(self):
        # Structural safeguard (guarantee #18): the addon must expose NO route that
        # frees a table / clears its order without going through payment settlement.
        # Release is derived from order state; there is intentionally no release API.
        import os
        ctrl_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'controllers')
        forbidden = ('/table/release', '/tables/free', '/tables/release',
                     '/force_release', '/tables/unassign', '/orders/release')
        offenders = []
        for fn in os.listdir(ctrl_dir):
            if not fn.endswith('.py'):
                continue
            with open(os.path.join(ctrl_dir, fn), encoding='utf-8') as fh:
                src = fh.read()
            for pat in forbidden:
                if pat in src:
                    offenders.append('%s -> %s' % (fn, pat))
            # no controller may set a draft order's table_id to False (silent release)
            if "'table_id': False" in src or '"table_id": False' in src:
                offenders.append('%s -> table_id:=False' % fn)
        self.assertFalse(offenders, 'unsafe table-release bypass present: %r' % offenders)

    # ---- F3: navigation convergence -------------------------------------
    def test_24_nav_canonical_single_source_f3(self):
        # F3 — the app shell + workspace nav are ONE canonical family in
        # design/components.css. Before F3 they were duplicated in cashier.css and
        # floor.css and had drifted (different topbar colour/height/logo), and the
        # base never reset the UA <button> appearance, so a <button> nav item
        # rendered on `buttonface` (#EFEFEF) under themed text — measured 1.02:1
        # in High Contrast dark. This test locks the single source and the reset.
        from odoo.tools import file_open

        def load(name):
            with file_open('mezze_bridge/static/%s' % name, 'r') as fh:
                return fh.read()

        comp = load('design/components.css')
        for cls in ('.mz-topbar', '.mz-brand', '.mz-logo', '.mz-branch',
                    '.mz-topbar-right', '.mz-user', '.mz-nav', '.mz-nav__item'):
            self.assertRegex(comp, r'(^|\n)%s[,{ ]' % re.escape(cls),
                             'canonical shell/nav member %r defined in components.css' % cls)
        base = re.search(r'\n\.mz-nav__item\{(.*?)\}', comp, re.DOTALL)
        self.assertTrue(base, '.mz-nav__item base rule present')
        body = base.group(1)
        # the UA button appearance MUST be reset, or <a> and <button> render differently
        self.assertIn('appearance:none', body, 'nav base resets the UA button appearance')
        self.assertIn('background:transparent', body, 'nav base owns its background')
        self.assertIn('border:0', body, 'nav base owns its border')
        self.assertIn('min-height:44px', body, 'nav item meets the 44px operational touch target')
        self.assertRegex(comp, r'\.mz-nav__item:focus-visible\{[^}]*outline:',
                         'nav item has a visible focus indicator')
        # current is never colour-only (weight cue), like the P3I segmented control
        self.assertRegex(
            comp, r'\.mz-nav__item--active[^{]*\{[^}]*font-weight:800',
            'current nav item carries a non-colour (weight) cue')
        # and the brand fill is darkened one step exactly like .mz-btn--primary (P3A),
        # because a 14px/600 nav label is NORMAL text and needs 4.5:1 in light mode
        self.assertRegex(comp, r'\.mz-nav__item--active[^{]*\{[^}]*color-mix\(in srgb, var\(--mz-brand\) 88%',
                         'current nav fill uses the AA-verified darkened brand step')
        # SINGLE SOURCE: neither app may redefine the shell or the nav
        for app in ('src/cashier/cashier.css', 'src/floor/floor.css'):
            css = load(app)
            for cls in ('.mz-nav', '.mz-nav__item', '.mz-topbar', '.mz-brand',
                        '.mz-logo', '.mz-branch', '.mz-user'):
                self.assertNotRegex(css, r'\n%s\{' % re.escape(cls),
                                    '%s must not redefine %s (canonical owns it)' % (app, cls))

    def test_25_floor_nav_exposes_the_same_workspaces_f3(self):
        # F3 — the nav is STABLE between staff workspaces: the Floor exposes the same
        # four destinations as the Register, in the same order, and Orders/Reservations
        # are reached with a ?view= deep link (navigation only).
        prelude = (
            "async function waitFor(f,l,ms=15000){const t0=Date.now();"
            "while(Date.now()-t0<ms){try{if(f())return true;}catch(e){}"
            "await new Promise(r=>setTimeout(r,100));}throw new Error('timeout: '+l);}"
            "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
            "const ok=()=>console.log('test successful');")
        self.browser_js('/mezze/floor', prelude + _js_body(r"""
            // F3 is satisfied more strongly than it used to be: Floor and Register no
            // longer keep SIMILAR navs in step by hand — they mount the SAME rail
            // component, so the destination set cannot drift between them.
            await waitFor(() => document.querySelectorAll('.mz-rail__item').length > 4,
                          'the shared workspace rail');
            const items = [...document.querySelectorAll('.mz-rail__item')];
            const labels = items.map(e => (e.getAttribute('aria-label') || '').trim());
            for (const want of ['Point of Sale', 'Floor', 'Kitchen', 'Orders', 'Reservations']) {
                assert(labels.includes(want), 'rail exposes ' + want + ': ' + labels.join('|'));
            }
            // exactly one current, and it is the workspace we are on
            const cur = items.filter(e => e.getAttribute('aria-current') === 'page');
            assert(cur.length === 1, 'exactly one aria-current=page (' + cur.length + ')');
            assert((cur[0].getAttribute('aria-label') || '').trim() === 'Floor',
                   'the current destination is Floor');
            // navigation stays navigation — never P3 tabs
            assert(!items.some(e => e.getAttribute('role') === 'tab'), 'rail items are not role=tab');
            assert(!items.some(e => e.hasAttribute('aria-pressed')), 'rail items do not carry aria-pressed');
            // Register / Floor / Kitchen are pages a dedicated device can run on its own
            const href = t => {
                const el = items.find(e => (e.getAttribute('aria-label') || '').trim() === t);
                return (el && el.getAttribute('href')) || '';
            };
            assert(/^\/mezze\/pos\b/.test(href('Point of Sale')), 'POS is a real page link');
            assert(/^\/mezze\/kds\b/.test(href('Kitchen')), 'Kitchen is a real page link');
            // an in-Register workspace still works from here, by deep link
            assert(/\/mezze\/pos\?ws=/.test(href('Orders')),
                   'Orders deep-links into the Register: ' + href('Orders'));
            // every rail item meets the operational touch target
            for (const e of items) {
                assert(Math.round(e.getBoundingClientRect().height) >= 44,
                       'rail item >=44px: ' + (e.getAttribute('aria-label') || ''));
            }
            ok();
        """), login='admin')

    def test_26_register_view_deeplink_f3(self):
        # F3 — ?view= is NAVIGATION ONLY: it opens a workspace the nav can already open
        # by click. It runs once after a successful boot, a table-bound Register always
        # wins, and an unknown value is ignored (never an error state).
        prelude = (
            "async function waitFor(f,l,ms=15000){const t0=Date.now();"
            "while(Date.now()-t0<ms){try{if(f())return true;}catch(e){}"
            "await new Promise(r=>setTimeout(r,100));}throw new Error('timeout: '+l);}"
            "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
            "const phase=()=>document.querySelector('.mz-app').dataset.phase;"
            "const ok=()=>console.log('test successful');")
        self.browser_js('/mezze/pos?view=orders', prelude + _js_body(r"""
            await waitFor(() => phase() === 'orders', 'lands on the Orders workspace');
            const cur = [...document.querySelectorAll('.mz-nav__item')]
                .filter(e => e.getAttribute('aria-current') === 'page');
            assert(cur.length === 1 && cur[0].textContent.trim() === 'Orders', 'Orders is the current workspace');
            ok();
        """), login='admin')
        self.browser_js('/mezze/pos?view=reservations', prelude + _js_body(r"""
            await waitFor(() => phase() === 'reservations', 'lands on the Reservations workspace');
            const cur = [...document.querySelectorAll('.mz-nav__item')]
                .filter(e => e.getAttribute('aria-current') === 'page');
            assert(cur.length === 1 && cur[0].textContent.trim() === 'Reservations', 'Reservations is current');
            ok();
        """), login='admin')
        self.browser_js('/mezze/pos?view=not_a_view', prelude + _js_body(r"""
            await waitFor(() => phase() === 'menu', 'unknown view is ignored -> plain Register');
            ok();
        """), login='admin')
        # a table-bound entry carries an order context and must land on the Register
        self.browser_js('/mezze/pos?view=orders&table_id=%d' % self.tables[0].id,
                        prelude + _js_body(r"""
            await waitFor(() => document.querySelector('.mz-ctx--table'), 'table-bound Register');
            assert(phase() === 'menu', 'a table-bound Register ignores ?view= (order context wins)');
            ok();
        """), login='admin')
