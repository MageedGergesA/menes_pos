"""The order panel's footer, and what it says about the verbs on it.

The design puts THREE verbs on the panel — Send to kitchen, Park, Bill — and
everything else behind More, under four headings (Order, Fire, Cash, Danger).
We shipped all sixteen as one flat grid.

That is not a smaller version of the design's footer; it is a different
instrument. Sixteen equally-weighted tiles state that voiding an order and
opening the drawer are the same kind of decision, and they bury the two verbs a
cashier touches on every single check somewhere in the middle of the other
fourteen. The design's hierarchy is the feature.

`Fire` is relabelled `Send to kitchen` for the same reason: it names what
happens rather than the trade word for it.
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
const foot  = () => $('[data-testid=mz-panel-footer]');
const sheet = () => $('[data-testid=mz-more-sheet]');
const more  = () => $('[data-testid=mz-more]');
const footVerbs = () => $$('[data-testid=mz-panel-footer] [data-verb]').map(b=>b.dataset.verb);
/** Ring something up so the cart is non-empty and the verbs are live. */
async function ringUp(){
  await waitFor(() => $$('.mz-tile').length, 'the catalogue');
  $$('.mz-tile')[0].click();
  await waitFor(() => $$('.mz-line').length, 'a line');
  await new Promise(r => setTimeout(r, 300));
}
"""


def _js(body):
    return _JS + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_panel')
