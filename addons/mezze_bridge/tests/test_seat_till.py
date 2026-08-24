# -*- coding: utf-8 -*-
"""Assigning seats at the till, and splitting by them.

The server side of this is proven in ``test_split_by_seat``. What that cannot prove
is the part that was actually missing: nothing in the product could put a seat on a
line, so "By seat" would have stayed disabled forever no matter how correct the
grouping code was.

Two of these assertions are about restraint rather than function:

* the control is offered only where the order is SEATED at a table — a takeaway
  counter has nobody to ask, and a question with no answer on every line of every
  order is worse than no control at all;
* choosing "Shared" is not choosing seat zero. It clears the assignment, which is
  what a bottle in the middle of the table is.
"""
from odoo.tests import tagged

from .common import MezzeHttpCase

_PRELUDE = r"""
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const phase = () => ($('.mz-app') ? $('.mz-app').dataset.phase : null);
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){} await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label + ' (phase=' + phase() + ')');
}
function assert(cond, msg){ if(!cond) throw new Error('assert failed: ' + msg); }
const ok = () => console.log('test successful');

/** Bind the Register to a table, the way choosing one on the floor does. */
async function sitAtTable(){
  await waitFor(() => window.__mezzeCashier, 'debug handle');
  const root = window.__mezzeCashier.root;
  root.state.table = { id: 1, name: 'T1', floor: 'Main', order_uuid: root.state.orderUuid,
                       guests: 4, seats: 4 };
  await new Promise(r => setTimeout(r, 250));
  return root;
}

async function addLines(n){
  await waitFor(() => $$('.mz-tile').length > 0, 'catalog');
  for (let i = 0; i < (n || 1); i++) {
    $$('.mz-tile')[0].click();
    await new Promise(r => setTimeout(r, 150));
  }
  await waitFor(() => $$('.mz-line').length > 0, 'a line in the cart');
}
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_seat_ui')
class TestSeatTill(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product.write({'available_in_pos': True, 'list_price': 40.0,
                           'taxes_id': [(5, 0, 0)]})
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.env.flush_all()

    def test_01_a_counter_order_is_not_asked_who_is_sitting_where(self):
        # A question with no answer, on every line of every order, is worse than no
        # control at all.
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await addLines(1);
            assert(!$('[data-testid="mz-line-seat"]'),
                   'a counter order was offered a seat control');
            ok();
        """), login='admin')

    def test_02_a_seated_order_offers_it_on_every_line(self):
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await sitAtTable();
            await addLines(2);
            await waitFor(() => $('[data-testid="mz-line-seat"]'), 'the seat control');
            assert($$('[data-testid="mz-line-seat"]').length === $$('.mz-line').length,
                   'not every line can be assigned');
            ok();
        """), login='admin')

    def test_03_choosing_a_seat_marks_the_line(self):
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            const root = await sitAtTable();
            await addLines(1);
            await waitFor(() => $('[data-testid="mz-line-seat"]'), 'the seat control');
            $('[data-testid="mz-line-seat"]').click();
            await waitFor(() => $('[data-testid="mz-seats"]'), 'the seat grid');
            $('[data-seat-choice="2"]').click();
            await waitFor(() => !$('[data-testid="mz-seats"]'), 'it closes on the tap');
            assert(root.order.state.lines[0].seat === 2,
                   'the line did not take the seat: ' + root.order.state.lines[0].seat);
            assert(/2/.test($('[data-testid="mz-line-seat"]').textContent),
                   'the control does not show which seat it holds');
            ok();
        """), login='admin')

    def test_04_shared_clears_the_seat_rather_than_setting_zero(self):
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            const root = await sitAtTable();
            await addLines(1);
            await waitFor(() => $('[data-testid="mz-line-seat"]'), 'the seat control');
            $('[data-testid="mz-line-seat"]').click();
            await waitFor(() => $('[data-testid="mz-seats"]'), 'the seat grid');
            $('[data-seat-choice="1"]').click();
            await new Promise(r => setTimeout(r, 200));
            $('[data-testid="mz-line-seat"]').click();
            await waitFor(() => $('[data-testid="mz-seats"]'), 'the seat grid again');
            $('[data-testid="mz-seats-shared"]').click();
            await new Promise(r => setTimeout(r, 250));
            assert(!root.order.state.lines[0].seat,
                   'shared left a seat number behind: ' + root.order.state.lines[0].seat);
            ok();
        """), login='admin')

    def test_05_the_grid_offers_the_tables_own_seats(self):
        # A four-top does not need anyone to type "3".
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await sitAtTable();
            await addLines(1);
            $('[data-testid="mz-line-seat"]').click();
            await waitFor(() => $('[data-testid="mz-seats"]'), 'the seat grid');
            assert($$('[data-seat-choice]').length === 4,
                   'the grid does not match the table: ' + $$('[data-seat-choice]').length);
            ok();
        """), login='admin')

    def test_06_two_guests_ordering_the_same_dish_stay_two_lines(self):
        # Merging them would put one plate on the bill and lose which of them is
        # paying for it. Asserted on what would be SENT, not on the display.
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            const root = await sitAtTable();
            await addLines(1);
            $('[data-testid="mz-line-seat"]').click();
            await waitFor(() => $('[data-testid="mz-seats"]'), 'grid');
            $('[data-seat-choice="1"]').click();
            await new Promise(r => setTimeout(r, 200));
            $$('.mz-tile')[0].click();          // the same dish again
            await new Promise(r => setTimeout(r, 250));
            const seats = $$('[data-testid="mz-line-seat"]');
            assert(seats.length === 2, 'the second plate merged into the first');
            seats[1].click();
            await waitFor(() => $('[data-testid="mz-seats"]'), 'grid again');
            $('[data-seat-choice="3"]').click();
            await new Promise(r => setTimeout(r, 250));
            const sent = root.order.toSyncLines();
            assert(sent.length === 2, 'the sync merged two guests into one line');
            assert(sent.map(l => l.seat).sort().join(',') === '1,3',
                   'the seats did not survive the grouping: '
                   + JSON.stringify(sent.map(l => l.seat)));
            ok();
        """), login='admin')
