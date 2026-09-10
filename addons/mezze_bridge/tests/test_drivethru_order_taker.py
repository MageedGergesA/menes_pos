"""CONV-2b — the Drive-Thru Order Taker is the Mezze Register in drive-thru mode.

The screen this replaces put a 16-car monitoring board across 82% of the canvas and
squeezed ordering into a 440px drawer with two product columns and no order panel at
all. The operator's job at this station is to take food orders, so the workspace is
now the Register's: the same product browser, the same category navigation, the same
order panel, from the same stylesheets — plus the lane context a drive-thru needs.

What is asserted here is the SPLIT and the CONVERGENCE:

* ``?mode=order`` (the default) is the four-pane ordering workspace and carries no
  operations rows;
* ``?mode=ops`` is the original board, with every row action still on it;
* the ordering half is canonical — if a class here stopped matching the Register's,
  these tests would fail rather than the two screens quietly drifting apart.

Money is asserted against the SERVER, not against arithmetic in the page: the panel's
total has to equal what ``/drivethru/quote`` says the same lines cost.
"""
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
const px = (v) => parseFloat(v) || 0;
const W = (s) => { const e=$(s); return e ? Math.round(e.getBoundingClientRect().width) : 0; };

/* The workspace at a chosen width, in an iframe, because a layout contract checked
   only at the test browser's own width is not checked. */
