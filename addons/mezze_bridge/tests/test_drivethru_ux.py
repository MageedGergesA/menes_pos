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

    # ---- DT-UX3: the payment window ----------------------------------------
    def _pay_js(self, body):
        return _js(r"""
            await waitFor(() => $('.payveh') || $('.payempty'), 'payment window');
            await new Promise(r => setTimeout(r, 300));
        """ + body)

    def test_09_payment_is_a_dedicated_view_not_the_order_taker(self):
        self.browser_js('/mezze/drivethru?mode=payment', self._pay_js(r"""
            assert(document.body.getAttribute('data-mode') === 'payment',
                   'the workstation opens straight into payment');
            const menu = $('#menu');
            const shown = menu && menu.getBoundingClientRect().height > 0;
            assert(!shown, 'the product catalogue is NOT the default workspace');
            assert($('.paycta'), 'there is a primary payment action');
            assert($$('.paycta').length === 1, 'exactly one primary CTA');
            ok();
        """), login='admin')

    def test_10_the_operator_can_identify_the_car_before_tendering(self):
        self.browser_js('/mezze/drivethru?mode=payment', self._pay_js(r"""
            const veh = $('.payveh'), id = $('.payid');
            assert(veh && veh.textContent.trim(), 'vehicle');
            assert(id && /#/.test(id.textContent), 'lane and order id (' + id.textContent + ')');
            // the vehicle must be the loudest thing on the screen, louder than branding
            const v = parseFloat(getComputedStyle(veh).fontSize);
            const brand = parseFloat(getComputedStyle($('.brand')).fontSize);
            assert(v > brand, 'vehicle identity outranks branding (' + v + ' vs ' + brand + ')');
            assert($('.payclock .v'), 'elapsed time is on the payment screen');
            ok();
        """), login='admin')

    def test_11_kitchen_and_payment_are_separate_tracks(self):
        self.browser_js('/mezze/drivethru?mode=payment', self._pay_js(r"""
            const tracks = $$('.track').map(t => t.innerText.replace(/\n/g, ' ').trim());
            assert(tracks.length >= 2, 'two tracks (' + tracks.join(' | ') + ')');
            const joined = tracks.join(' ').toLowerCase();
            assert(/kitchen|مطبخ/.test(joined), 'a kitchen track');
            assert(/payment|دفع/.test(joined), 'a payment track');
            ok();
        """), login='admin')

    def test_12_the_queue_stays_beside_the_payment_workspace(self):
        self.browser_js('/mezze/drivethru?mode=payment', self._pay_js(r"""
            const rows = $$('.qrow');
            assert(rows.length >= 4, 'approaching vehicles are listed (' + rows.length + ')');
            const q = $('.queue').getBoundingClientRect();
            const visible = rows.filter(r => {
                const b = r.getBoundingClientRect();
                return b.top >= q.top - 1 && b.bottom <= q.bottom + 1;
            });
            assert(visible.length >= 4, 'at least four next cars readable (' + visible.length + ')');
            assert($('.qrow[aria-current="true"]'), 'the selected car is marked in the queue');
            ok();
        """), login='admin')

    def test_13_the_recommended_car_is_the_oldest_unpaid(self):
        # Documented rule: longest-waiting car that is still unpaid. A paid car must
        # not be recommended for payment.
        self.browser_js('/mezze/drivethru?mode=payment', self._pay_js(r"""
            const cur = $('.payid').textContent;
            const m = cur.match(/#(\S+)/);
            assert(m, 'the current car has an order id');
            const row = $$('.qrow').find(r => r.getAttribute('aria-current') === 'true');
            assert(row, 'it is the marked row');
            assert(!/PAID|مدفوع/i.test(row.innerText) || /PAYMENT DUE|مستحق/i.test(row.innerText),
                   'the recommendation is an UNPAID car (' + row.innerText.replace(/\n/g,' ') + ')');
            ok();
        """), login='admin')

    def test_14_payment_methods_are_the_branch_s_real_tenders(self):
        self.browser_js('/mezze/drivethru?mode=payment', self._pay_js(r"""
            const buttons = $$('.methods button');
            assert(buttons.length >= 1, 'configured methods are offered');
            for (const b of buttons) {
                const r = b.getBoundingClientRect();
                assert(r.height >= 48, 'tender targets are generous (' + r.height + ')');
                assert(b.textContent.trim(), 'each has an accessible name');
            }
            ok();
        """), login='admin')

    def test_15_a_failure_leaves_the_order_unpaid_and_offers_a_way_out(self):
        # Force the server to refuse, then assert the screen says so operationally
        # and does NOT mark the car paid.
        self.browser_js('/mezze/drivethru?mode=payment', self._pay_js(r"""
            const orig = window.fetch;
            window.fetch = function(u, o){
                if (String(u).includes('/drivethru/stage')) {
                    return Promise.resolve(new Response(
                        JSON.stringify({ok:false, error:'payment_failed', message:'Card declined'}),
                        {status:200, headers:{'Content-Type':'application/json'}}));
                }
                return orig.apply(this, arguments);
            };
            $('#docomplete').click();
            await waitFor(() => $('.payfail'), 'failure state');
            const txt = $('.payfail').innerText;
            assert(!/something went wrong/i.test(txt), 'operational language, not a generic error');
            assert($$('.payfail button').length >= 2, 'try again AND another method');
            assert($('.payveh').textContent.trim(), 'the vehicle is still identified');
            assert($('.qrow'), 'the queue is still there');
            window.fetch = orig;
            ok();
        """), login='admin')

    # ---- PRE-FLIGHT 2: payment must not recommend a car that is not at the window
    def test_16_payment_prefers_the_car_actually_at_the_window(self):
        # `at_window` means the car has physically reached the window ("settled when
        # the car reaches the window"). Recommending by age alone could put a vehicle
        # on screen that the operator cannot see — that is how the wrong car gets
        # charged. A younger car AT the window outranks an older one still in lane.
        oldest = self.cars[0]          # 8 minutes old, state 'preparing'
        youngest = self.cars[-1]       # 1 minute old
        youngest.write({'state': 'at_window'})
        self.env.flush_all()
        self.browser_js('/mezze/drivethru?mode=payment', _js(r"""
            await waitFor(() => $('.payveh'), 'payment window');
            await new Promise(r => setTimeout(r, 400));
            const id = $('.payid').textContent;
            assert(/%s/.test(id), 'the car AT THE WINDOW is recommended, not the oldest (' + id + ')');
            assert(!$('[data-testid="not-at-window"]'), 'and it is not flagged as un-called');
            ok();
        """ % youngest.pos_order_id.tracking_number or youngest.pos_order_id.pos_reference),
            login='admin')

    def test_17_a_car_not_called_forward_is_flagged(self):
        # With nobody called forward the oldest unpaid car is still offered — silence
        # would be worse — but the screen says it has not been called forward, so the
        # operator confirms rather than assumes.
        self.env['mezze.drivethru'].search([]).write({'state': 'preparing'})
        self.env.flush_all()
        self.browser_js('/mezze/drivethru?mode=payment', _js(r"""
            await waitFor(() => $('.payveh'), 'payment window');
            await new Promise(r => setTimeout(r, 400));
            assert($('[data-testid="not-at-window"]'), 'the qualification is shown');
            ok();
        """), login='admin')

    # ---- DT-UX4: pickup -----------------------------------------------------
    def test_18_pickup_is_its_own_mode_and_shows_neither_menu_nor_tender(self):
        # DT-UX5: a car must be AT THE WINDOW for pickup to have a subject, so the
        # fixture puts one there. Without that the screen correctly shows
        # "no vehicle at the window" and offers Call forward instead of a handoff.
        self.cars[0].write({'state': 'at_window'})
        self.env.flush_all()
        self.browser_js('/mezze/drivethru?mode=pickup', _js(r"""
            await waitFor(() => $('.payveh') || $('.nowindow'), 'pickup');
            assert(document.body.getAttribute('data-mode') === 'pickup', 'pickup mode');
            const menu = $('#menu');
            assert(!(menu && menu.getBoundingClientRect().height > 0), 'no product catalogue');
            assert($$('.methods button').length === 0, 'no tender controls');
            assert($('#dohandoff'), 'a handoff action for the car at the window');
            ok();
        """), login='admin')

    def test_18b_with_no_car_at_the_window_pickup_says_so(self):
        # The label must not overstate physical truth: nothing is "current" when no
        # car has been called forward. Two facts, not one misleading one.
        self.env['mezze.drivethru'].search([]).write({'state': 'ready'})
        self.env.flush_all()
        self.browser_js('/mezze/drivethru?mode=pickup', _js(r"""
            await waitFor(() => $('.nowindow'), 'the honest empty state');
            assert(!$('#dohandoff'), 'nothing to hand off');
            assert($('#callfwd'), 'and a way to call the next car forward');
            assert($('.nextcall .payveh').textContent.trim(), 'which names that car');
            ok();
        """), login='admin')

    def test_19_an_unknown_mode_falls_back_instead_of_rendering_nothing(self):
        self.browser_js('/mezze/drivethru?mode=wat', _js(r"""
            await waitFor(() => $('.qrow'), 'the board still renders');
            assert(document.body.getAttribute('data-mode') === 'order',
                   'unknown mode falls back to order taking, not an empty screen');
            ok();
        """), login='admin')

    def test_20_the_blocked_reason_is_readable_outside_the_disabled_button(self):
        # A disabled control takes no focus, so the reason must not live only on it.
        # at the window, but the kitchen is still working — the case the CTA blocks
        self.env['mezze.drivethru'].search([]).write({'state': 'preparing'})
        self.cars[0].write({'state': 'at_window'})
        self.env.flush_all()
        self.browser_js('/mezze/drivethru?mode=pickup', _js(r"""
            await waitFor(() => $('#dohandoff'), 'pickup');
            await new Promise(r => setTimeout(r, 400));
            const cta = $('#dohandoff');
            assert(cta.disabled, 'an ineligible car cannot be handed off from the UI');
            const id = cta.getAttribute('aria-describedby');
            assert(id && document.getElementById(id), 'the CTA points at its reason');
            const reason = document.getElementById(id).innerText.trim();
            assert(reason.length > 0, 'and that reason is visible text (' + reason + ')');
            assert(!/unknown|error|409/i.test(reason), 'operational language, not a status code');
            ok();
        """), login='admin')
