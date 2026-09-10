"""Screen 02 — the Floor's canvas, its legend and its side panel.

The design's Floor is a MAP with a fixed 320px panel beside it. Ours was a list of
tables drawn at their real coordinates and nothing else: no way to move around the
plan, no way to look at a table without acting on it, and a legend that named the
four states without saying how many were in each.

Three things here are behaviour rather than decoration:

* the plan PANS and ZOOMS instead of scrolling — a scrollbar on a map hides the
  part of the room you are not looking at;
* a tap SELECTS. It used to navigate straight to the Register for any serviceable
  table, so checking who was on 12 and how long they had been there cost a round
  trip through the till and back;
* the legend counts. A legend that only names the colours says what the map means;
  one that counts them says what the room is doing, which is the question a host
  walked over to answer.
"""
from odoo.tests import tagged

from .common import MezzeHttpCase

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
const ok = () => console.log('test successful');
const canvas = () => $('[data-testid=mz-floor-canvas]');
const plan   = () => $('.mz-canvas');
const sel    = () => $('[data-testid=mz-floor-selection]');
const pct    = () => $('[data-testid=mz-zoom-pct]');
const scaleOf = (el) => {
  const m = /scale\(([\d.]+)\)/.exec(getComputedStyle(el).transform === 'none'
              ? (el.getAttribute('style')||'') : (el.getAttribute('style')||''));
  return m ? parseFloat(m[1]) : 1;
};
async function ready(){ await waitFor(() => $$('.mz-tbl').length, 'the floor plan'); }
"""


def _js(body):
    return _JS + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_floor2')
class TestFloorCanvas(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.default_branch_id', str(cls.pos_config.id))
        ICP.set_param('mezze_bridge.api_security', 'observe')
        cls.env.flush_all()

    def test_01_the_plan_zooms_within_its_range(self):
        """0.7–1.4 in 0.1 steps. Below 0.7 the table numbers stop being readable and
        the plan becomes decoration; above 1.4 a dining room no longer fits."""
        self.browser_js('/mezze/floor', _js(r"""
            await ready();
            const start = scaleOf(plan());
            $('[data-testid=mz-zoom-in]').click();
            await new Promise(r => setTimeout(r, 250));
            assert(scaleOf(plan()) > start, 'zoom in did nothing');
            // walk it to the ceiling and check it stops
            for (let i = 0; i < 12; i++) {
              const b = $('[data-testid=mz-zoom-in]');
              if (b.disabled) { break; }
              b.click();
              await new Promise(r => setTimeout(r, 60));
            }
            const top = scaleOf(plan());
            assert(top <= 1.4001, 'zoom ran past the ceiling: ' + top);
            assert($('[data-testid=mz-zoom-in]').disabled,
                   'the zoom-in control is still live at the ceiling');
            ok();
        """), login='admin')

    def test_02_the_readout_states_the_zoom_and_resets_it(self):
        self.browser_js('/mezze/floor', _js(r"""
            await ready();
            assert(/100\s*%/.test(pct().textContent), 'the plan does not start at 100%');
            $('[data-testid=mz-zoom-in]').click();
            await new Promise(r => setTimeout(r, 250));
            assert(!/100\s*%/.test(pct().textContent),
                   'the readout does not follow the zoom: ' + pct().textContent);
            pct().click();                       // the readout doubles as zoom-to-fit
            await new Promise(r => setTimeout(r, 250));
            assert(/100\s*%/.test(pct().textContent), 'fit did not reset the zoom');
            ok();
        """), login='admin')

    def test_03_fit_also_recentres(self):
        """A fit that left the plan panned off screen would be a button that appears
        to do nothing."""
        self.browser_js('/mezze/floor', _js(r"""
            await ready();
            const c = canvas();
            const r = c.getBoundingClientRect();
            c.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true, clientX:r.left+40, clientY:r.top+40}));
            c.dispatchEvent(new PointerEvent('pointermove', {bubbles:true, clientX:r.left+160, clientY:r.top+120}));
            c.dispatchEvent(new PointerEvent('pointerup',   {bubbles:true}));
            await new Promise(r2 => setTimeout(r2, 250));
            const moved = plan().getAttribute('style') || '';
            assert(/translate\((?!0px,\s*0px)/.test(moved), 'the drag did not pan the plan: ' + moved);
            pct().click();
            await new Promise(r2 => setTimeout(r2, 250));
            assert(/translate\(0px,\s*0px\)/.test(plan().getAttribute('style') || ''),
                   'fit left the plan panned off centre');
            ok();
        """), login='admin')

    def test_04_dragging_a_table_does_not_pan_the_room(self):
        """Panning starts on empty canvas only. Otherwise every mis-swipe on a token
        moves the room instead of opening the check."""
        self.browser_js('/mezze/floor', _js(r"""
            await ready();
            const before = plan().getAttribute('style') || '';
            const tbl = $('.mz-tbl');
            const r = tbl.getBoundingClientRect();
            tbl.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true, clientX:r.left+5, clientY:r.top+5}));
            canvas().dispatchEvent(new PointerEvent('pointermove', {bubbles:true, clientX:r.left+180, clientY:r.top+140}));
            canvas().dispatchEvent(new PointerEvent('pointerup', {bubbles:true}));
            await new Promise(r2 => setTimeout(r2, 250));
            assert((plan().getAttribute('style') || '') === before,
                   'dragging from a table panned the room');
            ok();
        """), login='admin')

    def test_05_a_tap_selects_rather_than_navigating(self):
        self.browser_js('/mezze/floor', _js(r"""
            await ready();
            const here = window.location.pathname;
            $('.mz-tbl').click();
            await new Promise(r => setTimeout(r, 400));
            assert(window.location.pathname === here,
                   'tapping a table left the floor for ' + window.location.pathname);
            assert($('.mz-selcard__no'), 'the side panel says nothing about the tap');
            ok();
        """), login='admin')

    def test_06_the_panel_names_the_table_and_offers_a_verb(self):
        self.browser_js('/mezze/floor', _js(r"""
            await ready();
            const t = $('.mz-tbl');
            const num = t.querySelector('.mz-tbl__num').textContent.trim();
            t.click();
            await new Promise(r => setTimeout(r, 400));
            assert($('.mz-selcard__no').textContent.trim() === num,
                   'the panel is describing a different table');
            assert($$('[data-floor-act]').length,
                   'the panel offers nothing to do with the table');
            ok();
        """), login='admin')

    def test_07_the_selection_can_be_cleared(self):
        self.browser_js('/mezze/floor', _js(r"""
            await ready();
            $('.mz-tbl').click();
            await new Promise(r => setTimeout(r, 350));
            assert($('.mz-selcard__no'), 'nothing got selected');
            $('[data-testid=mz-floor-deselect]').click();
            await new Promise(r => setTimeout(r, 350));
            assert(!$('.mz-selcard__no'), 'the selection could not be cleared');
            assert(sel().textContent.trim().length, 'the empty panel says nothing at all');
            ok();
        """), login='admin')

    def test_08_the_legend_counts_the_states(self):
        """And the counts must agree with the plan, or the legend is decoration."""
        self.browser_js('/mezze/floor', _js(r"""
            await ready();
            const items = $$('.mz-legend__item');
            assert(items.length >= 4, 'the legend lost its states');
            let sum = 0;
            for (const it of items) {
              const n = it.querySelector('.mz-legend__n');
              assert(n, 'a legend row carries no count: ' + it.textContent.trim());
              sum += parseInt(n.textContent, 10) || 0;
            }
            assert(sum === $$('.mz-tbl').length,
                   'the legend counts ' + sum + ' tables and the plan draws '
                   + $$('.mz-tbl').length);
            ok();
        """), login='admin')

    def test_09_every_table_states_its_seat_ratio(self):
        """"2/4" is what a host scanning for somewhere to put a party of three is
        actually comparing."""
        self.browser_js('/mezze/floor', _js(r"""
            await ready();
            for (const t of $$('.mz-tbl')) {
              const r = t.querySelector('[data-testid=mz-table-ratio]');
              assert(r, 'a table token states no seat ratio');
              assert(/^\d+\/\d+$/.test(r.textContent.trim()),
                     'the ratio is not covers/capacity: ' + r.textContent.trim());
            }
            ok();
        """), login='admin')

    def test_10_the_side_panel_is_the_designs_fixed_width(self):
        self.browser_js('/mezze/floor', _js(r"""
            await ready();
            const w = Math.round($('.mz-floorside').getBoundingClientRect().width);
            assert(w === 320, 'the side panel measures ' + w + ', the design measures 320');
            ok();
        """), login='admin')
