"""R2A CP9 — Orders workspace: Park & Recall + safe order lookup.

Proves the cashier can leave an order, find another legitimately, and reopen it
safely — reusing pos.order as the single source of truth (no second order engine):

  * PARK        — tags a still-DRAFT order (never pays/cancels/unlinks; table stays occupied)
  * RECALL      — /orders/get returns the SAME order (uuid, lines, table, paid/remaining)
  * PARTIAL     — recall preserves paid + remaining; no duplicate payment
  * COMPLETED   — read-only: cannot be parked/resurrected into an editable draft
  * MOVED (CP7) — recall reflects the destination table, never the stale source
  * SCOPE       — a branch's token cannot read/list another branch's orders (by uuid OR id)

The server stays authoritative throughout; the workspace only mirrors it.
"""
import json
import re

from odoo.tests import tagged

from .common import MezzeHttpCase

_BOOT_RE = re.compile(r'<script[^>]*id="mezze-boot"[^>]*>(.*?)</script>', re.DOTALL)


def _js_body(body):
    return "(async () => {\n" + body + "\n})().catch(e => console.error(e.message || e));"


@tagged('post_install', '-at_install', 'mezze_floor')
class TestOrdersWorkspace(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product.write({'available_in_pos': True, 'list_price': 42.0, 'taxes_id': [(5, 0, 0)]})
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        sess = cls.pos_config.current_session_id
        if not sess or sess.state not in ('opened', 'opening_control'):
            sess = cls.env['pos.session'].create(
                {'config_id': cls.pos_config.id, 'user_id': cls.env.uid})
        if sess.state == 'opening_control':
            try:
                sess.set_opening_control(0, None)
            except Exception:  # noqa: BLE001
                pass
        cls.table = cls.tables[0]

    # -- helpers -----------------------------------------------------------
    def _boot(self, url):
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

    def _draft(self, token, uuid, qty=2, table=None):
        body = {'uuid': uuid, 'session_id': self.pos_config.current_session_id.id,
                'draft': True, 'lines': [{'product_id': self.product.id, 'qty': qty}]}
        if table is not None:
            body['table_id'] = table.id
        self._api('/orders/sync', body, token)
        return self.env['pos.order'].search([('uuid', '=', uuid)], limit=1)

    def _floor_status(self, token, table_id):
        r = self._api('/floors', {'config_id': self.pos_config.id}, token)
        for fl in r.json().get('floors', []):
            for t in fl.get('tables', []):
                if t.get('id') == table_id:
                    return t.get('status')
        return None

    # -- CP9 tests ---------------------------------------------------------
    def test_24_park_draft_order_preserves_identity(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        o = self._draft(token, 'cp9-park', qty=2, table=self.table)
        total_before, lines_before = o.amount_total, len(o.lines)
        self.assertEqual(self._floor_status(token, self.table.id), 'occupied')
        r = self._api('/orders/park', {'uuid': 'cp9-park', 'parked': True}, token)
        self.assertTrue(r.json().get('ok') and r.json().get('parked'), r.text)
        o.invalidate_recordset()
        self.assertEqual(o.state, 'draft', 'parking never leaves draft')
        self.assertTrue(o.mezze_parked, 'order tagged parked')
        self.assertEqual(o.amount_total, total_before, 'total preserved')
        self.assertEqual(len(o.lines), lines_before, 'lines preserved')
        self.assertEqual(len(self.env['pos.order'].search([('uuid', '=', 'cp9-park')])), 1, 'no duplicate')
        self.assertEqual(self._floor_status(token, self.table.id), 'occupied',
                         'a parked table order still holds its table')

    def test_25_recall_parked_order_same_uuid(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        o = self._draft(token, 'cp9-recall', qty=3)
        self._api('/orders/park', {'uuid': 'cp9-recall', 'parked': True}, token)
        # it appears under Parked, not Open
        parked = self._api('/orders/list', {'filter': 'parked'}, token).json().get('orders', [])
        self.assertIn('cp9-recall', [x['uuid'] for x in parked], 'parked order listed under Parked')
        opened = self._api('/orders/list', {'filter': 'open'}, token).json().get('orders', [])
        self.assertNotIn('cp9-recall', [x['uuid'] for x in opened], 'parked order not under Open')
        # recall = fetch the SAME order (no copy/duplicate)
        res = self._api('/orders/get', {'uuid': 'cp9-recall'}, token).json()
        self.assertTrue(res.get('ok'))
        self.assertEqual(res['uuid'], o.uuid)
        self.assertEqual(res['order_id'], o.id)
        self.assertEqual(sum(l['qty'] for l in res['lines']), 3, 'lines restored')
        self.assertEqual(len(self.env['pos.order'].search([('uuid', '=', 'cp9-recall')])), 1, 'no duplicate')

    def test_26_recall_table_order_restores_table_context(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        self._draft(token, 'cp9-tbl', qty=1, table=self.tables[1])
        self._api('/orders/set_guests', {'uuid': 'cp9-tbl', 'guests': 4, 'config_id': self.pos_config.id}, token)
        res = self._api('/orders/get', {'uuid': 'cp9-tbl'}, token).json()
        self.assertEqual(res['table_id'], self.tables[1].id, 'table id restored')
        self.assertEqual(res['table'], str(self.tables[1].table_number), 'table number for the chip')
        self.assertEqual(res['floor'], self.tables[1].floor_id.name, 'floor restored')
        self.assertEqual(res['guests'], 4, 'guest count restored')
        self.assertEqual(res['order_type'], 'dine_in')

    def test_27_partial_paid_recall_preserves_balance(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        o = self._draft(token, 'cp9-partial', qty=2, table=self.table)   # total 84
        total = round(o.amount_total, 2)
        pay = self._api('/orders/pay', {'uuid': 'cp9-partial', 'amount': 50.0,
                                        'tender_key': 'cp9-partial-t1'}, token).json()
        self.assertTrue(pay.get('partial'), pay)
        res = self._api('/orders/get', {'uuid': 'cp9-partial'}, token).json()
        self.assertEqual(res['state'], 'draft', 'still open')
        self.assertAlmostEqual(res['amount_total'], total, places=2)
        self.assertAlmostEqual(res['amount_paid'], 50.0, places=2)
        self.assertAlmostEqual(res['remaining'], round(total - 50.0, 2), places=2)
        self.assertEqual(self._floor_status(token, self.table.id), 'occupied')
        o.invalidate_recordset()
        self.assertEqual(len(o.payment_ids), 1, 'recall creates no duplicate payment')

    def test_28_completed_order_is_read_only(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        self._draft(token, 'cp9-done', qty=1)
        self._api('/orders/pay', {'uuid': 'cp9-done', 'tender_key': 'cp9-done-t1'}, token)  # full
        res = self._api('/orders/get', {'uuid': 'cp9-done'}, token).json()
        self.assertIn(res['state'], ('paid', 'done', 'invoiced'), 'completed state surfaced')
        # a completed order can never be tagged parked (no resurrection into a draft)
        r = self._api('/orders/park', {'uuid': 'cp9-done', 'parked': True}, token)
        self.assertEqual(r.json().get('error'), 'order_not_draft', 'completed order cannot be parked')
        # it appears under Completed, never Open/Parked
        completed = self._api('/orders/list', {'filter': 'completed'}, token).json().get('orders', [])
        self.assertIn('cp9-done', [x['uuid'] for x in completed])
        opened = self._api('/orders/list', {'filter': 'open'}, token).json().get('orders', [])
        self.assertNotIn('cp9-done', [x['uuid'] for x in opened])

    def test_29_stale_completed_order_cannot_resurrect(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        self._draft(token, 'cp9-stale', qty=1)  # a draft the list once saw as open
        # completed on "another terminal" (server truth changes underneath)
        self._api('/orders/pay', {'uuid': 'cp9-stale', 'tender_key': 'cp9-stale-t1'}, token)
        # the stale recall now resolves to a completed/read-only order, never a new draft
        res = self._api('/orders/get', {'uuid': 'cp9-stale'}, token).json()
        self.assertNotEqual(res['state'], 'draft', 'server truth wins: not editable')
        # re-syncing the same uuid does not spawn a second order
        dup = self._api('/orders/sync', {
            'uuid': 'cp9-stale', 'session_id': self.pos_config.current_session_id.id,
            'draft': True, 'lines': [{'product_id': self.product.id, 'qty': 5}]}, token).json()
        self.assertTrue(dup.get('duplicate'), 'idempotent — no resurrected draft')
        self.assertEqual(len(self.env['pos.order'].search([('uuid', '=', 'cp9-stale')])), 1)

    def test_30_moved_order_recalls_new_table(self):
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        src, dst = self.tables[0], self.tables[1]
        o = self._draft(token, 'cp9-moved', qty=2, table=src)
        r = self._api('/tables/transfer', {
            'session_id': self.pos_config.current_session_id.id,
            'from_table_id': src.id, 'to_table_id': dst.id, 'order_uuid': o.uuid}, token)
        self.assertTrue(r.json().get('ok'), r.text)
        res = self._api('/orders/get', {'uuid': 'cp9-moved'}, token).json()
        self.assertEqual(res['table_id'], dst.id, 'recall reflects the destination table')
        self.assertNotEqual(res['table_id'], src.id, 'never the stale source')

    def test_31_scoped_order_lookup_no_cross_branch_leak(self):
        # an order on ANOTHER branch (config) must be invisible/inaccessible to this
        # branch's terminal token — by uuid AND by guessable integer id.
        self.authenticate('admin', 'admin')
        token = self._boot('/mezze/pos')['token']
        other = self.make_second_pos_config()
        osess = self.env['pos.session'].create({'config_id': other.id, 'user_id': self.env.uid})
        if osess.state == 'opening_control':
            try:
                osess.set_opening_control(0, None)
            except Exception:  # noqa: BLE001
                pass
        foreign = self.env['pos.order'].sudo().create({
            'session_id': osess.id, 'config_id': other.id, 'company_id': other.company_id.id,
            'state': 'draft', 'amount_total': 99.0, 'amount_tax': 0.0, 'amount_paid': 0.0,
            'amount_return': 0.0, 'uuid': 'cp9-foreign',
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1, 'price_unit': 99.0,
                              'price_subtotal': 99.0, 'price_subtotal_incl': 99.0})]})
        # by uuid — denied (not this branch)
        by_uuid = self._api('/orders/get', {'uuid': 'cp9-foreign'}, token).json()
        self.assertFalse(by_uuid.get('ok'), 'cross-branch fetch by uuid refused')
        # by guessable integer id — denied
        by_id = self._api('/orders/get', {'order_id': foreign.id}, token).json()
        self.assertFalse(by_id.get('ok'), 'cross-branch fetch by id refused')
        # never surfaced in any list tab
        for filt in ('open', 'parked', 'completed', 'all'):
            rows = self._api('/orders/list', {'filter': filt}, token).json().get('orders', [])
            self.assertNotIn('cp9-foreign', [x['uuid'] for x in rows],
                             'cross-branch order absent from %s list' % filt)

    # -- browser proof (headless): park -> Orders -> recall round trip -----
    def test_32_park_and_recall_round_trip_ui(self):
        self.authenticate('admin', 'admin')
        prelude = (
            "const $=s=>document.querySelector(s);const $$=s=>[...document.querySelectorAll(s)];"
            "const phase=()=>($('.mz-app')?$('.mz-app').dataset.phase:null);"
            "async function waitFor(f,l,ms=15000){const t0=Date.now();"
            "while(Date.now()-t0<ms){try{if(f())return true;}catch(e){}"
            "await new Promise(r=>setTimeout(r,100));}throw new Error('timeout: '+l+' (phase='+phase()+')');}"
            "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
            "const ok=()=>console.log('test successful');")
        self.browser_js('/mezze/pos', prelude + _js_body(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            // build a counter order and PARK it
            $('.mz-tile:not(.mz-tile--out)').click();
            await waitFor(() => $('.mz-line'), 'line added');
            const park = $$('.mz-cart-foot .mz-btn').find(b => /park order/i.test(b.textContent));
            assert(park, 'Park order button present'); park.click();
            await waitFor(() => !$('.mz-line'), 'register cleared after park');
            // open Orders workspace
            const ordersNav = $$('.mz-nav__item').find(b => /orders/i.test(b.textContent));
            assert(ordersNav, 'Orders nav'); ordersNav.click();
            await waitFor(() => phase() === 'orders', 'orders phase');
            // Parked tab shows the parked order; recall it
            const parkedTab = $$('.mz-tab').find(b => /parked/i.test(b.textContent));
            assert(parkedTab, 'Parked tab'); parkedTab.click();
            await waitFor(() => $('.mz-ordcard'), 'a parked order card');
            $('.mz-ordcard').click();
            // recalled into the editable register with its line restored
            await waitFor(() => phase() === 'menu', 'back to register');
            await waitFor(() => $('.mz-line'), 'recalled order line restored');
            ok();
        """), login='admin')
