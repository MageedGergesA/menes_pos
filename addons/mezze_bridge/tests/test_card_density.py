"""The Compact / Standard / Training strip, and whether it does anything.

It did not. `setDensity()` wrote `state.density` and a caption read a hardcoded
lookup — `{compact:6, standard:5, training:3}` — while `.mz-grid` was sized by a
single `auto-fill` track (`minmax(154px, 1fr)`) that never referred to the density
at all. So the strip printed "5 cols" over a grid rendering ELEVEN, and pressing
Compact or Training changed the word and nothing else.

That is worse than an absent control. A cashier reads "5 cols · Standard", counts
nine, and learns the screen lies to them; and the one honest signal beside it —
the menu-health card — is on the same rail.

These tests assert the two properties that were broken, in the browser, on the
resolved layout rather than on the source: the grid's track count MOVES when the
card size changes, and the caption states the number actually rendered.
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
const grid = () => $('.mz-grid');
const tracks = () => getComputedStyle(grid()).gridTemplateColumns
                      .split(/\s+/).filter(Boolean).length;
/** The catalogue header's "N cols \u00b7 Mode" line. */
function caption(){
  const el = $$('p,span,div').find(e => /cols\s*\u00b7/.test(e.textContent || ''));
  return el ? el.textContent.replace(/\s+/g,' ').trim() : '';
}
/** The width of one grid track — the DIRECT consequence of the card-size rule.
 *  Asserting on the track COUNT instead looks equivalent and is not: the count
 *  also moves when the grid's own width moves, so a test that clicks the wrong
 *  element and happens to reflow the page passes while proving nothing. That is
 *  exactly what the first version of this file did. */
const trackW = () => parseFloat(
  getComputedStyle(grid()).gridTemplateColumns.split(/\s+/).filter(Boolean)[0]);
const gridW = () => grid().clientWidth;
/** The real control, addressed by its own test id — never by matching visible
 *  text, which also matches unrelated chrome elsewhere on the page. */
function pressSize(key){
  const b = document.querySelector(
    '[data-testid=mz-density] [data-density="' + key + '"]');
  assert(b, 'no card-size control for ' + key);
  b.click();
}
"""


def _js(body):
    return _JS + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_density')
class TestCardDensity(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.default_branch_id', str(cls.pos_config.id))
        ICP.set_param('mezze_bridge.api_security', 'observe')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.product.write({'available_in_pos': True})
        cls.env.flush_all()

    def test_01_the_card_size_actually_changes_the_grid(self):
        """The strip drives the layout, and it drives it the way the design does.

        The design sizes the catalogue by COLUMN COUNT — Compact 6 / Standard 5 /
        Training 4 — not by card width. So the assertion is on the count, and on its
        ORDER: a compact card must never yield fewer columns than a training one.

        An earlier version of this test mutated `data-mz-cards` on the element and
        compared the resolved template. That worked while CSS owned the layout; it
        would now pass or fail on nothing, because ProductGrid sets the template
        inline and an attribute change alone no longer reaches it. Drive the real
        control instead.
        """
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => grid() && $$('.mz-tile').length, 'the catalogue');
            const seen = {};
            for (const key of ['compact', 'standard', 'training']) {
              pressSize(key);
              await new Promise(r => setTimeout(r, 450));
              seen[key] = tracks();
            }
            assert(seen.compact >= seen.standard && seen.standard >= seen.training,
                   'a bigger card did not mean fewer columns: ' + JSON.stringify(seen));
            /* The density can only be OBSERVED when the ceil(sqrt(n)) cap is not the
               binding constraint. On a short menu the cap sits below every target
               (6/5/4), so all three densities correctly resolve to the same count —
               asserting a difference there would be asserting a bug. State the
               condition rather than papering over it with a magic tile count. */
            const cap = Math.ceil(Math.sqrt($$('.mz-tile').length));
            if (cap > 4) {
              assert(new Set(Object.values(seen)).size > 1,
                     'the menu is long enough for the density to show and it changed '
                     + 'nothing: ' + JSON.stringify(seen) + ' (cap ' + cap + ')');
            }
            ok();
        """), login='admin')

    def test_01b_a_short_menu_does_not_spread_across_the_whole_row(self):
        """The design caps the column count at ceil(sqrt(n)).

        Without it, auto-fill makes as many tracks as fit, so a six-item category
        lays out one dish per column — a screen of mostly gutter. With it, six items
        go three-across and read as a menu.
        """
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => grid() && $$('.mz-tile').length, 'the catalogue');
            pressSize('compact');
            await new Promise(r => setTimeout(r, 450));
            const n = $$('.mz-tile').length;
            const cap = Math.ceil(Math.sqrt(n));
            assert(tracks() <= cap,
                   n + ' items laid out in ' + tracks() + ' columns; the cap is ' + cap);
            ok();
        """), login='admin')

    def test_02_the_header_states_the_columns_actually_rendered(self):
        """The caption is measured, not predicted. `auto-fill` means the count
        depends on the width available, so no constant can be right."""
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => grid() && $$('.mz-tile').length, 'the catalogue');
            for (const size of ['compact', 'standard', 'training']) {
              pressSize(size);
              await new Promise(r => setTimeout(r, 450));
              const shown = tracks();
              const cap = caption();
              const m = cap.match(/(\d+)\s*cols/);
              assert(m, 'the catalogue header states no column count: ' + cap);
              assert(parseInt(m[1], 10) === shown,
                     size + ': header says ' + m[1] + ' cols, grid rendered '
                     + shown + ' (' + cap + ')');
            }
            ok();
        """), login='admin')

    def test_03_the_grid_carries_the_chosen_size(self):
        """The choice reaches the element the stylesheet keys on, so the CSS is
        driven by state rather than the state being decorative."""
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => grid() && $$('.mz-tile').length, 'the catalogue');
            pressSize('training');
            await new Promise(r => setTimeout(r, 400));
            assert(grid().getAttribute('data-mz-cards') === 'training',
                   'the grid does not carry the chosen card size: '
                   + grid().getAttribute('data-mz-cards'));
            ok();
        """), login='admin')

    def test_04_the_menu_health_card_prints_one_percent_sign(self):
        """`_t("%s%%", n)` is not sprintf — Odoo's JS translator substitutes `%s`
        and leaves `%%` verbatim, so the rail read "0%%"."""
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $$('.mz-tile').length, 'the catalogue');
            const txt = document.body.innerText;
            assert(!/%%/.test(txt), 'a doubled percent sign is on screen');
            ok();
        """), login='admin')
