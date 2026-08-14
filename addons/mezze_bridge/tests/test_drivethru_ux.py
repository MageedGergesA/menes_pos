"""Drive-thru enterprise workspace — DT-UX1 (queue + operations) and DT-UX2 (cockpit).

The board already showed vehicle identity, kitchen state, payment state and
stage-specific actions before this work; those are asserted here so the
enhancement cannot quietly regress them. What is NEW is the operations strip, one
cross-lane queue ordered by urgency, a real MM:SS timer anchored to the SERVER
clock, and an order panel that docks beside the queue instead of covering it.

The load is 8 cars across 2 lanes, because a queue that only works with two
fixtures is not a queue.
"""
import json
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import MezzeHttpCase

_PRELUDE = r"""
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){} await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label);
}
function assert(cond, msg){ if(!cond) throw new Error('assert failed: ' + msg); }
const ok = () => console.log('test successful');
const rects = (sel) => $$(sel).map(e => e.getBoundingClientRect());
const overlaps = (a,b) => a.left < b.right-2 && a.right > b.left+2
                       && a.top  < b.bottom-2 && a.bottom > b.top+2;
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_drivethru_ux')
class TestDriveThruUx(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        # HttpCase requests commit, so a sibling test's cars would still be in the
        # lane. Start from a known board every time.
        self.env['mezze.drivethru'].sudo().search([]).unlink()
        session = self.open_test_session()
        product = self.env['product.product'].search(
            [('available_in_pos', '=', True)], limit=1)
        plan = [('RED SUV', 1), ('WHITE SEDAN', 2), ('BLACK SUV', 1), ('SILVER HATCH', 2),
                ('BLUE TRUCK', 1), ('GREY SEDAN', 2), ('WHITE VAN', 1), ('RED HATCH', 2)]
        now = fields.Datetime.now()
        self.cars = self.env['mezze.drivethru']
        for i, (vehicle, lane) in enumerate(plan):
            order = self.env['pos.order'].create({
                'session_id': session.id, 'company_id': self.company.id,
                'lines': [(0, 0, {'product_id': product.id, 'qty': 1,
                                  'price_unit': product.list_price,
                                  'price_subtotal': product.list_price,
                                  'price_subtotal_incl': product.list_price})],
                'amount_total': product.list_price, 'amount_tax': 0.0,
                'amount_paid': 0.0, 'amount_return': 0.0})
            # staggered arrivals so "sorted by urgency" is actually testable
            self.cars |= self.env['mezze.drivethru'].create({
                'pos_order_id': order.id, 'lane': lane, 'vehicle': vehicle,
                'state': 'preparing',
                'placed_at': now - timedelta(minutes=(8 - i)),
            })
        self.env.flush_all()

    def _lane(self):
        self.authenticate('admin', 'admin')
        return self.url_open('/mezze/drivethru')

    # ---- DT-UX1: operations + queue ----------------------------------------
    def test_01_the_board_answers_how_the_lane_is_doing(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $('.ops') && $('.ops').innerText.trim(), 'operations strip');
            const t = $('.ops').innerText.toUpperCase();
            for (const k of ['CARS', 'AVG', 'LONGEST', 'TARGET']) {
                assert(t.includes(k), k + ' is on the operations strip (' + t.replace(/\n/g,' ') + ')');
            }
            assert(/\d\d:\d\d/.test(t), 'the metrics are MM:SS, not minutes-only');
            assert(!$('.ops canvas') && !$('.ops svg'), 'no charts on an operating tool');
            ok();
        """), login='admin')

    def test_02_one_queue_ordered_by_urgency_not_lane_columns(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.qrow').length >= 8, 'the whole queue');
            assert(!$('.lane .lanehd'), 'lane kanban columns are gone');
            const secs = $$('.qrow .qtime').map(e => {
                const [m, s] = e.textContent.trim().split(':').map(Number);
                return m*60 + s;
            });
            for (let i = 1; i < secs.length; i++) {
                assert(secs[i] <= secs[i-1] + 1,
                       'longest wait first (' + secs.join(',') + ')');
            }
            // every row still carries its lane, so cross-lane ordering is not confusing
            assert($$('.qrow .qlane').length === $$('.qrow').length, 'every row shows its lane');
            ok();
        """), login='admin')

    def test_03_the_timer_is_prominent_and_ticks(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $('.qtime'), 'a queue row');
            const t = $('.qtime');
            assert(/^\d{2}:\d{2}$/.test(t.textContent.trim()), 'MM:SS (' + t.textContent + ')');
            const size = parseFloat(getComputedStyle(t).fontSize);
            const veh  = parseFloat(getComputedStyle($('.qveh')).fontSize);
            assert(size >= veh, 'the timer is at least as prominent as the vehicle name ('
                   + size + ' vs ' + veh + ')');
            const brand = parseFloat(getComputedStyle($('.brand')).fontSize);
            assert(size >= brand, 'and not smaller than the branding (' + size + ' vs ' + brand + ')');
            const before = t.textContent;
            await new Promise(r => setTimeout(r, 1600));
            assert(t.textContent !== before, 'it ticks without a poll (' + before + ' -> ' + t.textContent + ')');
            ok();
        """), login='admin')

    def test_04_late_is_not_signalled_by_colour_alone(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $('.qrow'), 'a queue row');
            const late = $$('.qrow').find(r => r.className.includes('late'));
            assert(late, 'with an 8-minute-old car, something is late');
            assert(late.querySelector('.qsub').textContent.trim().length > 0,
                   'the row says so in words as well as colour');
            ok();
        """), login='admin')

    # ---- what already worked and must not regress --------------------------
    def test_05_vehicle_kitchen_and_payment_stay_visible(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $('.qrow'), 'a queue row');
            const row = $('.qrow');
            assert(row.querySelector('.qveh').textContent.trim(), 'vehicle identity');
            assert(row.querySelector('.b'), 'kitchen/payment badges');
            assert(row.querySelector('[data-a]'), 'a stage action');
            ok();
        """), login='admin')

    # ---- DT-UX2: the cockpit ------------------------------------------------
    def test_06_taking_an_order_does_not_hide_the_queue(self):
        # The whole point: at the moment the operator is busiest, the lane must
        # still be readable. Below 1100px it is a modal by design, so this asserts
        # the cockpit width only.
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.qrow').length >= 8, 'queue');
            if (window.innerWidth < 1100) { ok(); return; }   // modal by design
            $('#new').click();
            await waitFor(() => $('.sheet.on'), 'order panel');
            await new Promise(r => setTimeout(r, 400));
            const panel = $('.sheet .inner').getBoundingClientRect();
            const covered = rects('.qrow').filter(r => overlaps(r, panel));
            assert(covered.length === 0,
                   'no queue row sits under the order panel (' + covered.length + ' covered)');
            const visible = $$('.qrow').filter(r => {
                const b = r.getBoundingClientRect();
                return b.right <= window.innerWidth + 1 && b.left >= -1;
            });
            assert(visible.length >= 4, 'at least four cars readable while ordering ('
                   + visible.length + ')');
            ok();
        """), login='admin')

    # ---- server truth -------------------------------------------------------
    def test_07_the_server_owns_the_clock(self):
        r = self.url_open(
            '/mezze/api/v1/drivethru/board',
            data=json.dumps({'token': self._shared_token(), 'config_id': self.pos_config.id}),
            headers={'Content-Type': 'application/json'}, timeout=30)
        body = r.json()
        self.assertTrue(body.get('ok'), body)
        self.assertTrue(body.get('now'), 'the board carries the server clock')
        self.assertTrue(body.get('target_seconds'), 'and a configurable target')
        car = body['cars'][0]
        for key in ('placed_at', 'kitchen_ready', 'paid', 'lane', 'vehicle'):
            self.assertIn(key, car, '%s is server-supplied, not invented client-side' % key)

    def test_08_the_target_is_configuration_not_a_hardcoded_sla(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.drivethru_target_seconds', '240')
        self.env.flush_all()
        r = self.url_open(
            '/mezze/api/v1/drivethru/board',
            data=json.dumps({'token': self._shared_token(), 'config_id': self.pos_config.id}),
            headers={'Content-Type': 'application/json'}, timeout=30)
        self.assertEqual(r.json().get('target_seconds'), 240)

    def _shared_token(self):
        icp = self.env['ir.config_parameter'].sudo()
        tok = icp.get_param('mezze_bridge.api_token')
        if not tok:
            tok = 'dtux-tok'
            icp.set_param('mezze_bridge.api_token', tok)
            icp.set_param('mezze_bridge.api_security', 'observe')
            self.env.flush_all()
        return tok
