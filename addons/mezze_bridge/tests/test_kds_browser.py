"""V2C — authenticated browser certification of the REAL Owl Kitchen Display (/mezze/kds).

Uses Odoo's own ``HttpCase.browser_js(login=...)`` — the framework authenticates the
headless Chrome via the test session, so NO password is typed and NO auth bypass is
introduced. Production ``/mezze/kds`` stays ``auth='user'`` and mints a LEAST-PRIVILEGE
kitchen token (kitchen.read + kitchen.update only).

Fires / voids that seed a scenario are driven server-side over HTTP (``url_open`` →
committed in the live worker, so the browser's next snapshot sees them). Firing uses a
scoped ``role='terminal'`` fixture token (holds orders.fire — the waiter/table
principal); voiding narrows to a manager ``mezze.cashier`` (holds orders.void). These
are TEST FIXTURES that model the authoritative waiter/manager principals — the
production KDS page never exposes them. In-board transitions use the page's OWN kitchen
token (kitchen.update). Authority throughout = ``mezze.kds.ticket``; no Enterprise
Preparation Display is involved.

Tagged ``mezze_browser`` so it selects/skips independently of the headless suite.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase
from ..controllers.main import API_PREFIX

_PRELUDE = r"""
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const app = () => $('.mz-kds-app');
const phase = () => (app() ? app().dataset.phase : null);
const cards = () => $$('.mz-kds-card');
const cardFor = (id) => $('.mz-kds-card[data-ticket-id="' + id + '"]');
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){} await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label + ' (phase=' + phase() + ')');
}
function assert(cond, msg){ if(!cond) throw new Error('assert failed: ' + msg); }
const ok = () => console.log('test successful');
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser')
class TestKdsBrowser(MezzeHttpCase):
    fixture_profile = 'KDS'
    open_session_in_setup = True   # the fire/void HTTP helpers need an open session

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product.write({'available_in_pos': True, 'list_price': 100.0, 'taxes_id': [(5, 0, 0)]})
        # a SECOND product so a course-2 / addition is visibly distinct from course-1
        cls.product2 = cls.env['product.product'].sudo().create({
            'name': 'Mezze KDS Dish Two', 'available_in_pos': True, 'list_price': 40.0,
            'taxes_id': [(5, 0, 0)]})
        # cash is already on the fixture config (C_POS); a session is open here, so
        # payment methods must NOT be modified. KDS itself never takes payment.
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        # a stable, fully 'opened' session for the fire/void HTTP calls + KDS snapshot
        sess = cls.pos_config.current_session_id
        if sess:
            if sess.state == 'opening_control':
                try:
                    sess.set_opening_control(0, None)
                except Exception:  # noqa: BLE001
                    pass
            if sess.state != 'opened':
                sess.sudo().write({'state': 'opened'})
        cls.session_id = sess.id if sess else False
        cls.table = cls.tables[0]
        # fixture FIRE token — a scoped role='terminal' principal (holds orders.fire),
        # standing in for the waiter/table app. Plaintext kept only in the test.
        cls.fire_token = 'kds-fire-tok'
        cls.env['mezze.terminal'].sudo().create({
            'name': 'KDS Test Fire', 'identifier': 'kds-test-fire',
            'token': cls.fire_token, 'branch_id': cls.pos_config.id,
            'active': True, 'role': 'terminal'})
        # manager cashier → narrows the void call to orders.void (least privilege elsewhere)
        cls.mgr = cls.env['mezze.cashier'].sudo().create({
            'name': 'KDS Test Manager', 'code': 'KDSMGR', 'role': 'manager',
            'active': True, 'config_ids': [(4, cls.pos_config.id)]})
        # a real ar_001 kitchen user for the Arabic acceptance test
        cls.env['res.lang'].sudo()._activate_lang('ar_001')
        cls.ar_user = cls.env['res.users'].sudo().create({
            'name': 'Mezze AR Kitchen', 'login': 'mz_ar_kitchen', 'lang': 'ar_001',
            'group_ids': [(6, 0, cls.env.ref('base.group_user').ids
                          + cls.env.ref('point_of_sale.group_pos_user').ids)],
        })
        cls.env.flush_all()

    # ---- server-side scenario helpers (commit in the live worker) ----------
    def _post(self, path, **params):
        params.setdefault('token', self.fire_token)
        r = self.url_open(API_PREFIX + path, data=json.dumps(params),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:200]}

    def _fire(self, uuid, product, qty=1, table_id=None, fire_uuid=None):
        st, data = self._post('/orders/fire', uuid=uuid, session_id=self.session_id,
                              table_id=table_id or self.table.id,
                              lines=[{'product_id': product.id, 'qty': qty}],
                              fire_uuid=fire_uuid)
        self.assertEqual(st, 200, 'fire HTTP ok: %s' % (data,))
        self.assertTrue(data.get('ok'), 'fire ok: %s' % (data,))
        return data

    def _hold(self, table_id, seq, product, qty=1):
        st, data = self._post('/courses/hold', table_id=table_id, seq=seq,
                              name='Course %s' % seq,
                              lines=[{'product_id': product.id, 'qty': qty}])
        self.assertEqual(st, 200, 'hold HTTP ok: %s' % (data,))
        self.assertTrue(data.get('ok'), 'hold ok: %s' % (data,))
        return data

    def _fire_course(self, table_id, seq):
        st, data = self._post('/courses/fire', table_id=table_id, seq=seq)
        self.assertEqual(st, 200, 'course-fire HTTP ok: %s' % (data,))
        self.assertTrue(data.get('ok'), 'course-fire ok: %s' % (data,))
        return data

    def _void(self, order_id):
        st, data = self._post('/orders/void', session_id=self.session_id,
                              order_id=order_id, cashier_id=self.mgr.id,
                              reason='browser test void')
        self.assertEqual(st, 200, 'void HTTP ok: %s' % (data,))
        self.assertTrue(data.get('ok'), 'void ok: %s' % (data,))
        return data

    # ---- Part E: mount the REAL board (not demo, not prototype) -------------
    def test_01_kds_mounts_real_not_demo(self):
        self._fire('kds-mount-1', self.product)
        self.browser_js('/mezze/kds', _js(r"""
            await waitFor(() => phase() === 'board', 'phase=board (Owl ready)');
            assert($('.mz-kds-board'), 'board mounted');
            assert(!$('[data-testid="mz-kds-error"]'), 'no error state');
            assert(!$('[data-testid="mz-kds-auth"]'), 'no auth banner');
            await waitFor(() => cards().length >= 1, 'at least one real ticket card');
            const c = cards()[0];
            assert(c.dataset.state, 'card carries an explicit data-state');
            assert($('.mz-kds-timer'), 'a monospaced timer is rendered');
            assert($('.mz-kds-branch') && $('.mz-kds-branch').textContent.trim().length > 0, 'branch name present');
            const conn = $('.mz-kds-conn');
            assert(conn && /mz-status--(success|danger|neutral)/.test(conn.className), 'connectivity is a canonical .mz-status');
            assert(conn.textContent.trim().length > 0, 'connectivity is not colour-only');
            assert($('.mz-kds-livecount__n'), 'a live count is shown');
            ok();
        """), login='admin')

    # ---- Part 11/36: held course hidden, then appears exactly once on fire (HARD GATE) ----
    def test_02_held_course_hidden_then_fired(self):
        # course 1 fired to the table; course 2 HELD (must never reach the kitchen)
        self._fire('kds-crs-1', self.product, table_id=self.table.id)
        self._hold(self.table.id, 2, self.product2)
        self.browser_js('/mezze/kds', _js(r"""
            await waitFor(() => phase() === 'board', 'board');
            await waitFor(() => cards().length >= 1, 'course 1 visible');
            assert($$('.mz-kds-card[data-course="2"]').length === 0,
                   'HELD course 2 is NOT on the kitchen board');
            ok();
        """), login='admin')
        # now FIRE course 2 → it must appear exactly once
        self._fire_course(self.table.id, 2)
        self.browser_js('/mezze/kds', _js(r"""
            await waitFor(() => phase() === 'board', 'board');
            await waitFor(() => $$('.mz-kds-card[data-course="2"]').length === 1, 'course 2 appears');
            assert($$('.mz-kds-card[data-course="2"]').length === 1,
                   'fired course 2 appears EXACTLY once');
            ok();
        """), login='admin')

    # ---- Part 12/37: an addition after fire is obvious + appears once (HARD GATE) ----
    def test_03_addition_marked_exactly_once(self):
        self._fire('kds-add-1', self.product, table_id=self.table.id)
        # a later fire to the SAME table = an addition (course > 1)
        self._fire('kds-add-1', self.product2, table_id=self.table.id, fire_uuid='kds-add-delta')
        self.browser_js('/mezze/kds', _js(r"""
            await waitFor(() => phase() === 'board', 'board');
            await waitFor(() => $$('.mz-kds-card[data-added="1"]').length === 1, 'addition present');
            const added = $$('.mz-kds-card[data-added="1"]');
            assert(added.length === 1, 'the addition appears EXACTLY once');
            assert(/ADDED/i.test(added[0].textContent), 'addition carries an explicit ADDED marker (not colour-only)');
            ok();
        """), login='admin')

    # ---- Part 13/38: void → KDS cancellation, shown once, never silently removed (HARD GATE) ----
    def test_04_cancellation_shown_exactly_once(self):
        d = self._fire('kds-void-1', self.product, table_id=self.table.id)
        order_id = d['order_id']
        tid = d['tickets'][0]['id']
        # board sees it live first
        self.browser_js('/mezze/kds', _js((r"""
            await waitFor(() => phase() === 'board', 'board');
            await waitFor(() => cardFor(%d) && cardFor(%d).dataset.state !== 'cancel', 'live ticket present');
            ok();
        """ % (tid, tid))), login='admin')
        # authoritative void
        self._void(order_id)
        self.browser_js('/mezze/kds', _js((r"""
            await waitFor(() => phase() === 'board', 'board');
            await waitFor(() => $$('.mz-kds-card[data-state="cancel"]').length === 1, 'cancellation shown');
            const cx = $$('.mz-kds-card[data-state="cancel"]');
            assert(cx.length === 1, 'cancellation appears EXACTLY once');
            assert(/CANCELLED/i.test(cx[0].textContent), 'cancelled work is explicitly labelled, not silently removed');
            ok();
        """)), login='admin')
        # DB truth: every live ticket of that order is now cancelled
        tickets = self.env['mezze.kds.ticket'].search([('pos_order_id', '=', order_id)])
        self.assertTrue(tickets, 'tickets exist for the order')
        self.assertTrue(all(t.state == 'cancel' for t in tickets),
                        'the void cascaded to every kitchen ticket')

    # ---- Part 16: next-action transition via the page's OWN kitchen token ----
    def test_05_transition_advances_state(self):
        d = self._fire('kds-adv-1', self.product, table_id=self.table.id)
        oid = d['order_id']
        tid = d['tickets'][0]['id']
        self.browser_js('/mezze/kds', _js((r"""
            await waitFor(() => phase() === 'board', 'board');
            const card = await (async () => { await waitFor(() => cardFor(%d), 'card'); return cardFor(%d); })();
            assert(card.dataset.state === 'fired', 'starts fired');
            const adv = card.querySelector('.mz-kds-advance');
            assert(adv, 'a single next-action button (not every state)');
            assert(card.querySelectorAll('.mz-kds-advance').length === 1, 'exactly one advance action');
            adv.click();
            await waitFor(() => cardFor(%d) && cardFor(%d).dataset.state === 'accepted', 'advanced to accepted');
            cardFor(%d).querySelector('.mz-kds-advance').click();
            await waitFor(() => cardFor(%d) && cardFor(%d).dataset.state === 'preparing', 'advanced to preparing');
            ok();
        """ % (tid, tid, tid, tid, tid, tid, tid))), login='admin')
        ticket = self.env['mezze.kds.ticket'].search([('pos_order_id', '=', oid)], limit=1)
        self.assertEqual(ticket.state, 'preparing', 'DB reflects the browser transitions')

    # ---- Part 33/41: concurrent bump on one ticket → one logical transition ----
    def test_06_concurrent_transition_one_logical_effect(self):
        d = self._fire('kds-conc-1', self.product, table_id=self.table.id)
        oid = d['order_id']
        tid = d['tickets'][0]['id']
        # two simultaneous accepts on the same ticket (row-locked server) → exactly one
        # logical transition; the loser reports changed=false. The board converges.
        self.browser_js('/mezze/kds?debug=1', _js((r"""
            await waitFor(() => phase() === 'board', 'board');
            await waitFor(() => cardFor(%d), 'card');
            const api = window.__mezzeKds.root.api;
            const [a, b] = await Promise.all([
                api.call('/kds/transition', {ticket_id: %d, action: 'accept'}),
                api.call('/kds/transition', {ticket_id: %d, action: 'accept'}),
            ]);
            const changes = [a.changed, b.changed].filter(Boolean).length;
            assert(changes === 1, 'exactly ONE logical transition (got ' + changes + ')');
            await window.__mezzeKds.root.seedSnapshot();
            await waitFor(() => cardFor(%d) && cardFor(%d).dataset.state === 'accepted', 'both converge to accepted');
            ok();
        """ % (tid, tid, tid, tid, tid))), login='admin')
        ticket = self.env['mezze.kds.ticket'].search([('pos_order_id', '=', oid)], limit=1)
        self.assertEqual(ticket.state, 'accepted', 'one logical accept persisted')

    # ---- Part 34: reconnect reconciles from the server snapshot (no duplicates) ----
    def test_07_reconnect_reseeds_without_duplicates(self):
        self._fire('kds-rc-1', self.product, table_id=self.table.id)
        self.browser_js('/mezze/kds?debug=1', _js(r"""
            await waitFor(() => phase() === 'board', 'board');
            await waitFor(() => cards().length >= 1, 'seeded');
            const before = cards().length;
            const root = window.__mezzeKds.root;
            // simulate a dropped socket → reconnect: full authoritative re-seed
            await root.seedSnapshot();
            await root.seedSnapshot();
            await new Promise(r => setTimeout(r, 200));
            assert(cards().length === before, 'reconnect did NOT duplicate tickets (' + cards().length + ' vs ' + before + ')');
            ok();
        """), login='admin')

    # ---- Part 27: Arabic (ar_001) — RTL + IBM Plex Sans Arabic + numeric timer ----
    def test_08_arabic_rtl(self):
        self._fire('kds-ar-1', self.product, table_id=self.table.id)
        self.browser_js('/mezze/kds', _js(r"""
            await waitFor(() => phase() === 'board', 'board (ar)');
            const h = document.documentElement;
            assert(h.getAttribute('dir') === 'rtl', 'html dir=rtl for ar');
            assert((h.getAttribute('lang') || '').indexOf('ar') === 0, 'html lang=ar');
            const ff = getComputedStyle(document.body).fontFamily;
            assert(/IBM Plex\s+Sans\s+Arabic/i.test(ff), 'canonical Arabic font on body: ' + ff);
            await waitFor(() => cards().length >= 1, 'card renders under RTL');
            const timer = $('.mz-kds-timer');
            assert(timer && timer.getAttribute('dir') === 'ltr', 'timer stays LTR/numeric under RTL');
            assert(/\d/.test(timer.textContent), 'timer shows digits');
            ok();
        """), login=self.ar_user.login)

    # ---- Part 29: Dark mode via the REAL Mezze theme contract ----
    def test_09_dark_mode_real_contract(self):
        self._fire('kds-dk-1', self.product, table_id=self.table.id)
        self.browser_js('/mezze/kds?mzmode=dark', _js(r"""
            await waitFor(() => phase() === 'board', 'board');
            const h = document.documentElement;
            assert(h.getAttribute('data-mz-mode') === 'dark', 'data-mz-mode=dark');
            var cv=document.createElement('canvas'); cv.width=cv.height=1; var cx=cv.getContext('2d');
            cx.fillStyle=getComputedStyle(h).getPropertyValue('--mz-canvas').trim(); cx.fillRect(0,0,1,1);
            var d=cx.getImageData(0,0,1,1).data;
            var lum=(0.2126*d[0]+0.7152*d[1]+0.0722*d[2])/255;
            assert(lum < 0.35, 'dark canvas luminance ('+lum.toFixed(2)+')');
            await waitFor(() => cards().length >= 1, 'card renders in dark');
            ok();
        """), login='admin')

    # ---- Part 30: High-Contrast via the REAL Mezze app theme (labels stay explicit) ----
    def test_10_high_contrast_app_theme(self):
        self._fire('kds-hc-1', self.product, table_id=self.table.id)
        self.browser_js('/mezze/kds?mztheme=highcontrast', _js(r"""
            await waitFor(() => phase() === 'board', 'board');
            const h = document.documentElement;
            assert(h.getAttribute('data-mz-theme') === 'highcontrast', 'HC theme active');
            function rgb(css){ var cv=document.createElement('canvas'); cv.width=cv.height=1; var cx=cv.getContext('2d'); cx.fillStyle=css; cx.fillRect(0,0,1,1); return cx.getImageData(0,0,1,1).data; }
            function lum(d){ return (0.2126*d[0]+0.7152*d[1]+0.0722*d[2])/255; }
            var cs=getComputedStyle(h);
            var Lc=lum(rgb(cs.getPropertyValue('--mz-canvas').trim()));
            var Lt=lum(rgb(cs.getPropertyValue('--mz-text').trim()));
            assert(Math.abs(Lc - Lt) > 0.7, 'HC canvas/text near-max contrast ('+Lc.toFixed(2)+'/'+Lt.toFixed(2)+')');
            await waitFor(() => cards().length >= 1, 'card renders');
            const chip = $('.mz-kds-statechip');
            assert(chip && chip.textContent.trim().length > 0, 'state meaning stays explicit TEXT under HC');
            ok();
        """), login='admin')

    # ---- Part 35: REAL /mezze/pos exists + a real fire flows to the REAL /mezze/kds ----
    def test_11_cashier_and_kds_are_real_products(self):
        # (a) the REAL cashier mounts (not the prototype)
        self.browser_js('/mezze/pos', _js(r"""
            const p = () => ($('.mz-app') ? $('.mz-app').dataset.phase : null);
            await waitFor(() => p() === 'menu', 'real cashier menu');
            assert($('.mz-workspace'), 'real cashier workspace (not prototype)');
            assert($$('.mz-tile').length > 0, 'real catalog');
            ok();
        """), login='admin')
        # (b) a table order fired via the authoritative path lands on the REAL KDS,
        #     exactly once, and the kitchen can work it.
        d = self._fire('kds-e2e-1', self.product, table_id=self.table.id)
        oid = d['order_id']
        tid = d['tickets'][0]['id']
        self.browser_js('/mezze/kds', _js((r"""
            await waitFor(() => phase() === 'board', 'real KDS board');
            await waitFor(() => cardFor(%d), 'fired ticket on the real KDS');
            assert($$('.mz-kds-card[data-ticket-id="%d"]').length === 1,
                   'the fired order appears exactly once');
            cardFor(%d).querySelector('.mz-kds-advance').click();
            await waitFor(() => cardFor(%d) && cardFor(%d).dataset.state === 'accepted', 'kitchen accepted it');
            ok();
        """ % (tid, tid, tid, tid, tid))), login='admin')
        ticket = self.env['mezze.kds.ticket'].search([('pos_order_id', '=', oid)], limit=1)
        self.assertEqual(ticket.state, 'accepted', 'the real cashier→KDS flow persisted a transition')
