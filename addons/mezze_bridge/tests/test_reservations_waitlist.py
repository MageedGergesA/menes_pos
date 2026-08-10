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