class TestPanelFooter(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.default_branch_id', str(cls.pos_config.id))
        ICP.set_param('mezze_bridge.api_security', 'observe')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.product.write({'available_in_pos': True})
        cls.env.flush_all()

    def test_01_the_panel_carries_only_the_designs_three_verbs_plus_more(self):
        self.browser_js('/mezze/pos', _js(r"""
            await ringUp();
            assert(foot(), 'the panel has no footer');
            const verbs = footVerbs();
            assert(verbs.length <= 3,
                   'the footer carries more than the design\'s three verbs: ' + verbs);
            for (const v of verbs) {
              assert(['fire','park','bill'].includes(v),
                     v + ' is on the panel; the design puts it behind More');
            }
            assert(more(), 'there is no More control, so the rest are unreachable');
            ok();
        """), login='admin')

    def test_02_more_is_closed_until_it_is_asked_for(self):
        """A sheet that starts open is just the flat grid with a heading on it."""
        self.browser_js('/mezze/pos', _js(r"""
            await ringUp();
            assert(sheet(), 'no More sheet exists');
            assert(sheet().hasAttribute('hidden'), 'the More sheet starts open');
            assert(more().getAttribute('aria-expanded') === 'false',
                   'More does not report itself closed');
            ok();
        """), login='admin')

    def test_03_more_opens_and_the_control_says_so(self):
        """aria-expanded and visibility must not be able to disagree — a screen
        reader is told the same thing the screen shows."""
        self.browser_js('/mezze/pos', _js(r"""
            await ringUp();
            more().click();
            await new Promise(r => setTimeout(r, 250));
            assert(!sheet().hasAttribute('hidden'), 'More did not open the sheet');
            assert(more().getAttribute('aria-expanded') === 'true',
                   'the sheet is open and More still reports closed');
            more().click();
            await new Promise(r => setTimeout(r, 250));
            assert(sheet().hasAttribute('hidden'), 'More did not close the sheet');
            assert(more().getAttribute('aria-expanded') === 'false',
                   'the sheet is shut and More still reports open');
            ok();
        """), login='admin')

    def test_04_the_sheet_is_grouped_the_way_the_design_groups_it(self):
        self.browser_js('/mezze/pos', _js(r"""
            await ringUp();
            more().click();
            await new Promise(r => setTimeout(r, 250));
            const groups = $$('[data-testid=mz-more-sheet] [data-group]')
                             .map(g => g.dataset.group);
            assert(groups.length, 'the sheet has no groups at all');
            for (const g of groups) {
              assert(['order','fire','cash','danger'].includes(g),
                     'unknown group in the More sheet: ' + g);
            }
            // every group rendered must carry at least one verb
            for (const el of $$('[data-testid=mz-more-sheet] [data-group]')) {
              assert(el.querySelectorAll('[data-verb]').length,
                     'the sheet renders an empty "' + el.dataset.group + '" heading');
            }
            ok();
        """), login='admin')

    def test_05_the_destructive_verbs_are_under_danger(self):
        """Refund and Void must not sit next to a routine verb."""
        self.browser_js('/mezze/pos', _js(r"""
            await ringUp();
            more().click();
            await new Promise(r => setTimeout(r, 250));
            for (const key of ['refund','void']) {
              const b = $('[data-testid=mz-more-sheet] [data-verb=' + key + ']');
              if (!b) { continue; }   // this branch may not offer it at all
              const g = b.closest('[data-group]');
              assert(g && g.dataset.group === 'danger',
                     key + ' is filed under "' + (g && g.dataset.group) + '"');
            }
            ok();
        """), login='admin')

    # ── the per-line overflow ────────────────────────────────────────────
    def test_07_the_line_row_carries_only_note_and_more(self):
        """The design shows the stepper, Edit, Note and `⋯` on a line. Ours put
        Discount, Comp, Assign seat, Type quantity and Lot on the row as well —
        seven controls in a 436px column, which wrapped the row and gave comping
        an item the same visual weight as the quantity stepper."""
        self.browser_js('/mezze/pos', _js(r"""
            await ringUp();
            const line = $('.mz-line');
            assert(line, 'no line on the check');
            /* Off the ROW — they live in the overflow now, which is inside the
               line but is not the control row. Asserting absence from the document
               would be wrong: they are still rendered, just not on the row. */
            const row = line.querySelector('.mz-line-ctl') || line.firstElementChild;
            for (const gone of ['mz-line-discount', 'mz-line-comp', 'mz-line-seat',
                                'mz-line-numpad', 'mz-line-lot']) {
              const el = line.querySelector('[data-testid=' + gone + ']');
              assert(!el || el.closest('[data-testid=mz-line-menu]'),
                     gone + ' is still on the line row; the design puts it behind the overflow');
            }
            assert($('[data-testid=mz-line-more]'), 'the line has no overflow control');
            ok();
        """), login='admin')

    def test_08_the_line_overflow_opens_inline_and_says_so(self):
        """Inline beneath the line, not floated over the next one — and the control
        reports its own state so a screen reader is told what the screen shows."""
        self.browser_js('/mezze/pos', _js(r"""
            await ringUp();
            const more = $('[data-testid=mz-line-more]');
            assert(more.getAttribute('aria-expanded') === 'false',
                   'the line overflow starts open');
            const menu = $('[data-testid=mz-line-menu]');
            assert(menu, 'the line has no overflow menu at all');
            /* Present but hidden, exactly as the More sheet is: [hidden] rather
               than a t-if, so the control's aria-expanded and the element's
               visibility cannot disagree, and so a test about what a control DOES
               need not first drive the layout that reveals it. */
            assert(menu.hasAttribute('hidden'), 'the overflow starts visible');
            more.click();
            await new Promise(r => setTimeout(r, 250));
            assert(!menu.hasAttribute('hidden'), 'the overflow did not open');
            assert(more.getAttribute('aria-expanded') === 'true',
                   'the menu is open and the control still reports closed');
            /* inline: the menu must sit INSIDE the line it belongs to, so it can
               never cover a different line's controls */
            assert($('.mz-line').contains(menu),
                   'the menu is not inside its own line');
            ok();
        """), login='admin')

    def test_09_the_manager_gated_rows_are_marked(self):
        """Discount and Comp ask for a manager. The design marks them with a lock,
        so a cashier knows before they tap rather than after."""
        self.browser_js('/mezze/pos', _js(r"""
            await ringUp();
            $('[data-testid=mz-line-more]').click();
            await new Promise(r => setTimeout(r, 250));
            const rows = $$('[data-testid=mz-line-menu] [data-line-act]');
            assert(rows.length, 'the overflow is empty');
            for (const key of ['discount', 'comp']) {
              const b = $('[data-line-act=' + key + ']');
              if (!b) { continue; }   // this branch may not offer it
              assert(b.querySelector('.mz-linemenu__lock'),
                     key + ' asks for a manager and is not marked as gated');
            }
            ok();
        """), login='admin')

    def test_10_choosing_an_action_closes_the_overflow(self):
        """A menu that stays open over the line it just acted on hides the result."""
        self.browser_js('/mezze/pos', _js(r"""
            await ringUp();
            $('[data-testid=mz-line-more]').click();
            await new Promise(r => setTimeout(r, 250));
            const first = $$('[data-testid=mz-line-menu] [data-line-act]')[0];
            assert(first, 'the overflow is empty');
            first.click();
            await new Promise(r => setTimeout(r, 350));
            const m = $('[data-testid=mz-line-menu]');
            assert(!m || m.hasAttribute('hidden'),
                   'the overflow stayed open after acting');
            ok();
        """), login='admin')

    def test_11_the_guest_row_uses_the_designs_wording(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $$('.mz-tile').length, 'the catalogue');
            const chip = $('.mz-custchip');
            assert(chip, 'no guest row on the panel');
            assert(/Attach a guest/i.test(chip.innerText),
                   'the guest row reads: ' + chip.innerText.trim());
            ok();
        """), login='admin')

    def test_06_the_fire_verb_is_named_for_what_it_does(self):
        self.browser_js('/mezze/pos', _js(r"""
            await ringUp();
            const b = $('[data-testid=mz-panel-footer] [data-verb=fire]');
            assert(b, 'Send to kitchen is not on the panel');
            assert(/kitchen/i.test(b.innerText),
                   'the verb is still trade jargon: ' + b.innerText.trim());
            ok();
        """), login='admin')
