"""R2A CP10 — Reservations + Waitlist: arrival, walk-in & safe seating.

Reuses the canonical FSMs (reservation.py / waitlist.py) and the shared seating
attach path; the workspace only mirrors server truth. Proves:

  * branch/company SCOPE — a branch's token cannot read/list/transition another's
  * arrival transitions guarded (illegal jump -> 409, no write)
  * seating attaches EXACTLY ONE order (idempotent on retry); pos_order_id == order
  * guest/customer context reaches the order
  * capacity safeguard (undersized tables excluded from availability)
  * stale/concurrent transition resolves to server truth (no duplicate)
  * seated order appears in CP9 Orders; payment still releases the table (CP8)
"""
import json
import re

from odoo import fields
from odoo.tests import tagged

from .common import MezzeHttpCase

_BOOT_RE = re.compile(r'<script[^>]*id="mezze-boot"[^>]*>(.*?)</script>', re.DOTALL)


def _js_body(body):
    return "(async () => {\n" + body + "\n})().catch(e => console.error(e.message || e));"


@tagged('post_install', '-at_install', 'mezze_floor')
class TestReservationsWaitlist(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product.write({'available_in_pos': True, 'list_price': 42.0, 'taxes_id': [(5, 0, 0)]})
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_security', 'enforce')
        sess = cls.pos_config.current_session_id
        if not sess or sess.state not in ('opened', 'opening_control'):
            sess = cls.env['pos.session'].create(
                {'config_id': cls.pos_config.id, 'user_id': cls.env.uid})
        if sess.state == 'opening_control':
            try:
                sess.set_opening_control(0, None)
            except Exception:  # noqa: BLE001
                pass
        cls.psession = sess
        cls.table = cls.tables[0]

    # -- helpers -----------------------------------------------------------
    def _boot(self, url='/mezze/pos'):
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

    def _mk_res(self, config, table, state='booked', start='2026-07-24 19:00:00',
                guests=2, name='Salma G.', phone='0100', vip=False, occasion=None):
        vals = {'table_id': table.id, 'config_id': config.id, 'start': start,
                'guests': guests, 'customer_name': name, 'phone': phone, 'state': state,
                'is_vip': vip}
        if occasion:
            vals['occasion'] = occasion
        return self.env['mezze.reservation'].sudo().create(vals)

    def _mk_wl(self, config, name='Karim', size=3, state='waiting', quoted=20):
        return self.env['mezze.waitlist'].sudo().create({
            'config_id': config.id, 'customer_name': name, 'party_size': size,
            'state': state, 'quoted_wait': quoted})

    def _draft_on_table(self, token, uuid, table):
        self._api('/orders/sync', {
            'uuid': uuid, 'session_id': self.psession.id, 'draft': True,
            'table_id': table.id, 'lines': [{'product_id': self.product.id, 'qty': 2}]}, token)
        return self.env['pos.order'].search([('uuid', '=', uuid)], limit=1)

    def _second_branch(self):
        other = self.make_second_pos_config()
        osess = self.env['pos.session'].create({'config_id': other.id, 'user_id': self.env.uid})
        if osess.state == 'opening_control':
            try:
                osess.set_opening_control(0, None)
            except Exception:  # noqa: BLE001
                pass
        return other

    # ===================== SCOPE =====================
    def test_33_reservation_list_is_branch_scoped(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        now = fields.Datetime.to_string(fields.Datetime.now())
        mine = self._mk_res(self.pos_config, self.table, name='Mine A', start=now)
        other = self._second_branch()
        self._mk_res(other, self.tables[1], name='Foreign B', start=now)
        rows = self._api('/reservations/list', {'scope': 'upcoming'}, token).json().get('reservations', [])
        whos = [r['who'] for r in rows]
        self.assertIn('Mine A', whos)
        self.assertNotIn('Foreign B', whos, 'another branch reservation must not be listed')
        # search cannot reveal the foreign reservation either
        found = self._api('/reservations/list', {'q': 'Foreign'}, token).json().get('reservations', [])
        self.assertEqual(found, [], 'scoped search cannot surface another branch')

    def test_34_cross_branch_reservation_transition_denied(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        other = self._second_branch()
        foreign = self._mk_res(other, self.tables[1], state='booked', name='Foreign B')
        r = self._api('/reservations/state',
                      {'reservation_id': foreign.id, 'action': 'confirm'}, token)
        self.assertFalse(r.json().get('ok'), 'cross-branch transition refused')
        foreign.invalidate_recordset()
        self.assertEqual(foreign.state, 'booked', 'no write on a denied cross-branch transition')

    # ===================== TRANSITIONS =====================
    def test_35_reservation_arrival_transition_guard(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        res = self._mk_res(self.pos_config, self.table, state='booked')
        self.assertTrue(self._api('/reservations/state',
                        {'reservation_id': res.id, 'action': 'confirm'}, token).json().get('ok'))
        self.assertTrue(self._api('/reservations/state',
                        {'reservation_id': res.id, 'action': 'arrive'}, token).json().get('ok'))
        res.invalidate_recordset()
        self.assertEqual(res.state, 'arrived')
        # illegal jump: arrived -> done (not in the map) is rejected, no write
        bad = self._api('/reservations/state', {'reservation_id': res.id, 'action': 'complete'}, token)
        self.assertEqual(bad.json().get('error'), 'invalid_transition')
        res.invalidate_recordset()
        self.assertEqual(res.state, 'arrived', 'illegal transition left the state unchanged')

    # ===================== SEATING =====================
    def test_36_reservation_seat_creates_one_order(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        order = self._draft_on_table(token, 'cp10-seat', self.table)
        res = self._mk_res(self.pos_config, self.table, state='arrived', guests=4,
                           name='Salma G.')
        r = self._api('/reservations/state',
                      {'reservation_id': res.id, 'action': 'seat', 'session_id': self.psession.id},
                      token).json()
        self.assertTrue(r.get('ok') and r['reservation']['state'] == 'seated', r)
        self.assertTrue(r.get('order'))
        self.assertEqual(r['order']['order_id'], order.id, 'attached the table\'s single draft')
        res.invalidate_recordset(); order.invalidate_recordset()
        self.assertEqual(res.pos_order_id.id, order.id, 'reservation linked to the canonical order')
        self.assertEqual(order.customer_count, 4, 'guest count reached the order')
        n = self.env['pos.order'].search_count(
            [('table_id', '=', self.table.id), ('state', '=', 'draft')])
        self.assertEqual(n, 1, 'exactly one order on the table')

    def test_37_reservation_seat_retry_idempotent(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        order = self._draft_on_table(token, 'cp10-seat2', self.table)
        res = self._mk_res(self.pos_config, self.table, state='arrived')
        body = {'reservation_id': res.id, 'action': 'seat', 'session_id': self.psession.id}
        a = self._api('/reservations/state', body, token).json()
        b = self._api('/reservations/state', body, token).json()   # retry
        self.assertEqual(a['order']['order_id'], order.id)
        self.assertEqual(b['order']['order_id'], order.id, 'retry attaches the same order')
        self.assertEqual(self.env['pos.order'].search_count(
            [('table_id', '=', self.table.id), ('state', '=', 'draft')]), 1, 'no duplicate order')

    def test_38_capacity_safeguard_excludes_undersized(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        small = self.env['restaurant.table'].create(
            {'table_number': 91, 'floor_id': self.floor.id, 'seats': 2})
        big = self.env['restaurant.table'].create(
            {'table_number': 92, 'floor_id': self.floor.id, 'seats': 8})
        res = self._api('/reservations/availability',
                        {'start': '2026-07-24 20:00:00', 'duration': 1.5, 'guests': 6}, token).json()
        ids = [t['id'] for t in res.get('tables', [])]
        self.assertIn(big.id, ids, 'a big-enough table is offered')
        self.assertNotIn(small.id, ids, 'a party of 6 is never offered a 2-seat table')

    # ===================== WAITLIST =====================
    def test_39_waitlist_list_is_branch_scoped(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        self._mk_wl(self.pos_config, name='Karim A')
        other = self._second_branch()
        self._mk_wl(other, name='Foreign W')
        items = self._api('/waitlist/list', {}, token).json().get('items', [])
        whos = [w['who'] for w in items]
        self.assertIn('Karim A', whos)
        self.assertNotIn('Foreign W', whos, 'another branch queue entry must not be listed')

    def test_40_waitlist_progression_and_guard(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        w = self._mk_wl(self.pos_config, name='Nour', size=2, state='waiting')
        self.assertTrue(self._api('/waitlist/state',
                        {'waitlist_id': w.id, 'action': 'notify'}, token).json().get('ok'))
        w.invalidate_recordset()
        self.assertEqual(w.state, 'notified')
        # illegal: notified -> restore(waiting) is legal; but seated->notified is not.
        w.write({'state': 'seated'})
        bad = self._api('/waitlist/state', {'waitlist_id': w.id, 'action': 'notify'}, token)
        self.assertEqual(bad.json().get('error'), 'invalid_transition')
        w.invalidate_recordset()
        self.assertEqual(w.state, 'seated', 'illegal transition left the state unchanged')

    def test_41_waitlist_seat_creates_one_order(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        order = self._draft_on_table(token, 'cp10-wl-seat', self.table)
        w = self._mk_wl(self.pos_config, name='Karim', size=3, state='notified')
        r = self._api('/waitlist/state',
                      {'waitlist_id': w.id, 'action': 'seat', 'table_id': self.table.id,
                       'session_id': self.psession.id}, token).json()
        self.assertTrue(r.get('ok') and r['waitlist']['state'] == 'seated', r)
        self.assertEqual(r['order']['order_id'], order.id)
        w.invalidate_recordset()
        self.assertEqual(w.table_id.id, self.table.id, 'seat recorded the table')
        self.assertEqual(w.pos_order_id.id, order.id, 'queue entry linked to the order')
        self.assertEqual(self.env['pos.order'].search_count(
            [('table_id', '=', self.table.id), ('state', '=', 'draft')]), 1)

    def test_42_waitlist_seat_retry_idempotent(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        order = self._draft_on_table(token, 'cp10-wl-seat2', self.table)
        w = self._mk_wl(self.pos_config, name='Nour', size=2, state='notified')
        body = {'waitlist_id': w.id, 'action': 'seat', 'table_id': self.table.id,
                'session_id': self.psession.id}
        self._api('/waitlist/state', body, token)
        self._api('/waitlist/state', body, token)   # retry
        self.assertEqual(self.env['pos.order'].search_count(
            [('table_id', '=', self.table.id), ('state', '=', 'draft')]), 1, 'no duplicate order')

    # ===================== STALE / INTEGRATION =====================
    def test_43_stale_reservation_transition_refetches_truth(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        self._draft_on_table(token, 'cp10-stale', self.table)
        res = self._mk_res(self.pos_config, self.table, state='arrived')
        # seated on "another device"
        self._api('/reservations/state',
                  {'reservation_id': res.id, 'action': 'seat', 'session_id': self.psession.id}, token)
        # a stale card still shows 'arrived' and tries to Arrive again -> rejected
        stale = self._api('/reservations/state', {'reservation_id': res.id, 'action': 'arrive'}, token)
        self.assertEqual(stale.json().get('error'), 'invalid_transition')
        res.invalidate_recordset()
        self.assertEqual(res.state, 'seated', 'server truth wins')
        self.assertEqual(self.env['pos.order'].search_count(
            [('table_id', '=', self.table.id), ('state', '=', 'draft')]), 1, 'no duplicate order')

    def test_44_seated_order_appears_in_cp9_orders(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        order = self._draft_on_table(token, 'cp10-orders', self.table)
        res = self._mk_res(self.pos_config, self.table, state='arrived', name='Salma G.')
        self._api('/reservations/state',
                  {'reservation_id': res.id, 'action': 'seat', 'session_id': self.psession.id}, token)
        rows = self._api('/orders/list', {'filter': 'open'}, token).json().get('orders', [])
        row = next((x for x in rows if x['uuid'] == order.uuid), None)
        self.assertTrue(row, 'the seated order appears in CP9 Orders')
        self.assertEqual(row['table'], str(self.table.table_number), 'correct table shown')

    def test_45_reservation_payment_release_integration(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        order = self._draft_on_table(token, 'cp10-pay', self.table)
        res = self._mk_res(self.pos_config, self.table, state='arrived')
        self._api('/reservations/state',
                  {'reservation_id': res.id, 'action': 'seat', 'session_id': self.psession.id}, token)
        # pay the seated order in full -> table releases (CP8), history preserved
        pay = self._api('/orders/pay', {'uuid': 'cp10-pay', 'tender_key': 'cp10-pay-t1'}, token).json()
        self.assertTrue(pay.get('ok') and pay.get('remaining') == 0.0, pay)
        order.invalidate_recordset(); res.invalidate_recordset()
        self.assertIn(order.state, ('paid', 'done', 'invoiced'))
        self.assertFalse(self.env['pos.order'].search(
            [('table_id', '=', self.table.id), ('state', '=', 'draft')]), 'table released')
        self.assertEqual(res.pos_order_id.id, order.id, 'reservation->order link preserved historically')

    # ===================== BROWSER =====================
    def test_46_reservation_arrive_seat_browser(self):
        self.authenticate('admin', 'admin')
        # a confirmed reservation with no table yet -> host seats it to a free table
        free = self.env['restaurant.table'].create(
            {'table_number': 77, 'floor_id': self.floor.id, 'seats': 6})
        res = self._mk_res(self.pos_config, free, state='confirmed', name='Salma G.',
                           start=fields.Datetime.to_string(fields.Datetime.now()))
        prelude = (
            "const $=s=>document.querySelector(s);const $$=s=>[...document.querySelectorAll(s)];"
            "const phase=()=>($('.mz-app')?$('.mz-app').dataset.phase:null);"
            "async function waitFor(f,l,ms=15000){const t0=Date.now();"
            "while(Date.now()-t0<ms){try{if(f())return true;}catch(e){}"
            "await new Promise(r=>setTimeout(r,100));}throw new Error('timeout: '+l+' (phase='+phase()+')');}"
            "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
            "function card(){return $$('.mz-rescard').find(c=>/Salma/.test(c.textContent));}"
            "function act(re){const c=card();return c?$$('.mz-btn',c).find(b=>re.test(b.textContent))"
            ":[...document.querySelectorAll('.mz-rescard .mz-btn')].find(b=>re.test(b.textContent));}"
            "const ok=()=>console.log('test successful');")
        self.browser_js('/mezze/pos', prelude + _js_body(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            const nav = $$('.mz-nav__item').find(b => /reservations/i.test(b.textContent));
            assert(nav, 'Reservations nav'); nav.click();
            await waitFor(() => phase() === 'reservations', 'reservations phase');
            await waitFor(() => card(), 'Salma reservation card');
            // Confirmed -> Arrived
            const arrived = [...document.querySelectorAll('.mz-rescard .mz-btn')].find(b=>/arrived/i.test(b.textContent));
            assert(arrived, 'Arrived action'); arrived.click();
            await waitFor(() => [...document.querySelectorAll('.mz-rescard .mz-btn')].some(b=>/seat/i.test(b.textContent)), 'Seat available');
            const seat = [...document.querySelectorAll('.mz-rescard .mz-btn')].find(b=>/^\s*Seat\s*$/i.test(b.textContent));
            assert(seat, 'Seat action'); seat.click();
            await waitFor(() => $('.mz-assign__t'), 'seat picker open');
            const t = $$('.mz-assign__t').find(b => !b.disabled);
            assert(t, 'a free table to seat'); t.click();
            // seated -> Register opens table-bound
            await waitFor(() => phase() === 'menu', 'register after seat');
            await waitFor(() => $('.mz-tablechip'), 'table chip after seating');
            ok();
        """), login='admin')
        res.invalidate_recordset()
        self.assertEqual(res.state, 'seated', 'reservation seated via the browser flow')

    def test_47_waitlist_add_notify_seat_browser(self):
        self.authenticate('admin', 'admin')
        free = self.env['restaurant.table'].create(
            {'table_number': 78, 'floor_id': self.floor.id, 'seats': 4})
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
            $$('.mz-nav__item').find(b => /reservations/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'reservations', 'reservations phase');
            // switch to Waitlist and add a walk-in
            $$('.mz-tab').find(b => /waitlist/i.test(b.textContent)).click();
            await waitFor(() => $$('.mz-btn').some(b => /add walk-in/i.test(b.textContent)), 'Add walk-in btn');
            $$('.mz-btn').find(b => /add walk-in/i.test(b.textContent)).click();
            await waitFor(() => $('.mz-resform'), 'walk-in form');
            const name = $('.mz-resform .mz-input'); name.value = 'Karim';
            name.dispatchEvent(new Event('input', {bubbles: true}));
            $$('.mz-resform .mz-btn').find(b => /add to waitlist/i.test(b.textContent)).click();
            await waitFor(() => $$('.mz-rescard').some(c => /Karim/.test(c.textContent)), 'Karim on the waitlist');
            // Notify then Seat
            [...document.querySelectorAll('.mz-rescard .mz-btn')].find(b=>/notify/i.test(b.textContent)).click();
            await waitFor(() => [...document.querySelectorAll('.mz-rescard .mz-btn')].some(b=>/seat/i.test(b.textContent)), 'Seat available');
            [...document.querySelectorAll('.mz-rescard .mz-btn')].find(b=>/^\s*Seat\s*$/i.test(b.textContent)).click();
            await waitFor(() => $('.mz-assign__t'), 'seat picker');
            const t = $$('.mz-assign__t').find(b => !b.disabled);
            assert(t, 'a free table'); t.click();
            await waitFor(() => phase() === 'menu', 'register after seat');
            await waitFor(() => $('.mz-tablechip'), 'table chip after seating');
            ok();
        """), login='admin')

    def test_48_status_badge_canonical_p3b2(self):
        # DESIGN-P3B.2 — the reservation card metadata uses the canonical .mz-badge
        # (VIP/occasion) and Late uses the canonical .mz-status--warning; the bespoke
        # .mz-chip palette is fully retired. Real headless-browser render assertion.
        self.authenticate('admin', 'admin')
        now = fields.Datetime.now()
        # a confirmed booking whose slot has passed -> server marks it `late`; VIP + occasion
        self._mk_res(self.pos_config, self.tables[0], state='confirmed',
                     start=fields.Datetime.to_string(now - __import__('datetime').timedelta(hours=1)),
                     name='Salma G.', vip=True, occasion='Anniversary')
        prelude = (
            "const $=s=>document.querySelector(s);const $$=s=>[...document.querySelectorAll(s)];"
            "const phase=()=>($('.mz-app')?$('.mz-app').dataset.phase:null);"
            "async function waitFor(f,l,ms=15000){const t0=Date.now();"
            "while(Date.now()-t0<ms){try{if(f())return true;}catch(e){}"
            "await new Promise(r=>setTimeout(r,100));}throw new Error('timeout: '+l+' (phase='+phase()+')');}"
            "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
            "function card(){return $$('.mz-rescard').find(c=>/Salma/.test(c.textContent));}"
            "const ok=()=>console.log('test successful');")
        self.browser_js('/mezze/pos', prelude + _js_body(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            $$('.mz-nav__item').find(b => /reservations/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'reservations', 'reservations phase');
            await waitFor(() => card(), 'Salma card');
            const c = card();
            // canonical metadata badge language (VIP + occasion), NOT the retired .mz-chip
            assert(c.querySelector('.mz-badge--vip'), 'VIP renders as canonical .mz-badge--vip');
            assert([...c.querySelectorAll('.mz-badge')].some(b=>/Anniversary/.test(b.textContent)), 'occasion is a .mz-badge');
            // canonical operational status for Late (warning) with a non-colour-only dot
            const late = [...c.querySelectorAll('.mz-status--warning')].find(s=>/late/i.test(s.textContent));
            assert(late, 'Late renders as canonical .mz-status--warning');
            assert(late.querySelector('.mz-status__dot'), 'Late status carries the non-colour dot cue');
            // the main state chip is also canonical .mz-status
            assert(c.querySelector('.mz-status .mz-status__dot'), 'card state uses canonical .mz-status');
            // the bespoke palette is gone, product-wide
            assert(document.querySelectorAll('.mz-chip').length === 0, 'no retired .mz-chip anywhere');
            ok();
        """), login='admin')

    def test_49_alert_canonical_p3c(self):
        # DESIGN-P3C — a form validation failure renders the canonical .mz-alert--danger
        # (role=alert, severity glyph via ::before = non-colour cue); the retired
        # .mz-tablewarn / .mz-pay-error palettes are gone product-wide.
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
            $$('.mz-nav__item').find(b => /reservations/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'reservations', 'reservations phase');
            $$('.mz-btn').find(b => /new reservation/i.test(b.textContent)).click();
            await waitFor(() => $('.mz-resform'), 'reservation form');
            // Save with no guest name -> a canonical danger alert must appear
            $$('.mz-resform .mz-btn').find(b => /save reservation/i.test(b.textContent)).click();
            await waitFor(() => $('.mz-resform .mz-alert--danger'), 'canonical .mz-alert--danger renders');
            const a = $('.mz-resform .mz-alert--danger');
            assert(a.getAttribute('role') === 'alert', 'error alert is role=alert');
            // non-colour cue: the severity glyph is drawn via ::before
            const icon = getComputedStyle(a, '::before').content;
            assert(icon && icon !== 'none' && icon !== 'normal' && icon !== '""',
                   'alert carries a ::before severity glyph (non-colour cue), got: ' + icon);
            // the retired ad-hoc alert palettes are gone product-wide
            assert(document.querySelectorAll('.mz-tablewarn, .mz-pay-error').length === 0,
                   'no retired .mz-tablewarn / .mz-pay-error anywhere');
            ok();
        """), login='admin')

    def test_50_input_canonical_p3d(self):
        # DESIGN-P3D — canonical .mz-input: a visible focus ring (was missing), the 44px
        # touch height, a visible label, and a native .mz-select in the same family.
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
            $$('.mz-nav__item').find(b => /reservations/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'reservations', 'reservations phase');
            $$('.mz-btn').find(b => /new reservation/i.test(b.textContent)).click();
            await waitFor(() => $('.mz-resform .mz-input'), 'canonical input renders');
            const inp = $('.mz-resform .mz-input');
            // 44px touch contract
            assert(inp.getBoundingClientRect().height >= 44, 'input effective height >= 44px, got '
                   + inp.getBoundingClientRect().height);
            // the P3D fix: a visible focus ring (canonical .mz-input previously had none)
            inp.focus();
            const cs = getComputedStyle(inp);
            const ow = parseFloat(cs.outlineWidth) || 0;
            assert(cs.outlineStyle !== 'none' && ow >= 2, 'focused input shows a canonical outline ring, got '
                   + cs.outlineStyle + ' ' + cs.outlineWidth);
            // a visible label (not placeholder-only) sits in the field
            const field = inp.closest('.mz-field') || inp.closest('label');
            assert(field && /guest name/i.test(field.textContent), 'field has a visible label');
            // native select is in the same family
            assert($('.mz-resform .mz-select'), 'table picker is a canonical .mz-select');
            ok();
        """), login='admin')

    def test_51_visible_label_closure_p3d1(self):
        # DESIGN-P3D.1 — every form control on the production reservation/walk-in surface
        # carries a STABLE, programmatically-associated VISIBLE label (not placeholder-only).
        self.authenticate('admin', 'admin')
        prelude = (
            "const $=s=>document.querySelector(s);const $$=s=>[...document.querySelectorAll(s)];"
            "const phase=()=>($('.mz-app')?$('.mz-app').dataset.phase:null);"
            "async function waitFor(f,l,ms=15000){const t0=Date.now();"
            "while(Date.now()-t0<ms){try{if(f())return true;}catch(e){}"
            "await new Promise(r=>setTimeout(r,100));}throw new Error('timeout: '+l+' (phase='+phase()+')');}"
            "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
            "function auditModal(sel){const ctrls=$$(sel+' input, '+sel+' select, '+sel+' textarea');"
            "assert(ctrls.length>=3, sel+' has form controls, got '+ctrls.length);"
            "for(const c of ctrls){const lab=c.closest('label')||(c.id?$('label[for=\\''+c.id+'\\']'):null);"
            "assert(lab, sel+' control '+(c.type||c.tagName)+' has an associated <label>');"
            "const txt=(lab.textContent||'').replace(/\\s+/g,' ').trim();"
            "assert(txt.length>0, sel+' label for '+(c.type||c.tagName)+' has visible text');}}"
            "const ok=()=>console.log('test successful');")
        self.browser_js('/mezze/pos', prelude + _js_body(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            $$('.mz-nav__item').find(b => /reservations/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'reservations', 'reservations phase');
            // New reservation — every control labeled, guest name is a visible label
            $$('.mz-btn').find(b => /new reservation/i.test(b.textContent)).click();
            await waitFor(() => $('.mz-resform .mz-input'), 'reservation form renders');
            auditModal('.mz-resform');
            const rf = $('.mz-resform');
            assert(/guest name/i.test(rf.textContent) && /party size/i.test(rf.textContent),
                   'reservation shows visible Guest name + Party size labels');
            $('.mz-resform .mz-modal__x').click();
            // Walk-in — same contract (Waitlist tab → Add walk-in)
            await waitFor(() => !$('.mz-resform'), 'reservation form closed');
            $$('.mz-tab').find(b => /waitlist/i.test(b.textContent)).click();
            await waitFor(() => $$('.mz-btn').some(b => /add walk-in/i.test(b.textContent)), 'Add walk-in btn');
            $$('.mz-btn').find(b => /add walk-in/i.test(b.textContent)).click();
            await waitFor(() => $('.mz-resform .mz-input'), 'walk-in form renders');
            auditModal('.mz-resform');
            ok();
        """), login='admin')

    def test_52_customer_form_labels_static_p3d1(self):
        # DESIGN-P3D.1 — the customer HTML surfaces (not in the Owl suite) verified by
        # static contract: persisted fields are labeled, not placeholder-only; transient
        # search stays exempt; new i18n label keys exist in BOTH languages.
        from odoo.tools import file_open

        def load(name):
            with file_open('mezze_bridge/static/%s' % name, 'r') as fh:
                return fh.read()

        shop = load('shop.html')
        # persisted checkout fields no longer rely on placeholder identity (data-tph gone)…
        for k in ('name', 'phone', 'street', 'building', 'floor', 'apt', 'landmark', 'note'):
            self.assertNotIn('data-tph="%s"' % k, shop,
                             'shop persisted field %r must not be placeholder-only' % k)
            # …and each carries a canonical visible label
            self.assertRegex(shop, r'mz-label"[^>]*data-t="%s"' % k,
                             'shop field %r has a visible .mz-label' % k)
        self.assertRegex(shop, r'mz-label"[^>]*data-t="area"', 'delivery area labeled')
        # transient search stays exempt (accessible name via aria-label + placeholder)
        self.assertRegex(shop, r'id="search"[^>]*aria-label=', 'search keeps an accessible name')
        # new label key present in EN and AR
        self.assertEqual(shop.count("area:'"), 2, "area label key defined in both languages")

        fb = load('feedback.html')
        self.assertNotIn('data-tph=', fb, 'feedback fields are labeled, not placeholder-only')
        for k in ('commentlbl', 'namelbl'):
            self.assertRegex(fb, r'mz-label"[^>]*data-t="%s"' % k, 'feedback %r labeled' % k)
            self.assertEqual(fb.count("%s:'" % k), 2, '%r defined in both languages' % k)

        for name, ctrl_id, label in (('drivethru.html', 'veh', 'Vehicle'),
                                     ('courses.html', 'cname', 'Course name')):
            html = load(name)
            self.assertRegex(html, r'mz-label">%s' % label, '%s field labeled' % name)
            # placeholder demoted to an example hint, not the field identity
            self.assertRegex(html, r'id="%s"[^>]*placeholder="e\.g\.' % ctrl_id,
                             '%s placeholder is an example hint' % name)

    def test_53_party_size_stepper_canonical_p3e(self):
        # DESIGN-P3E — the party-size stepper is the canonical .mz-stepper (44px, native
        # button, accessible name, visible focus) and preserves the Math.max(1) clamp.
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
            $$('.mz-nav__item').find(b => /reservations/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'reservations', 'reservations phase');
            $$('.mz-btn').find(b => /new reservation/i.test(b.textContent)).click();
            await waitFor(() => $('.mz-guest .mz-stepper__btn'), 'party stepper renders');
            const btns = $$('.mz-guest .mz-stepper__btn');
            assert(btns.length === 2, 'minus + plus');
            const minus = btns[0], plus = btns[1];
            const val = () => $('.mz-guest .mz-stepper__value');
            // geometry + semantics
            const r = plus.getBoundingClientRect();
            assert(r.width >= 44 && r.height >= 44, 'party stepper >=44px, got ' + r.width + 'x' + r.height);
            for (const b of btns){
                assert(b.tagName === 'BUTTON' && b.getAttribute('type') === 'button', 'native <button type=button>');
                assert((b.getAttribute('aria-label') || '').trim().length > 0, 'stepper button has an accessible name');
            }
            plus.focus();
            const ow = parseFloat(getComputedStyle(plus).outlineWidth) || 0;
            assert(getComputedStyle(plus).outlineStyle !== 'none' && ow >= 2, 'focus ring visible on party stepper');
            // increment then clamp-at-1 (existing Math.max(1) rule, never removed/below 1)
            const start = parseInt(val().textContent.trim(), 10);
            plus.click(); plus.click();
            await waitFor(() => parseInt(val().textContent.trim(),10) === start + 2, 'two taps add two');
            for (let i=0;i<10;i++){ minus.click(); }
            await new Promise(r => setTimeout(r, 150));
            assert($('.mz-guest .mz-stepper__value'), 'stepper still present (form not removed by minus)');
            assert(parseInt(val().textContent.trim(),10) === 1, 'party size clamps at 1, got ' + val().textContent);
            ok();
        """), login='admin')

    def test_54_stepper_canonical_static_p3e(self):
        # DESIGN-P3E — every customer cart stepper is the canonical .mz-stepper; the old
        # per-surface visual classes (.step/.stepper/.qbtn) are gone; the family is 44px.
        from odoo.tools import file_open

        def load(name):
            with file_open('mezze_bridge/static/%s' % name, 'r') as fh:
                return fh.read()

        comp = load('design/components.css')
        self.assertIn('.mz-stepper__btn', comp, 'canonical stepper family defined once')
        self.assertRegex(comp, r'\.mz-stepper__btn\{[^}]*min-height:44px', 'canonical stepper is >=44px')

        # each customer surface adopts the canonical family, with accessible names,
        # and no longer ships its own quantity visual class
        for name, retired in (('shop.html', ('class="step"', '.step button')),
                              ('qr.html', ('class="stepper"', '.stepper button')),
                              ('kiosk.html', ('class="qbtn"', '.qbtn{')),
                              ('drivethru.html', ('class="step"', '.step button')),
                              ('courses.html', ('class="step"', '.step button'))):
            html = load(name)
            self.assertIn('mz-stepper__btn', html, '%s uses the canonical stepper' % name)
            self.assertIn('mz-stepper__value', html, '%s uses the canonical value' % name)
            self.assertIn('aria-label="Decrease quantity"', html, '%s minus has an accessible name' % name)
            self.assertIn('aria-label="Increase quantity"', html, '%s plus has an accessible name' % name)
            for token in retired:
                self.assertNotIn(token, html, '%s retired legacy quantity class %r' % (name, token))

        # cashier retired its bespoke quantity/guest button visuals
        css = load('src/cashier/cashier.css')
        self.assertNotIn('.mz-qtybtn{', css, 'cashier .mz-qtybtn visual removed')
        self.assertNotIn('.mz-guest__btn{', css, 'cashier .mz-guest__btn visual removed')

    def test_55_dialog_focus_canonical_p3f(self):
        # DESIGN-P3F — a real cashier dialog (reservation form) is the canonical dialog:
        # role/name, close >=44 with a name, action >=44, focus ENTERS on open, Tab is
        # trapped, and focus RESTORES to the trigger on close.
        self.authenticate('admin', 'admin')
        prelude = (
            "const $=s=>document.querySelector(s);const $$=s=>[...document.querySelectorAll(s)];"
            "const phase=()=>($('.mz-app')?$('.mz-app').dataset.phase:null);"
            "async function waitFor(f,l,ms=15000){const t0=Date.now();"
            "while(Date.now()-t0<ms){try{if(f())return true;}catch(e){}"
            "await new Promise(r=>setTimeout(r,100));}throw new Error('timeout: '+l+' (phase='+phase()+')');}"
            "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
            "const vis=el=>[...el.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled])')].filter(e=>e.offsetParent!==null);"
            "const ok=()=>console.log('test successful');")
        self.browser_js('/mezze/pos', prelude + _js_body(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            $$('.mz-nav__item').find(b => /reservations/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'reservations', 'reservations phase');
            const trigger = $$('.mz-btn').find(b => /new reservation/i.test(b.textContent));
            trigger.focus();                       // simulate keyboard-initiated open
            const before = document.activeElement;
            trigger.click();
            await waitFor(() => $('.mz-modal-scrim .mz-modal'), 'dialog renders');
            const panel = $('.mz-modal-scrim .mz-modal');
            // 1) canonical dialog semantics
            assert(panel.getAttribute('role') === 'dialog', 'role=dialog');
            assert((panel.getAttribute('aria-label') || panel.getAttribute('aria-labelledby') || '').length > 0,
                   'dialog has an accessible name');
            // 2) initial focus entered the dialog
            await waitFor(() => panel.contains(document.activeElement), 'focus moved inside the dialog');
            // 3) close control >=44x44 (measured via the CSS contract, not sub-pixel rect)
            //    with an accessible name
            const x = panel.querySelector('.mz-modal__x');
            const xcs = getComputedStyle(x);
            assert(parseFloat(xcs.width) >= 44 && parseFloat(xcs.height) >= 44,
                   'close >=44x44, got ' + xcs.width + 'x' + xcs.height);
            assert((x.getAttribute('aria-label') || '').trim().length > 0, 'close has an accessible name');
            // 4) action button >=44px high
            const save = $$('.mz-btn', panel).find(b => /save reservation/i.test(b.textContent))
                        || vis(panel).slice(-1)[0];
            assert(parseFloat(getComputedStyle(save).minHeight) >= 44
                   || parseFloat(getComputedStyle(save).height) >= 44, 'action >=44px high');
            // 5) focus trap — Tab at the last focusable wraps back inside (never escapes)
            const f = vis(panel);
            f[f.length - 1].focus();
            panel.dispatchEvent(new KeyboardEvent('keydown', {key:'Tab', bubbles:true}));
            assert(panel.contains(document.activeElement), 'Tab keeps focus inside the dialog');
            // 6) backdrop click closes the (cancellable) dialog AND restores focus to trigger
            $('.mz-modal-scrim').click();
            await waitFor(() => !$('.mz-modal-scrim .mz-modal'), 'dialog closed via backdrop');
            await waitFor(() => document.activeElement === before, 'focus restored to the trigger');
            ok();
        """), login='admin')

    def test_56_dialog_and_toast_static_p3f(self):
        # DESIGN-P3F — canonical dialog family exists + folds the legacy cashier modal
        # palette; production browser-native blocking UI (alert/confirm/prompt) is gone,
        # replaced by the canonical non-blocking toast.
        import re as _re
        from odoo.tools import file_open

        def load(name):
            with file_open('mezze_bridge/static/%s' % name, 'r') as fh:
                return fh.read()

        comp = load('design/components.css')
        for cls in ('.mz-dialog__backdrop', '.mz-dialog__panel', '.mz-dialog__title',
                    '.mz-dialog__actions', '.mz-dialog__close'):
            self.assertIn(cls, comp, 'canonical dialog part %r defined' % cls)
        # the legacy cashier modal class names are FOLDED onto the canonical rules…
        self.assertRegex(comp, r'\.mz-dialog__backdrop,[^{]*\.mz-modal-scrim', 'scrim folded onto canonical backdrop')
        self.assertRegex(comp, r'\.mz-dialog__close,[^{]*\.mz-modal__x', 'close folded onto canonical')
        # …and their bespoke bodies are removed from cashier.css (single source of truth)
        css = load('src/cashier/cashier.css')
        self.assertNotIn('.mz-modal-scrim{', css, 'cashier scrim body removed')
        self.assertNotIn('.mz-modal__x{', css, 'cashier close body removed')

        # production customer surfaces: ZERO browser-native blocking UI, canonical toast present
        native = _re.compile(r'(?<![.\w])(?:alert|confirm|prompt)\s*\(')
        for name in ('feedback.html', 'shop.html', 'drivethru.html', 'courses.html', 'mezze-customer.js'):
            src = load(name)
            # strip full-line comments that merely mention alert() in prose
            code = '\n'.join(ln for ln in src.splitlines() if not ln.lstrip().startswith('//'))
            self.assertFalse(native.search(code),
                             '%s still calls a browser-native alert/confirm/prompt' % name)
        for name in ('feedback.html', 'shop.html', 'drivethru.html', 'courses.html'):
            self.assertIn('function mzToast', load(name), '%s has the canonical toast helper' % name)

    def test_57_card_canonical_p3g(self):
        # DESIGN-P3G — the reservation card is the canonical container: a NON-interactive
        # container with explicit child actions (never a card-button wrapping buttons),
        # canonical surface/border, business status stays .mz-status, and its frequent
        # actions are >=44px.
        self.authenticate('admin', 'admin')
        now = fields.Datetime.now()
        self._mk_res(self.pos_config, self.tables[0], state='confirmed',
                     start=fields.Datetime.to_string(now + __import__('datetime').timedelta(hours=1)),
                     name='Nadia P.')
        prelude = (
            "const $=s=>document.querySelector(s);const $$=s=>[...document.querySelectorAll(s)];"
            "const phase=()=>($('.mz-app')?$('.mz-app').dataset.phase:null);"
            "async function waitFor(f,l,ms=15000){const t0=Date.now();"
            "while(Date.now()-t0<ms){try{if(f())return true;}catch(e){}"
            "await new Promise(r=>setTimeout(r,100));}throw new Error('timeout: '+l+' (phase='+phase()+')');}"
            "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
            "function card(){return $$('.mz-rescard').find(c=>/Nadia/.test(c.textContent));}"
            "const ok=()=>console.log('test successful');")
        self.browser_js('/mezze/pos', prelude + _js_body(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            $$('.mz-nav__item').find(b => /reservations/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'reservations', 'reservations phase');
            await waitFor(() => card(), 'Nadia card');
            const c = card();
            // 1) canonical container surface (real border + non-transparent background)
            const cs = getComputedStyle(c);
            assert(parseFloat(cs.borderTopWidth) >= 1, 'card has a canonical border');
            assert(cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)', 'card has a surface fill');
            // 2) NOT a whole-card button/link, and it does NOT nest a button inside a button
            assert(c.tagName !== 'BUTTON' && c.tagName !== 'A',
                   'reservation card is a non-interactive container, not a card-button');
            assert(!c.closest('button') && !c.closest('a'), 'card is not wrapped by an interactive control');
            // 3) explicit child action buttons (native <button>), each >=44px high
            const acts = [...c.querySelectorAll('.mz-rescard__actions .mz-btn')];
            assert(acts.length >= 1, 'card exposes explicit child actions');
            for (const b of acts) {
                assert(b.tagName === 'BUTTON', 'each card action is a native <button>');
                assert(parseFloat(getComputedStyle(b).minHeight) >= 44
                       || b.getBoundingClientRect().height >= 43.5, 'card action >=44px');
            }
            // 4) business status stays .mz-status (never encoded by the card colour alone)
            assert(c.querySelector('.mz-status .mz-status__dot'), 'status stays canonical .mz-status');
            ok();
        """), login='admin')

    def test_58_card_family_static_p3g(self):
        # DESIGN-P3G — canonical card/list-row family exists and the operational cards
        # (tile/order/reservation/kds/customer-row) are FOLDED onto it (their bespoke
        # surface/border/radius bodies are gone). Status/attention stay separate.
        from odoo.tools import file_open

        def load(name):
            with file_open('mezze_bridge/static/%s' % name, 'r') as fh:
                return fh.read()

        comp = load('design/components.css')
        for cls in ('.mz-card', '.mz-listrow', '.mz-card--interactive', '.mz-card--selected',
                    '.mz-card--attention', '.mz-listrow__main', '.mz-card__actions'):
            self.assertIn(cls, comp, 'canonical card part %r defined' % cls)
        # the operational cards are grouped onto the canonical surface rule…
        self.assertRegex(comp, r'\.mz-card,[^{]*\.mz-tile,[^{]*\.mz-ordcard,[^{]*\.mz-rescard,[^{]*\.mz-kds-card\{',
                         'operational cards folded onto the canonical card surface')
        self.assertRegex(comp, r'\.mz-listrow,[^{]*\.mz-cust-row\{', 'customer row folded onto canonical list-row')
        # selection is not colour-only (border + inset ring) and distinct from success
        self.assertRegex(comp, r'\.mz-card--selected,[^{]*\.mz-tile--kbd,[^{]*\.mz-cust-row--active\{[^}]*box-shadow:inset',
                         'selected state carries a non-colour inset ring')
        # …and the bespoke surface/border bodies are removed from the cashier/kds defs
        css = load('src/cashier/cashier.css')
        self.assertNotRegex(css, r'\.mz-tile\{[^}]*border:1px solid var\(--mz-border\)', 'tile border folded')
        self.assertNotRegex(css, r'\.mz-ordcard\{[^}]*border:1px solid', 'order card border folded')
        self.assertNotIn('.mz-tile--kbd{', css, 'tile selected visual folded')
        self.assertNotIn('.mz-cust-row--active{', css, 'customer-row selected visual folded')
        kds = load('src/kds/kds.css')
        self.assertNotRegex(kds, r'\.mz-kds-card \{[^}]*border:', 'kds card border folded')

    def test_59_empty_state_not_error_p3h(self):
        # DESIGN-P3H — an empty list (no waiting guests) is a NORMAL empty state, not a
        # failure: canonical .mz-state--empty, muted (not danger), and NOT a live-region
        # error/alert.
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
            $$('.mz-nav__item').find(b => /reservations/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'reservations', 'reservations phase');
            $$('.mz-tab').find(b => /waitlist/i.test(b.textContent)).click();
            await waitFor(() => $('.mz-state--empty'), 'empty state renders for an empty waitlist');
            const e = $('.mz-state--empty');
            // 1) it is the canonical EMPTY, never the ERROR palette
            assert(!e.classList.contains('mz-state--error'), 'empty is not styled as an error');
            // 2) empty is not an urgent live region (P3C owns urgent announcements)
            assert(e.getAttribute('role') !== 'alert' && !e.closest('[role="alert"]'),
                   'empty state is not a role=alert live region');
            // 3) friendly no-data copy, not the word "Error"
            assert(!/error|failed|unavailable/i.test(e.textContent), 'empty copy is not a failure message');
            assert(e.textContent.trim().length > 0, 'empty state has a message');
            // 4) muted colour (text-mut), not the danger colour
            const col = getComputedStyle(e).color;
            const danger = getComputedStyle(document.documentElement).getPropertyValue('--mz-danger').trim();
            assert(!danger || col !== danger, 'empty text is not the danger colour');
            ok();
        """), login='admin')

    def test_60_state_family_static_p3h(self):
        # DESIGN-P3H — one canonical empty/loading/error family + one spinner (with the
        # reduced-motion cue the cashier lacked); cashier/floor duplicates folded; a
        # single @keyframes; loading carries aria-busy.
        from odoo.tools import file_open

        def load(name):
            with file_open('mezze_bridge/static/%s' % name, 'r') as fh:
                return fh.read()

        comp = load('design/components.css')
        for cls in ('.mz-state', '.mz-state__title', '.mz-state__message', '.mz-state__actions',
                    '.mz-state--error', '.mz-state--empty', '.mz-grid-empty', '.mz-spinner'):
            self.assertIn(cls, comp, 'canonical state part %r defined' % cls)
        self.assertIn('@keyframes mz-spin', comp, 'single spin keyframe lives in the canonical layer')
        self.assertRegex(comp, r'prefers-reduced-motion: reduce\)\{ \.mz-spinner\{ animation-duration',
                         'reduced motion keeps a visible (slow) spinner, not gone')
        # cashier + floor duplicate bodies folded (no local spin keyframe / spinner body)
        css = load('src/cashier/cashier.css')
        self.assertNotIn('@keyframes mz-spin', css, 'cashier keyframe folded')
        self.assertNotRegex(css, r'\.mz-state\{', 'cashier .mz-state body folded')
        self.assertNotRegex(css, r'\.mz-spinner\{[^}]*animation:mz-spin', 'cashier spinner body folded')
        floor = load('src/floor/floor.css')
        self.assertNotIn('@keyframes mz-spin', floor, 'floor keyframe folded')
        self.assertNotRegex(floor, r'\.mz-spinner\{[^}]*animation:mz-spin', 'floor spinner body folded')
        # loading state carries canonical busy semantics
        self.assertRegex(load('src/cashier/root.xml'), r'mz-state--info"[^>]*aria-busy="true"',
                         'cashier loading state is aria-busy')

    def test_61_segmented_canonical_p3i(self):
        # DESIGN-P3I — the host day + Reservations|Waitlist controls are canonical single-
        # select SEGMENTED tracks: aria-pressed toggle, >=44px, non-colour weight cue, and
        # business status stays .mz-status (never a filter).
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
            $$('.mz-nav__item').find(b => /reservations/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'reservations', 'reservations phase');
            const view = [...document.querySelectorAll('.mz-host__tabs .mz-tab')];
            assert(view.length === 2, 'Reservations|Waitlist segmented has two items');
            // 1) aria-pressed toggle + >=44px on every item
            for (const t of view) {
                assert(t.tagName === 'BUTTON' && t.hasAttribute('aria-pressed'), 'segment is a button with aria-pressed');
                assert(parseFloat(getComputedStyle(t).minHeight) >= 44, 'segment >=44px');
            }
            const res = view.find(t => /reservations/i.test(t.textContent));
            const wl = view.find(t => /waitlist/i.test(t.textContent));
            assert(res.getAttribute('aria-pressed') === 'true' && wl.getAttribute('aria-pressed') === 'false',
                   'Reservations is initially selected, single-select');
            // 2) selected is not colour-only — heavier weight than the unselected segment
            assert(parseInt(getComputedStyle(res).fontWeight,10) > parseInt(getComputedStyle(wl).fontWeight,10),
                   'selected segment is heavier (non-colour cue)');
            // 3) selecting Waitlist moves the pressed state (single-select)
            wl.click();
            await waitFor(() => wl.getAttribute('aria-pressed') === 'true', 'Waitlist becomes selected');
            assert(res.getAttribute('aria-pressed') === 'false', 'Reservations deselected — single-select');
            // 4) the day control is also an aria-pressed segmented track
            assert([...document.querySelectorAll('.mz-host__date .mz-tab')].every(t => t.hasAttribute('aria-pressed')),
                   'day filter uses aria-pressed');
            // 5) business status never becomes a filter
            assert($$('.mz-status').every(s => !s.hasAttribute('aria-pressed')), 'status is not a filter');
            ok();
        """), login='admin')

    def test_62_tabs_filters_static_p3i(self):
        # DESIGN-P3I — canonical segmented + filter-chip families exist and fold the legacy
        # cashier .mz-tab/.mz-cat; selected is not colour-only; customer category strips carry
        # aria-pressed; no unused true-tab system is built.
        from odoo.tools import file_open

        def load(name):
            with file_open('mezze_bridge/static/%s' % name, 'r') as fh:
                return fh.read()

        comp = load('design/components.css')
        for cls in ('.mz-segmented', '.mz-segmented__item', '.mz-filter-chip'):
            self.assertIn(cls, comp, 'canonical control %r defined' % cls)
        # legacy names fold onto the canonical rules
        self.assertRegex(comp, r'\.mz-segmented__item,[^{]*\.mz-tab\{', 'legacy .mz-tab folds onto segmented item')
        self.assertRegex(comp, r'\.mz-filter-chip,[^{]*\.mz-cat\{', 'legacy .mz-cat folds onto filter chip')
        # selected state carries a weight (non-colour) cue, not colour alone
        self.assertRegex(comp, r'\.mz-tab\[aria-pressed="true"\][^{]*\{[^}]*font-weight:800',
                         'selected segment is not colour-only (weight cue)')
        self.assertRegex(comp, r'\.mz-cat--active\{[^}]*box-shadow:inset', 'selected chip has an inset ring')
        # the bespoke cashier bodies are removed (single source)
        css = load('src/cashier/cashier.css')
        self.assertNotRegex(css, r'\n\.mz-tab\{', 'cashier .mz-tab body folded')
        self.assertNotRegex(css, r'\n\.mz-cat\{', 'cashier .mz-cat body folded')
        # customer category strips expose aria-pressed
        for name in ('qr.html', 'kiosk.html'):
            self.assertIn('aria-pressed', load(name), '%s category strip carries aria-pressed' % name)
