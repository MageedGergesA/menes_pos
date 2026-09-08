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

    def test_01_the_card_size_actually_resizes_the_grid(self):
        """The stylesheet genuinely keys on the chosen size.

        Written to be decisive rather than plausible. Earlier drafts clicked the
        control and compared the resolved COLUMN COUNT — which also moves when the
        grid's own width moves, so the first version passed against a stylesheet
        whose rules had been deleted (it was measuring a scrollbar). The second
        compared track WIDTH and still could not separate Standard from Training,
        because at the headless viewport both land on three columns.

        So this changes ONE thing — the attribute — on an otherwise untouched
        element, and reads the resolved template back. No click, no state change,
        no reflow: if `.mz-grid[data-mz-cards=...]` is not in the bundle, all three
        reads are identical and this fails.
        """
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => grid() && $$('.mz-tile').length, 'the catalogue');
            const g = grid();
            const was = g.getAttribute('data-mz-cards');
            const seen = {};
            for (const key of ['compact', 'standard', 'training']) {
              g.setAttribute('data-mz-cards', key);
              // force a style resolve on the same element, same width, same content
              seen[key] = getComputedStyle(g).gridTemplateColumns;
            }
            g.setAttribute('data-mz-cards', was);
            const vals = Object.values(seen);
            assert(new Set(vals).size === 3,
                   'the card size does not reach the stylesheet — all three resolve '
                   + 'the same: ' + JSON.stringify(seen));
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
