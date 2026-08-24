# -*- coding: utf-8 -*-
"""Which batch actually went out.

Mezze wrote ``'pack_lot_ids': []`` on every path that built an order line, so a
tracked product left the branch with no record of the lot or serial it came from.

For food that is the entire point of tracking one. An allergen or contamination
recall has to answer "which orders received lot X" — and an empty list cannot answer
it at all. The information exists at the moment of sale and nowhere afterwards, so
not capturing it is not a gap that can be filled in later.

Two rules, both taken from what tracking MEANS rather than from what is convenient:

* a SERIAL identifies one physical item, so the count must equal the quantity. Three
  bottles cannot leave under two serials; allowing it makes the trail quietly wrong,
  which is worse than obviously incomplete.
* an UNTRACKED product records nothing, whatever the browser sends. Inventing a lot
  for something the branch does not track puts fiction into the audit trail.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_lots')
class TestLotSerial(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'lt-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)

        def dish(name, tracking):
            p = env['product.product'].sudo().create({
                'name': name, 'available_in_pos': True, 'list_price': 20.0,
                'type': 'consu', 'is_storable': True, 'tracking': tracking})
            p.write({'taxes_id': [(5, 0, 0)]})
            return p

        cls.by_lot = dish('LT Batch Cheese', 'lot')
        cls.by_serial = dish('LT Numbered Bottle', 'serial')
        cls.plain = dish('LT Plain Bread', 'none')
        env.flush_all()

    def _sync(self, uuid, product, qty=1, lots=None):
        line = {'product_id': product.id, 'qty': qty}
        if lots is not None:
            line['lot_names'] = lots
        r = self.url_open('/mezze/api/v1/orders/sync',
                          data=json.dumps({'uuid': uuid, 'session_id': self.pos_sess.id,
                                           'draft': True, 'lines': [line],
                                           'token': 'lt-tok'}),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _lots(self, uuid):
        self.env.invalidate_all()
        order = self.env['pos.order'].sudo().search([('uuid', '=', uuid)], limit=1)
        return order.lines.mapped('pack_lot_ids.lot_name')

    # -- it is recorded at all --------------------------------------------
    def test_01_a_lot_number_reaches_the_order(self):
        d = self._sync('lt-1', self.by_lot, 2, ['BATCH-2026-08'])
        self.assertTrue(d.get('ok'), d)
        self.assertEqual(self._lots('lt-1'), ['BATCH-2026-08'],
                         'the batch that went out was not recorded')

    def test_02_several_lots_on_one_line(self):
        # A kilo drawn from two batches is two lots on the line.
        self._sync('lt-2', self.by_lot, 2, ['BATCH-A', 'BATCH-B'])
        self.assertEqual(sorted(self._lots('lt-2')), ['BATCH-A', 'BATCH-B'])

    def test_03_serials_are_recorded_one_per_item(self):
        self._sync('lt-3', self.by_serial, 3, ['S-1', 'S-2', 'S-3'])
        self.assertEqual(sorted(self._lots('lt-3')), ['S-1', 'S-2', 'S-3'])

    # -- and it is recorded HONESTLY ---------------------------------------
    def test_10_a_serial_count_must_match_the_quantity(self):
        # THE rule. Three bottles under two serials is a trail that is quietly wrong.
        d = self._sync('lt-4', self.by_serial, 3, ['S-1', 'S-2'])
        self.assertFalse(d.get('ok'), 'three items left under two serials: %s' % d)
        self.assertEqual(self._lots('lt-4'), [])

    def test_11_a_repeated_serial_is_refused(self):
        # Two items cannot claim one identity.
        d = self._sync('lt-5', self.by_serial, 2, ['S-9', 'S-9'])
        self.assertFalse(d.get('ok'), 'two items shared one serial: %s' % d)

    def test_12_a_repeated_lot_is_merged_not_refused(self):
        # Unlike a serial, the same lot typed twice is simply the same lot.
        self._sync('lt-6', self.by_lot, 2, ['BATCH-A', 'BATCH-A'])
        self.assertEqual(self._lots('lt-6'), ['BATCH-A'])

    def test_13_an_untracked_product_records_nothing(self):
        # Whatever the browser sends. Fiction in an audit trail is worse than silence.
        d = self._sync('lt-7', self.plain, 1, ['MADE-UP'])
        self.assertTrue(d.get('ok'), d)
        self.assertEqual(self._lots('lt-7'), [])

    def test_14_a_tracked_product_without_numbers_still_sells(self):
        # Refusing the sale would stop the till over a record the cashier may not
        # have. The gap is visible in the trail, which is the honest outcome.
        d = self._sync('lt-8', self.by_lot, 1)
        self.assertTrue(d.get('ok'), d)
        self.assertEqual(self._lots('lt-8'), [])

    def test_15_blank_entries_are_ignored(self):
        self._sync('lt-9', self.by_lot, 1, ['', '   ', 'REAL-LOT'])
        self.assertEqual(self._lots('lt-9'), ['REAL-LOT'])


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_lots')
class TestLotEntryOnTill(MezzeHttpCase):
    """The cashier can actually record the batch.

    The server has stored lots since the traceability work, and until now nothing on
    the till could collect one — so in practice every sale still went out unrecorded.
    A capability the product cannot reach is a capability it does not have, which is
    the single most repeated finding in this whole comparison.
    """
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.categ = env['pos.category'].sudo().search([], limit=1) \
            or env['pos.category'].sudo().create({'name': 'LT'})
        cls.tracked = env['product.product'].sudo().create({
            'name': 'LT Tracked Cheese', 'available_in_pos': True, 'list_price': 30.0,
            'type': 'consu', 'is_storable': True, 'tracking': 'lot',
            'pos_categ_ids': [(6, 0, cls.categ.ids)]})
        cls.untracked = env['product.product'].sudo().create({
            'name': 'LT Untracked Bread', 'available_in_pos': True, 'list_price': 10.0,
            'type': 'consu', 'pos_categ_ids': [(6, 0, cls.categ.ids)]})
        (cls.tracked | cls.untracked).write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    _JS = r"""
    const $ = (s) => document.querySelector(s);
    const $$ = (s) => Array.from(document.querySelectorAll(s));
    async function waitFor(fn, label, ms=20000){
      const t0 = Date.now();
      while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){}
        await new Promise(r=>setTimeout(r,120)); }
      throw new Error('timeout waiting for: ' + label);
    }
    function assert(c,m){ if(!c) throw new Error('assert failed: ' + m); }
    const tile = (n) => $$('.mz-tile').find(t => new RegExp(n).test(t.textContent));
    const lineOf = (n) => $$('.mz-line').find(l => new RegExp(n).test(l.textContent));
    """

    def test_20_a_tracked_line_offers_batch_entry(self):
        self.browser_js('/mezze/pos?ws=register', self._JS + r"""
            (async () => {
                await waitFor(() => tile('LT Tracked Cheese'), 'the menu');
                tile('LT Tracked Cheese').click();
                await waitFor(() => lineOf('LT Tracked Cheese'), 'the line');
                assert(lineOf('LT Tracked Cheese')
                        .querySelector('[data-testid="mz-line-lot"]'),
                       'a tracked product offers no way to record its batch');
                console.log('test successful');
            })().catch(e => { console.error(e.message || e); });
        """, login='admin')

    def test_21_an_untracked_line_does_not(self):
        # A lot on something the branch does not track is fiction in the trail.
        self.browser_js('/mezze/pos?ws=register', self._JS + r"""
            (async () => {
                await waitFor(() => tile('LT Untracked Bread'), 'the menu');
                tile('LT Untracked Bread').click();
                await waitFor(() => lineOf('LT Untracked Bread'), 'the line');
                assert(!lineOf('LT Untracked Bread')
                        .querySelector('[data-testid="mz-line-lot"]'),
                       'an untracked product was asked for a batch number');
                console.log('test successful');
            })().catch(e => { console.error(e.message || e); });
        """, login='admin')

    def test_22_a_typed_batch_reaches_the_server(self):
        self.browser_js('/mezze/pos?ws=register', self._JS + r"""
            (async () => {
                await waitFor(() => tile('LT Tracked Cheese'), 'the menu');
                tile('LT Tracked Cheese').click();
                await waitFor(() => lineOf('LT Tracked Cheese'), 'the line');
                lineOf('LT Tracked Cheese')
                    .querySelector('[data-testid="mz-line-lot"]').click();
                await waitFor(() => $('[data-testid="mz-lots-input"]'), 'the dialog');
                const box = $('[data-testid="mz-lots-input"]');
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value').set;
                setter.call(box, 'BATCH-BROWSER-1');
                box.dispatchEvent(new Event('input', {bubbles:true}));
                await new Promise(r => setTimeout(r, 120));
                $('[data-testid="mz-lots-apply"]').click();
                await waitFor(() => !$('[data-testid="mz-lots-input"]'), 'the dialog to close');
                // persist through a flow that syncs
                $$('.mz-verb').find(v => /Enter Code/.test(v.textContent)).click();
                await waitFor(() => $('[data-testid="mz-code-input"]'), 'persisted');
                console.log('test successful');
            })().catch(e => { console.error(e.message || e); });
        """, login='admin')
        self.env.invalidate_all()
        order = self.env['pos.order'].sudo().search(
            [('session_id', '=', self.pos_sess.id)], order='id desc', limit=1)
        self.assertTrue(order, 'no order was persisted')
        self.assertIn('BATCH-BROWSER-1', order.lines.mapped('pack_lot_ids.lot_name'),
                      'the typed batch never reached the server')