async function at(width, path){
  const fr = document.createElement('iframe');
  fr.setAttribute('width', width);
  fr.style.cssText = 'width:'+width+'px;height:760px;border:0;position:fixed;left:-9999px;top:0';
  fr.src = path || '/mezze/drivethru?mode=order';
  document.body.appendChild(fr);
  await new Promise((res) => { fr.onload = res; });
  const d = fr.contentDocument;
  const t0 = Date.now();
  while (Date.now()-t0 < 20000){
    if (d.querySelector('.mz-tile')) break;
    await new Promise(r=>setTimeout(r,150));
  }
  await new Promise(r=>setTimeout(r,400));
  return fr;
}
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_conv2b')
class TestDriveThruOrderTaker(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        # test_40c compares the lane against the Register at /mezze/pos. Without a
        # default branch that route cannot know WHICH branch is being rung up and
        # answers with the branch chooser (303 -> /mezze/start), so the catalogue it
        # waits for never mounts. The chooser landed after this test did (fe4eddc,
        # 2026-08-19) and this file was not updated with its neighbours.
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(self.pos_config.id))
        self.env['mezze.drivethru'].sudo().search([]).unlink()
        session = self.open_test_session()
        product = self.env['product.product'].search(
            [('available_in_pos', '=', True)], limit=1)
        now = fields.Datetime.now()
        plan = [('RED SUV', 1), ('WHITE SEDAN', 2), ('BLACK SUV', 1), ('SILVER HATCH', 2),
                ('BLUE TRUCK', 1), ('GREY SEDAN', 2), ('WHITE VAN', 1), ('RED HATCH', 2)]
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
            self.cars |= self.env['mezze.drivethru'].create({
                'pos_order_id': order.id, 'lane': lane, 'vehicle': vehicle,
                'state': 'preparing', 'placed_at': now - timedelta(minutes=(8 - i))})
        self.env.flush_all()

    # ---- the role split ------------------------------------------------------
    def test_01_order_mode_is_an_ordering_workspace_not_a_board(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            // WAIT FOR A POLL. Asserting "no board rows" before the first
            // /drivethru/board response is a test of timing, not of structure — a
            // negative control proved this passed even with the board left visible.
            await waitFor(() => $$('.otcar').length >= 8, 'a completed board poll');
            assert(document.body.dataset.mode === 'order', 'order is the default mode');
            // the four panes
            assert($('.otq'), 'a compact queue');
            assert($('.mz-catalog') && $('.mz-grid'), 'the canonical catalogue');
            assert($('.mz-cart'), 'the canonical order panel');
            // and NOT the operations board
            assert($$('.qrow').length === 0,
                   'no operations rows in the order taker (' + $$('.qrow').length + ')');
            assert($$('.qacts').length === 0, 'no row action clusters');
            assert(!$$('.otcar button').length, 'the compact queue carries no row actions');
            ok();
        """), login='admin')

    def test_02_ops_mode_is_the_original_board_with_its_actions(self):
        self.browser_js('/mezze/drivethru?mode=ops', _js(r"""
            await waitFor(() => $$('.qrow').length >= 8, 'the full board');
            assert(document.body.dataset.mode === 'ops', 'ops mode');
            assert($$('.qrow .qacts').length >= 8, 'every row keeps its actions');
            assert($$('[data-a="window"]').length > 0, 'Call forward is here');
            assert($$('[data-a="pay"]').length > 0, 'Take payment is here');
            assert($$('[data-a="cancel"]').length > 0, 'cancel is here');
            assert($('.lanefilter'), 'lane filters are here');
            assert(/CARS/.test($('.ops').innerText.toUpperCase()), 'metrics are here');
            // and the ordering workspace is not
            assert(getComputedStyle($('.ot')).display === 'none', 'no ordering workspace');
            ok();
        """), login='admin')

    def test_03_the_order_taker_can_reach_operations(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $('#openops'), 'the operations control');
            const b = $('#openops');
            assert(b.getBoundingClientRect().height >= 44, 'it meets the touch floor');
            assert(b.textContent.trim().length > 0, 'and it is labelled');
            ok();
        """), login='admin')

    # ---- the ordering half is the Register's -------------------------------
    def test_10_the_product_browser_is_the_canonical_one(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'tiles');
            const cell = $('.mz-tile-cell'), tile = $('.mz-tile');
            assert(cell && tile, 'canonical card markup');
            assert($('.mz-tile__media'), 'the image-led media band');
            assert($('.mz-tile__body') && $('.mz-tile-name') && $('.mz-tile-price'),
                   'canonical name/price band');
            assert($('.mz-tile__quick-add'), 'canonical quick-add');
            // Both numbers below are the FROZEN DESIGN's own literals, read from
            // docs/design-handoff/Mezze POS v3.dc.html — the media at line 210
            // (`aspect-ratio:16/10`) and the gutter at line 207 (`gap:14px`).
            //
            // They used to assert a SQUARE media and an 11px gutter. Neither came
            // from the design: the square card was ours from CONV-1, and the 11px
            // was a measurement recorded in GAP_REGISTER §8b that contradicts the
            // source. Operator ruled the gutter is 14 (2026-09-09).
            //
            // The point of this test is unchanged: the drive-thru board and the
            // Register draw the SAME card from the SAME stylesheet, so whatever
            // these values are, both surfaces must agree on them. That is why the
            // ratio is asserted rather than the pixel height — the card is fluid,
            // its proportion is the contract.
            const media = $('.mz-tile__media').getBoundingClientRect();
            assert(Math.abs(media.width / media.height - 1.6) <= 0.02,
                   'the media is the design 16/10, got ' + (media.width / media.height));
            assert(getComputedStyle($('.mz-grid')).gap === '14px', 'canonical 14px gutter');
            // and NOTHING drive-thru specific replaced them
            assert($$('.mi, .mn, .mp').length === 0, 'no drive-thru product card survives');
            ok();
        """), login='admin')

    def test_11_the_category_navigation_is_the_canonical_one(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-catside__item').length > 1, 'the sidebar');
            const side = $('.mz-catside');
            assert(side, 'the canonical sidebar exists');
            assert($('.mz-catside__branch'), 'branch chip');
            assert($$('.mz-catside__c').length > 1, 'live per-category counts');
            for (const r of $$('.mz-catside__item')) {
                assert(r.getBoundingClientRect().height >= 44, 'a 44px row');
                assert(r.hasAttribute('aria-pressed'), 'selection is announced');
            }
            assert($('.mz-catside__item--active'), 'an active category');
            // the chip strip is the SAME data, and never shown beside the sidebar
            assert($$('#cats .mz-cat').length === $$('.mz-catside__item').length,
                   'one category model, two forms');
            ok();
        """), login='admin')

    def test_12_the_order_panel_is_the_canonical_one(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            assert($('.mz-cart'), 'canonical panel');
            assert($('.mz-cart-head') && $('.mz-cart-count'), 'canonical head + count');
            assert($('.mz-cart-lines'), 'canonical lines region');
            assert($('.mz-cart-foot') && $('.mz-total-row') && $('.mz-total-amt'),
                   'canonical foot + total');
            assert($('.mz-cart-empty'), 'canonical empty state before anything is added');
            const cta = $('#send');
            assert(cta.classList.contains('mz-btn') && cta.classList.contains('mz-btn--confirm'),
                   'the canonical primary action');
            assert(cta.getBoundingClientRect().height >= 44, 'and it is at least 44px');
            // drive-thru workflow, not the till's
            assert(!/charge/i.test(cta.textContent), 'it does not say Charge: ' + cta.textContent);
            // Register CAPABILITIES the drive-thru must not acquire
            for (const s of ['.mz-otype', '.mz-custchip', '.mz-verbs', '.mz-ctx--table']) {
                assert($$(s).length === 0, 'no ' + s + ' in the drive-thru panel');
            }
            ok();
        """), login='admin')

    def test_13_products_operate_the_order(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'tiles');
            $$('.mz-tile')[0].click();
            await waitFor(() => $$('.mz-line').length === 1, 'a line');
            assert($('.mz-cart-count').textContent.trim() === '1', 'the count follows');
            // quantity, through the canonical stepper
            $$('.mz-line-ctrls .mz-stepper__btn')[1].click();
            await waitFor(() => $('.mz-stepper__value').textContent.trim() === '2', 'qty 2');
            assert($('.mz-line-q'), 'the qty badge appears at 2');
            $$('.mz-line-ctrls .mz-stepper__btn')[0].click();
            await waitFor(() => $('.mz-stepper__value').textContent.trim() === '1', 'qty 1');
            // remove
            $('.mz-line-remove').click();
            await waitFor(() => $$('.mz-line').length === 0, 'the line is gone');
            assert($('#send').disabled, 'and an empty order cannot be sent');
            ok();
        """), login='admin')

    def test_14_search_filters_the_same_catalogue(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'tiles');
            const all = $$('.mz-tile').length;
            const s = $('#psearch');
            assert(s && s.classList.contains('mz-search'), 'the canonical search input');
            s.value = $('.mz-tile-name').textContent.trim().slice(0, 4);
            s.dispatchEvent(new Event('input', {bubbles: true}));
            await new Promise(r => setTimeout(r, 300));
            assert($$('.mz-tile').length <= all, 'the grid filtered');
            assert(/\d/.test($('#pcount').textContent), 'the live count reports it');
            assert(!$('#psearchx').hidden, 'and a clear control appears');
            $('#psearchx').click();
            await new Promise(r => setTimeout(r, 300));
            assert($$('.mz-tile').length === all, 'clearing restores the catalogue');
            ok();
        """), login='admin')

    # ---- money: the server's answer -----------------------------------------
    def test_20_the_total_is_the_servers_number(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile')[0], 'tiles');
            $$('.mz-tile')[0].click();
            $$('.mz-tile')[1].click();
            await waitFor(() => $$('.mz-line').length === 2, 'two lines');
            await waitFor(() => !/^—?$/.test($('#ottotal').textContent.trim()), 'a priced total');

            // ask the server the same question, independently of the panel
            const boot = JSON.parse(document.getElementById('mezze-boot').textContent);
            const ids = $$('.mz-tile').slice(0, 2).map(t => +t.dataset.productId);
            const res = await fetch('/mezze/api/v1/drivethru/quote', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token: boot.token, config_id: boot.config_id,
                    lines: ids.map(id => ({product_id: id, qty: 1, attribute_value_ids: []}))})});
            const q = await res.json();
            assert(q.ok, 'the pricing endpoint answered');
            const shown = $('#ottotal').textContent.replace(/[^0-9.]/g, '');
            assert(Math.abs(parseFloat(shown) - q.money.total) < 0.01,
                   'the panel shows the server total (' + shown + ' vs ' + q.money.total + ')');
            // a row exists only if the branch actually charges it
            assert($('#ottax').hidden === !(q.money.tax > 0),
                   'the tax row appears only when there is tax');
            assert($('#otsub').hidden === !(q.money.tax > 0),
                   'and a subtotal only when it differs from the total');
            // per-line money is the server's too
            const line = $('.mz-line-total').textContent.replace(/[^0-9.]/g, '');
            assert(Math.abs(parseFloat(line) - q.lines[0].line_total) < 0.01,
                   'the line total is the server line total');
            ok();
        """), login='admin')

    # ---- New Car is a short pre-step ----------------------------------------
    def test_30_new_car_captures_the_car_and_nothing_else(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $('#new'), 'the workspace');
            $('#new').click();
            await waitFor(() => $('.sheet.on'), 'the pre-step');
            const sheet = $('.sheet');
            assert(sheet.querySelectorAll('.mz-tile').length === 0,
                   'New Car does NOT contain the product catalogue');
            assert(sheet.querySelectorAll('.mz-catalog, .mz-grid, .mz-search').length === 0,
                   'nor the catalogue chrome');
            assert(sheet.querySelectorAll('.lanevar button').length >= 2, 'lane capture');
            assert(sheet.querySelector('#veh'), 'vehicle capture');
            assert(sheet.querySelector('#start'), 'and one way forward');
            ok();
        """), login='admin')

    def test_31_start_order_hands_over_to_the_workspace(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $('#new'), 'the workspace');
            $('#new').click();
            await waitFor(() => $('.sheet.on'), 'the pre-step');
            $$('.lanevar button')[1].click();
            $('#veh').value = 'RED SUV';
            $('#start').click();
            await new Promise(r => setTimeout(r, 300));
            assert(!$('.sheet').classList.contains('on'), 'the pre-step closes');
            assert(document.activeElement === $('#psearch'),
                   'and focus lands in the work, not nowhere');
            assert($('.otctx__veh').textContent.trim() === 'RED SUV', 'the car is named');
            assert($('.otctx__lane').textContent.trim() === 'L2', 'on its lane');
            // DECISION-1: local draft. No order exists yet, so no reference is shown.
            assert(!/#\s*DT|#\d/.test($('.otctx').textContent),
                   'no order reference is invented before one exists: ' + $('.otctx').textContent);
            ok();
        """), login='admin')

    def test_32_the_car_being_served_never_leaves_the_screen(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $('#new'), 'the workspace');
            $('#new').click();
            await waitFor(() => $('.sheet.on'), 'the pre-step');
            $('#veh').value = 'BLUE TRUCK';
            $('#start').click();
            await waitFor(() => $('.otnow__veh'), 'the operating strip');
            assert($('.otnow__veh').textContent.trim() === 'BLUE TRUCK',
                   'the car is in the operating strip');
            assert($('.otctx__veh').textContent.trim() === 'BLUE TRUCK',
                   'and in the order panel header');
            // it survives ordering
            $$('.mz-tile')[0].click();
            await waitFor(() => $$('.mz-line').length === 1, 'a line');
            assert($('.otctx__veh').textContent.trim() === 'BLUE TRUCK',
                   'and it is still there once the order starts');
            ok();
        """), login='admin')

    # ---- layout contracts ----------------------------------------------------
    def test_40_products_are_the_largest_pane_at_desktop(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            for (const w of [1920, 1440, 1280]) {
                const fr = await at(w);
                const d = fr.contentDocument, V = fr.contentWindow;
                const wof = (s) => { const e = d.querySelector(s);
                    return e ? Math.round(e.getBoundingClientRect().width) : 0; };
                const products = wof('.otmenu'), queue = wof('.otq'),
                      cats = wof('.mz-catside'), cart = wof('.mz-cart');
                const cols = V.getComputedStyle(d.querySelector('.mz-grid'))
                              .gridTemplateColumns.split(' ').length;
                fr.remove();
                assert(products > queue, w + ': products must beat the queue ('
                       + products + ' vs ' + queue + ')');
                assert(products > cats && products > cart,
                       w + ': products are the largest pane');
                assert(cols >= 3, w + ': at least three product columns, got ' + cols);
                assert(queue >= 160 && queue <= 220, w + ': queue stays a rail (' + queue + ')');
                assert(cart >= 320, w + ': the order panel keeps its canonical width (' + cart + ')');
            }
            ok();
        """), login='admin')

    def test_40b_the_order_panel_is_the_same_width_as_the_registers(self):
        """One component, one width AT EACH WIDTH — including 1024, where it differed.

        The panel is responsive: it holds the design's 436 basis where the design is
        authored, and steps down below 1400 and again below 1100, because at 1280 a
        437px panel plus the rail and the category column leaves a lane board one
        product column.

        So the invariant is not a constant. It is that the lane board and the
        Register resolve to the SAME width at the same viewport — which is the bug
        this test was written for: the D1 `data-mz-panel-w` family outranks the
        media step, the Register was stamped with the branch's choice and the lane
        board was not, so at 1024 the till showed one width and the lane another.
        Asserting a fixed number would have passed for the wrong reason the moment
        both surfaces drifted together.
        """
        self.browser_js('/mezze/drivethru', _js(r"""
            const html = document.documentElement;
            assert(html.getAttribute('data-mz-panel-w'),
                   'the lane is stamped with the branch panel width');
            assert(html.getAttribute('data-mz-panel'),
                   'and with the panel side');
            const seen = {};
            for (const w of [1920, 1440, 1280, 1024]) {
                const lane = await at(w);
                const laneW = Math.round(
                    lane.contentDocument.querySelector('.mz-cart').getBoundingClientRect().width);
                lane.remove();
                const till = await at(w, '/mezze/pos');
                const tillW = Math.round(
                    till.contentDocument.querySelector('.mz-cart').getBoundingClientRect().width);
                till.remove();
                assert(laneW === tillW,
                       w + ': the lane shows ' + laneW + ' and the till ' + tillW
                       + ' — one component at two widths');
                seen[w] = laneW;
            }
            /* and the steps must actually step: a panel that never changed would
               satisfy the equality above while defeating its purpose. */
            assert(seen[1920] > seen[1280],
                   'the panel does not narrow at all: ' + JSON.stringify(seen));
            ok();
        """), login='admin')

    def _check_40c(self, cases):
        """"/" and Escape are muscle memory, so they must mean the same thing here.

        A cashier trained at the till reaches for "/" to search and Escape to abandon
        the search. On the lane board those keys did nothing, so the same person had to
        reach for the mouse for the same job — the last training-parity gap CONV-2b
        recorded. The SAME assertions run against both documents.
        """
        # A helper handed an empty list would loop zero times and report green:
        # the exact shape of a test that passes without running.
        self.assertTrue(cases, 'no case to check — the split lost its surface')
        for page in cases:
            self.browser_js(page, _js(r"""
                const press = (key, target) => {
                    const ev = new KeyboardEvent('keydown', {key, bubbles:true, cancelable:true});
                    (target || document.body).dispatchEvent(ev);
                    return ev;
                };
                await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
                const box = $('.mz-search');
                assert(box, 'the surface has the canonical search box');
                assert(/press \//.test(box.placeholder || ''),
                       'and it advertises the key: ' + box.placeholder);

                // "/" from anywhere on the ordering surface jumps into search
                document.body.focus();
                const jump = press('/');
                await new Promise(r => setTimeout(r, 150));
                assert(document.activeElement === box, '"/" focuses the search box');
                assert(jump.defaultPrevented, 'and the slash is not typed into it');

                // "/" while already typing is a literal slash, never a hijack
                const typed = press('/', box);
                assert(!typed.defaultPrevented, '"/" inside a field stays a character');

                // Escape abandons the search and gives the screen back
                box.value = 'burg';
                box.dispatchEvent(new Event('input', {bubbles:true}));
                await new Promise(r => setTimeout(r, 250));
                press('Escape', box);
                await new Promise(r => setTimeout(r, 250));
                assert(!$('.mz-search').value, 'Escape clears the query');
                assert(document.activeElement !== $('.mz-search'), 'and releases the field');
                ok();
            """), login='admin')

    def test_40c_the_search_shortcut_works_at_the_till(self):
        self._check_40c(('/mezze/pos',))

    def test_40d_the_search_shortcut_works_in_the_lane(self):
        self._check_40c(('/mezze/drivethru',))

    def test_41_the_category_contract_holds_across_the_breakpoint(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            for (const w of [1024, 1279, 1280, 1440, 1920]) {
                const fr = await at(w);
                const d = fr.contentDocument, V = fr.contentWindow;
                const side = V.getComputedStyle(d.querySelector('.mz-catside')).display;
                const bar  = V.getComputedStyle(d.querySelector('.mz-catbar')).display;
                fr.remove();
                assert(!(side !== 'none' && bar !== 'none'), w + ': both navigations visible');
                assert(!(side === 'none' && bar === 'none'), w + ': no navigation at all');
                assert((w >= 1280) === (side !== 'none'),
                       w + ': the sidebar belongs to >=1280 (' + side + ')');
            }
            ok();
        """), login='admin')

    def test_42_at_1024_the_queue_gets_out_of_the_way(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            const fr = await at(1024);
            const d = fr.contentDocument, V = fr.contentWindow;
            const q = d.querySelector('.otq');
            assert(V.getComputedStyle(q).display === 'none', 'the queue collapses');
            const btn = d.querySelector('#otqbtn');
            assert(V.getComputedStyle(btn).display !== 'none', 'and is one tap away');
            // ...but the car being served does NOT hide with it
            assert(d.querySelector('.otnow__veh'), 'the active car stays in the strip');
            // products and the order remain the workspace
            assert(Math.round(d.querySelector('.otmenu').getBoundingClientRect().width) > 400,
                   'products keep the space');
            assert(Math.round(d.querySelector('.mz-cart').getBoundingClientRect().width) >= 320,
                   'the order panel keeps its width');
            btn.click();
            await new Promise(r => setTimeout(r, 250));
            assert(V.getComputedStyle(q).display !== 'none', 'one tap opens it');
            assert(btn.getAttribute('aria-expanded') === 'true', 'and says so');
            assert(d.querySelectorAll('.otcar').length >= 4, 'with the next cars in it');
            fr.remove();
            ok();
        """), login='admin')

    def test_43_no_horizontal_overflow_at_any_width(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            const bad = [];
            for (const w of [1920, 1440, 1280, 1024]) {
                const fr = await at(w);
                const d = fr.contentDocument;
                const over = d.documentElement.scrollWidth - d.documentElement.clientWidth;
                if (over > 1) bad.push(w + ': ' + over + 'px');
                fr.remove();
            }
            assert(bad.length === 0, 'horizontal overflow: ' + bad.join(', '));
            ok();
        """), login='admin')

    # ---- Arabic + accessibility ---------------------------------------------
    def test_50_the_workspace_mirrors_under_rtl(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the workspace');
            if (window.innerWidth < 1280) { ok(); return; }   // sidebar phase only
            const order = () => ['.otq', '.mz-catside', '.otmenu', '.mz-cart']
                .map(s => $(s).getBoundingClientRect().left);
            const ltr = order();
            assert(ltr[0] < ltr[1] && ltr[1] < ltr[2] && ltr[2] < ltr[3],
                   'LTR: queue, categories, products, order');
            $('#lang').click();
            await waitFor(() => document.documentElement.getAttribute('dir') === 'rtl', 'arabic');
            await new Promise(r => setTimeout(r, 400));
            const rtl = order();
            assert(rtl[0] > rtl[1] && rtl[1] > rtl[2] && rtl[2] > rtl[3],
                   'RTL: the same four panes, mirrored');
            // and it is really Arabic, not a mirrored English screen
            assert(/[؀-ۿ]/.test($('#send').textContent), 'the action is translated');
            assert(/[؀-ۿ]/.test($('.otq__t').textContent), 'the queue is translated');
            assert(/^\d{1,4}:\d{2}$/.test($('.otcar__t').textContent.trim()),
                   'timers stay readable digits: ' + $('.otcar__t').textContent);
            ok();
        """), login='admin')

    def test_51_touch_focus_and_keyboard(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the workspace');
            $$('.mz-tile')[0].click();
            await waitFor(() => $$('.mz-line').length === 1, 'a line');
            const small = $$('button, input, [role=button]').filter(e => {
                const r = e.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && (r.width < 44 || r.height < 44);
            }).map(e => (e.id || e.className) + ' ' + Math.round(e.getBoundingClientRect().width)
                        + 'x' + Math.round(e.getBoundingClientRect().height));
            assert(small.length === 0, 'controls under the touch floor: ' + small.join(', '));
            assert($$('[tabindex]').filter(e => +e.getAttribute('tabindex') > 0).length === 0,
                   'no positive tabindex');
            // the compact queue row is a real control, not a clickable div
            assert($$('.otcar').every(e => e.tagName === 'BUTTON'),
                   'queue rows carry button semantics');
            // and the panes are labelled
            assert($('.otq').getAttribute('aria-label'), 'the queue is labelled');
            assert($('.mz-cart').getAttribute('aria-label'), 'the order panel is labelled');
            ok();
        """), login='admin')

    def test_52_the_compact_queue_reads_from_the_board_it_already_polls(self):
        """Performance: no per-car request may appear behind the new pane."""
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.otcar').length >= 8, 'the compact queue');
            const seen = [];
            const orig = window.fetch;
            window.fetch = function(url, opts){ seen.push(String(url)); return orig.apply(this, arguments); };
            await new Promise(r => setTimeout(r, 2600));   // at least one poll cycle
            window.fetch = orig;
            const board = seen.filter(u => /drivethru\/board/.test(u)).length;
            const perCar = seen.filter(u => /drivethru\/(car|row|status)/.test(u)).length;
            assert(board >= 1 && board <= 3, 'the board is polled once a cycle (' + board + ')');
            assert(perCar === 0, 'and nothing is fetched per car (' + perCar + ')');
            assert($$('.otcar').length >= 8, 'while the queue still shows every car');
            ok();
        """), login='admin')
