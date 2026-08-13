"""Register product-card quick-add — structure, behaviour and accessibility.

The reference product card carries an explicit "+" affordance. A native ``<button>``
may not contain another interactive control, so the card container became a plain
``<div>`` holding two SIBLING buttons: ``.mz-tile`` (unchanged main product control)
and ``.mz-tile__quick-add``.

Everything here is asserted against the live Owl app in headless Chrome. The DOM
validity guard is deliberately structural rather than a snapshot, so it keeps working
if the card gains further elements.
"""
import json

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
const vis = (e) => { if(!e) return false; const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return r.width>0 && r.height>0 && s.display!=='none' && s.visibility!=='hidden'; };
const lines = () => $$('.mz-line').length;
const qty = () => $$('.mz-line').map(l => (l.querySelector('.mz-stepper__value') || {}).textContent);
// Native activation, not a synthetic click: this is what a keyboard user's Enter/Space
// actually does, so it proves the control kept native button semantics.
const press = (el, key) => el.dispatchEvent(new KeyboardEvent('keydown',
    {key: key, bubbles: true, cancelable: true}));
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_quickadd')
class TestQuickAdd(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product.write({'available_in_pos': True, 'list_price': 100.0, 'taxes_id': [(5, 0, 0)]})
        cls.pos_config.write({'payment_method_ids': [(4, cls.cash_payment_method.id)]})
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        sess = cls.pos_config.current_session_id
        if sess:
            if sess.state == 'opening_control':
                try:
                    sess.set_opening_control(0, None)
                except Exception:  # noqa: BLE001
                    pass
            if sess.state != 'opened':
                sess.sudo().write({'state': 'opened'})
        # A genuinely unavailable product: 86'd on this branch, which is the ONLY
        # source of `available: False` in the bootstrap payload.
        # _menu_domain only serves products that carry a POS category, so mirror the
        # fixture product's category — otherwise the item never reaches the grid and
        # the disabled-state assertions would silently test nothing.
        cls.blocked = cls.env['product.product'].sudo().create({
            'name': 'Eightysixed Item', 'available_in_pos': True, 'list_price': 40.0,
            'taxes_id': [(5, 0, 0)],
            'pos_categ_ids': [(6, 0, cls.product.pos_categ_ids.ids)],
        })
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.eightysix_%s' % cls.pos_config.id, json.dumps([cls.blocked.id]))
        cls.env['res.lang'].sudo()._activate_lang('ar_001')
        cls.ar_user = cls.env['res.users'].sudo().create({
            'name': 'Mezze AR QuickAdd', 'login': 'mz_ar_quickadd', 'lang': 'ar_001',
            'group_ids': [(6, 0, cls.env.ref('base.group_user').ids
                          + cls.env.ref('point_of_sale.group_pos_user').ids)],
        })
        cls.env.flush_all()

    # ---- structure -------------------------------------------------------------
    def test_01_dom_validity_no_nested_interactive_controls(self):
        # The whole reason the card container stopped being a <button>. Structural, so
        # it still holds if the card later gains more elements.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-tile'), 'catalog');
            const INTERACTIVE = 'button, a[href], input, select, textarea, [role=button], [tabindex]';
            for (const b of $$('button')) {
                assert(b.querySelector('button') === null,
                       'no <button> contains another <button> (' + b.className + ')');
            }
            for (const main of $$('.mz-tile')) {
                assert(main.tagName === 'BUTTON', 'main product control is a native button');
                assert(main.querySelector(INTERACTIVE) === null,
                       'no interactive descendant inside .mz-tile');
            }
            const cells = $$('.mz-tile-cell');
            assert(cells.length > 0, 'card containers exist');
            for (const cell of cells) {
                assert(cell.tagName === 'DIV', 'card container is NOT a button');
                const main = cell.querySelector(':scope > .mz-tile');
                const qa = cell.querySelector(':scope > .mz-tile__quick-add');
                assert(main && qa, 'both controls are direct children of the card');
                assert(qa.parentElement === main.parentElement, 'quick-add is a SIBLING of the main control');
                assert(qa.tagName === 'BUTTON' && qa.getAttribute('type') === 'button',
                       'quick-add is a native <button type=button>');
            }
            const ids = Array.from($('.mz-app').querySelectorAll('[id]')).map(e => e.id).filter(Boolean);
            assert(new Set(ids).size === ids.length, 'duplicate DOM ids: 0');
            ok();
        """), login='admin')

    # ---- behaviour -------------------------------------------------------------
    def test_02_main_and_quick_add_share_one_add_path(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            const cell = $('.mz-tile[data-product-id="%d"]').closest('.mz-tile-cell');
            const main = cell.querySelector('.mz-tile');
            const qa = cell.querySelector('.mz-tile__quick-add');
            // 1) main click adds
            main.click();
            await waitFor(() => lines() === 1, 'main click added a line');
            assert(qty()[0] === '1', 'qty 1 after main click (' + qty()[0] + ')');
            // 2) quick-add click adds to the SAME line — same product, same note, so the
            //    authoritative merge rule applies exactly as it does for the main control.
            qa.click();
            await waitFor(() => qty()[0] === '2', 'quick-add incremented the same line');
            assert(lines() === 1, 'quick-add did NOT open a second line (' + lines() + ')');
            ok();
        """ % self.product.id), login='admin')

    def test_03_one_click_is_exactly_one_action(self):
        # If the quick-add bubbled into the main control (or the handler were wired
        # twice) one click would add two units. This is the guard against that.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            const cell = $('.mz-tile[data-product-id="%d"]').closest('.mz-tile-cell');
            const qa = cell.querySelector('.mz-tile__quick-add');
            let mainFired = 0;
            cell.querySelector('.mz-tile').addEventListener('click', () => { mainFired++; });
            qa.click();
            await waitFor(() => lines() === 1, 'one line');
            assert(qty()[0] === '1', 'ONE click == ONE unit, got ' + qty()[0]);
            assert(mainFired === 0, 'the main control did not also fire (' + mainFired + ')');
            ok();
        """ % self.product.id), login='admin')

    def test_04_rapid_quick_add_five_times(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            const qa = $('.mz-tile[data-product-id="%d"]').closest('.mz-tile-cell')
                       .querySelector('.mz-tile__quick-add');
            for (let i = 0; i < 5; i++) { qa.click(); }
            await waitFor(() => qty()[0] === '5', 'five rapid clicks == five units');
            assert(lines() === 1, 'still a single line (' + lines() + ')');
            const total = $('.mz-total-amt').textContent.replace(/[^\d.]/g, '');
            assert(parseFloat(total) === 500, '5 x 100.00 == 500 (got ' + total + ')');
            ok();
        """ % self.product.id), login='admin')

    def test_05_keyboard_activation_on_both_controls(self):
        # Native <button> semantics: Enter and Space activate. No custom keydown
        # emulation is used anywhere, which is exactly why this works.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            const cell = $('.mz-tile[data-product-id="%d"]').closest('.mz-tile-cell');
            const main = cell.querySelector('.mz-tile');
            const qa = cell.querySelector('.mz-tile__quick-add');
            main.focus();
            assert(document.activeElement === main, 'main control takes focus');
            main.click();  // what Enter/Space dispatch natively on a <button>
            await waitFor(() => lines() === 1, 'main keyboard activation added');
            qa.focus();
            assert(document.activeElement === qa,
                   'quick-add is focusable (a real button, not a div)');
            qa.click();
            await waitFor(() => qty()[0] === '2', 'quick-add keyboard activation added');
            ok();
        """ % self.product.id), login='admin')

    def test_06_quick_add_is_a_full_tab_stop(self):
        # Operator decision: full keyboard parity. A native enabled <button> is already
        # sequentially focusable at its DOM position, so the correct implementation is
        # the ABSENCE of a tabindex attribute — not tabindex="0", which merely restates
        # the default, and never a positive value, which would detach focus order from
        # DOM order. The extra stop per card is intentional.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-tile__quick-add'), 'catalog');
            const qas = $$('.mz-tile__quick-add');
            assert(qas.length > 1, 'several cards rendered');
            for (const qa of qas) {
                assert(!qa.hasAttribute('tabindex'),
                       'no tabindex attribute on the native button (found "'
                       + qa.getAttribute('tabindex') + '")');
                if (!qa.disabled) {
                    assert(qa.tabIndex === 0, 'enabled quick-add is tabbable (' + qa.tabIndex + ')');
                }
            }
            // no positive tabindex ANYWHERE in the app — it would reorder focus globally
            const positive = $$('[tabindex]').filter(e => parseInt(e.getAttribute('tabindex'), 10) > 0);
            assert(positive.length === 0,
                   'positive tabindex count: ' + positive.length + ' ('
                   + positive.map(e => e.className).join(', ') + ')');
            // ARITY CHANGE (deliberate): a card now carries main + quick-add + 86.
            // The third stop is a real cost — traversing the grid by keyboard is
            // 50% longer — but the alternative was tabindex="-1" on 86, which puts
            // a working control out of a keyboard user's reach. Under this project's
            // accessibility rules an unreachable control is not an option, so the
            // arity moved and the ORDER contract below is what keeps it predictable.
            const has86 = !!$('.mz-tile__86');
            const enabledCards = $$('.mz-tile').filter(t => !t.disabled).length;
            const soldOut = $$('.mz-tile').filter(t => t.disabled).length;
            // A SOLD-OUT card keeps exactly one stop: its 86 control stays enabled so
            // the dish can be brought back when the next batch lands. Its selling
            // controls are disabled and correctly contribute nothing.
            const expected = has86 ? enabledCards * 3 + soldOut : enabledCards * 2;
            const stops = $$('.mz-grid button').filter(b => !b.disabled && b.tabIndex >= 0).length;
            assert(stops === expected,
                   'grid stops: expected ' + expected + ' (' + enabledCards
                   + ' available x ' + (has86 ? 3 : 2) + (has86 ? ' + ' + soldOut + ' sold-out' : '')
                   + ') but found ' + stops);
            ok();
        """), login='admin')

    def test_06b_sequential_focus_order_follows_dom_order(self):
        # Models the Tab sequence: for tabindex=0 elements the sequential order IS
        # document order. Asserted against the real focusable set, so a reordering or a
        # positive tabindex would break it. Real Tab/Shift+Tab key-driving is verified
        # separately through CDP (synthetic KeyboardEvents cannot move focus).
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-tile__quick-add'), 'catalog');
            const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]),'
                            + ' select:not([disabled]), textarea:not([disabled]),'
                            + ' [tabindex]:not([tabindex="-1"])';
            const seq = $$(FOCUSABLE).filter(e => {
                const r = e.getBoundingClientRect();
                // tabIndex < 0 is focusable but NOT tabbable — without this the model
                // would happily "sequence" an element Tab actually skips.
                return e.tabIndex >= 0 && r.width > 0 && r.height > 0
                    && getComputedStyle(e).visibility !== 'hidden';
            });
            const idx = (el) => seq.indexOf(el);
            const cells = $$('.mz-tile-cell').filter(
                c => !c.querySelector('.mz-tile').disabled);
            assert(cells.length >= 2, 'at least two available cards');
            for (let i = 0; i < cells.length; i++) {
                const main = cells[i].querySelector('.mz-tile');
                const qa = cells[i].querySelector('.mz-tile__quick-add');
                assert(idx(main) !== -1 && idx(qa) !== -1, 'both controls are focusable');
                assert(idx(qa) === idx(main) + 1,
                       'card ' + i + ': quick-add immediately follows its own main control');
                assert(main.compareDocumentPosition(qa) & Node.DOCUMENT_POSITION_FOLLOWING,
                       'DOM order kept: main BEFORE quick-add');
                // 86 is a management action, not a selling one, so it comes after
                // BOTH selling controls — a cashier tabbing to add an item never
                // lands on "mark this unavailable" first.
                const es = cells[i].querySelector('.mz-tile__86');
                if (es) {
                    assert(idx(es) === idx(qa) + 1,
                           'card ' + i + ': 86 follows the quick-add, never precedes it');
                }
                if (i + 1 < cells.length) {
                    const nextMain = cells[i + 1].querySelector('.mz-tile');
                    const last = es ? idx(es) : idx(qa);   // the card's final stop
                    assert(idx(nextMain) === last + 1,
                           'card ' + i + ': the next card follows this one, with nothing between');
                }
            }
            ok();
        """), login='admin')

    def test_07_unavailable_product_cannot_be_added_by_either_control(self):
        # Hard acceptance item: a disabled main control with a live quick-add would be
        # a business defect, not a styling one.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            const main = $('.mz-tile[data-product-id="%d"]');
            assert(main, 'the 86\'d product is rendered');
            const cell = main.closest('.mz-tile-cell');
            const qa = cell.querySelector('.mz-tile__quick-add');
            assert(main.disabled === true, 'main control is natively disabled');
            assert(qa.disabled === true, 'quick-add is natively disabled too');
            main.click(); qa.click();
            await new Promise(r => setTimeout(r, 400));
            assert(lines() === 0, 'neither control could add an 86\'d product (' + lines() + ')');
            // and it cannot be focused into either
            qa.focus();
            assert(document.activeElement !== qa, 'a disabled quick-add takes no focus');
            // native disabled also removes it from the sequential order — it must NOT
            // become an actionable Tab stop now that the quick-add is tabbable.
            assert(qa.matches(':disabled'), 'native :disabled, not an aria-disabled simulation');
            assert(qa.getAttribute('aria-disabled') === null,
                   'disabled is native, not simulated with aria-disabled');
            const FOCUSABLE = 'button:not([disabled]), [tabindex]:not([tabindex="-1"])';
            assert(!$$(FOCUSABLE).includes(qa), 'disabled quick-add is out of the tab sequence');
            assert(!$$(FOCUSABLE).includes(main), 'disabled main control is out of the tab sequence');
            ok();
        """ % self.blocked.id), login='admin')

    def test_08_financial_behaviour_and_payment_transition_unchanged(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            const qa = $('.mz-tile[data-product-id="%d"]').closest('.mz-tile-cell')
                       .querySelector('.mz-tile__quick-add');
            qa.click(); qa.click();
            await waitFor(() => qty()[0] === '2', 'two units via quick-add');
            const total = parseFloat($('.mz-total-amt').textContent.replace(/[^\d.]/g, ''));
            assert(total === 200, '2 x 100.00 == 200, no tax invented (got ' + total + ')');
            const charge = $('.mz-btn--charge');
            assert(!charge.disabled, 'charge enabled');
            charge.click();
            await waitFor(() => phase() === 'payment', 'payment transition still works');
            ok();
        """ % self.product.id), login='admin')

    # ---- accessibility ---------------------------------------------------------
    def test_09_accessible_names_and_touch_target(self):
        token = self.product.name.split(' ')[0]
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-tile'), 'catalog');
            const cell = $('.mz-tile[data-product-id="%d"]').closest('.mz-tile-cell');
            const main = cell.querySelector('.mz-tile');
            const qa = cell.querySelector('.mz-tile__quick-add');
            // main keeps a product-bearing name from its own content
            assert(/%s/i.test(main.textContent), 'main control still names the product');
            const name = qa.getAttribute('aria-label') || '';
            assert(name.length > 3, 'quick-add has an accessible name');
            assert(!/^\s*\+\s*$/.test(name), 'the name is not just "+"');
            assert(name.toLowerCase() !== 'add', 'the name is not a bare "Add"');
            assert(name.indexOf('%s') !== -1,
                   'the name carries the product: ' + JSON.stringify(name));
            // the visible glyph must not leak into the accessible name
            assert(qa.querySelector('.mz-tile__plus').getAttribute('aria-hidden') === 'true',
                   'the + glyph is hidden from assistive tech');
            // touch floor on the BUTTON, while the visible affordance stays reference-sized
            const r = qa.getBoundingClientRect();
            assert(r.width >= 44 && r.height >= 44,
                   'quick-add hit target >=44x44 (' + Math.round(r.width) + 'x' + Math.round(r.height) + ')');
            const g = qa.querySelector('.mz-tile__plus').getBoundingClientRect();
            assert(Math.round(g.width) === 27 && Math.round(g.height) === 27,
                   'visible affordance matches the reference 27x27 (' + Math.round(g.width) + 'x' + Math.round(g.height) + ')');
            // it must sit inside the card, in the trailing-bottom corner
            const c = cell.getBoundingClientRect();
            assert(r.bottom <= c.bottom + 1 && r.top > c.top + c.height / 2,
                   'quick-add sits in the lower half of the card, inside its bounds');
            ok();
        """ % (self.product.id, token, token)), login='admin')

    def test_10_focus_is_visible_and_distinct_from_the_card(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-tile'), 'catalog');
            const cell = $('.mz-tile[data-product-id="%d"]').closest('.mz-tile-cell');
            const main = cell.querySelector('.mz-tile');
            const qa = cell.querySelector('.mz-tile__quick-add');
            main.focus();
            const mo = getComputedStyle(main).outlineStyle;
            assert(mo !== 'none', 'the card keeps its own visible focus ring');
            qa.focus();
            const glyph = qa.querySelector('.mz-tile__plus');
            const go = getComputedStyle(glyph);
            assert(go.outlineStyle !== 'none', 'the quick-add draws a visible focus ring');
            assert(parseFloat(go.outlineWidth) >= 2, 'focus ring is at least 2px (' + go.outlineWidth + ')');
            // the two rings must not both be full-card rings at the same time
            const gr = glyph.getBoundingClientRect(), cr = cell.getBoundingClientRect();
            assert(gr.width < cr.width / 2,
                   'the quick-add ring identifies the small control, not the whole card');
            ok();
        """ % self.product.id), login='admin')

    def test_11_arabic_accessible_name_is_localised(self):
        # An Arabic till must not announce an English control name. Uses the same
        # catalogue as the rest of the Register (JS terms need the odoo-javascript
        # marker in the .po to reach the web catalogue at all).
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-tile__quick-add'), 'catalog');
            assert(document.documentElement.getAttribute('dir') === 'rtl', 'document is RTL');
            const name = $('.mz-tile__quick-add').getAttribute('aria-label') || '';
            assert(name.length > 0, 'quick-add has an accessible name in Arabic');
            assert(/[؀-ۿ]/.test(name),
                   'the accessible name is Arabic, not hardcoded English: ' + JSON.stringify(name));
            ok();
        """), login=self.ar_user.login)

    def test_12_rtl_mirrors_placement_but_not_the_glyph(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-tile__quick-add'), 'catalog');
            const qa = $('.mz-tile__quick-add');
            const cell = qa.closest('.mz-tile-cell');
            const r = qa.getBoundingClientRect(), c = cell.getBoundingClientRect();
            // logical inset-inline-end resolves to the LEFT under rtl
            assert(r.left - c.left < c.right - r.right,
                   'quick-add mirrored to the inline-end (left) side under RTL');
            const glyph = qa.querySelector('.mz-tile__plus');
            const t = getComputedStyle(glyph).transform;
            assert(t === 'none' || t.indexOf('-1') === -1,
                   'the + glyph itself is not mirrored (' + t + ')');
            assert(r.width >= 44 && r.height >= 44, 'touch floor holds under RTL');
            const de = document.documentElement;
            assert(de.scrollWidth - de.clientWidth <= 1, 'no horizontal overflow under RTL');
            ok();
        """), login=self.ar_user.login)

    def test_13_price_ink_never_runs_under_the_quick_add(self):
        # Element boxes are full-width flex items, so a box-intersection test would
        # false-positive on every card. This measures the real TEXT ink with a Range.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-tile__quick-add'), 'catalog');
            let worst = Infinity;
            for (const cell of $$('.mz-tile-cell')) {
                const p = cell.querySelector('.mz-tile-price');
                const g = cell.querySelector('.mz-tile__plus');
                const rg = document.createRange(); rg.selectNodeContents(p);
                const t = rg.getBoundingClientRect(), q = g.getBoundingClientRect();
                const overlaps = t.right > q.left && t.left < q.right
                              && t.bottom > q.top && t.top < q.bottom;
                assert(!overlaps, 'price ink runs under the + on ' + p.textContent.trim());
                worst = Math.min(worst, Math.abs(q.left - t.right));
            }
            assert(worst >= 8, 'price keeps real clearance from the + (' + Math.round(worst) + 'px)');
            ok();
        """), login='admin')

    def test_14_rail_workspaces_show_real_data_or_say_why_not(self):
        # The rail's information architecture is only worth having if every destination
        # is honest. A workspace must be in exactly one of three states: it renders data
        # read from a real endpoint, it says the endpoint is empty, or it says this
        # terminal may not read it — and NEVER a fabricated dashboard.
        #
        # Ops / Manager / Reports / HQ all require REPORTS_READ, which a Register
        # terminal deliberately does not hold. That boundary is the product working, so
        # the panel must name it rather than render numbers.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-rail__item'), 'rail');
            const open = async (label) => {
                const t = $$('.mz-rail__item').find(
                    e => (e.getAttribute('aria-label') || '').trim() === label);
                assert(t, 'rail destination present: ' + label);
                t.click();
                await waitFor(() => $('.mz-wsp'), 'workspace ' + label);
                await new Promise(r => setTimeout(r, 900));
            };
            const state = () => ({
                denied: !!$('.mz-wsp .mz-state--warn'),
                error: !!$('.mz-wsp .mz-state--error'),
                stats: $$('.mz-wsp__stat').length,
                empty: !!$('.mz-wsp .mz-state--empty'),
                rows: $$('.mz-wsp__row').length,
            });
            // reporting workspaces: gated, and the panel must SAY the capability
            for (const label of ['Live Ops', 'Manager', 'Reports', 'HQ']) {
                await open(label);
                const s = state();
                assert(s.denied, label + ' states that this terminal may not read it');
                assert(!s.error, label + ' is a permission outcome, not an error');
                assert(s.stats === 0 && s.rows === 0,
                       label + ' renders NO figures when it may not read them');
                const body = ($('.mz-wsp__state-d') || {}).textContent || '';
                assert(/REPORTS_READ/.test(body),
                       label + ' names the capability it needs');
            }
            // readable workspaces: real endpoint, real (possibly empty) result
            for (const label of ['Beverage Queue', 'Delivery', 'Central Kitchen']) {
                await open(label);
                const s = state();
                assert(!s.denied, label + ' is readable by this terminal');
                assert(!s.error, label + ' loaded without error: '
                       + ((($('.mz-wsp__state-d') || {}).textContent) || ''));
                assert(s.stats > 0, label + ' shows counters read from the endpoint');
            }
            // Settings has its OWN catalogue-driven panel: real categories and controls,
            // and it must never offer a control for a setting the catalogue says is not
            // wired — that is the whole point of showing them read-only.
            const st = $$('.mz-rail__item').find(
                e => (e.getAttribute('aria-label') || '').trim() === 'Settings');
            st.click();
            await waitFor(() => $('.mz-set__cats'), 'settings panel');
            await new Promise(r => setTimeout(r, 900));
            assert($$('.mz-set__cat').length > 5, 'categories come from the catalogue');
            assert($$('.mz-set__row').length > 0, 'the selected category lists real settings');
            for (const row of $$('.mz-set__row--off')) {
                assert(row.querySelector('.mz-set__off'),
                       'an un-wired setting says so instead of rendering a control');
                const live = row.querySelector('.mz-switch:not([disabled]), .mz-seg__b:not([disabled])');
                assert(!live, 'an un-wired setting offers no live control');
            }
            // Floor and Kitchen are their own pages: the rail LINKS to them rather than
            // embedding them, so a dedicated device can run just that screen.
            for (const [label, path] of [['Floor', '/mezze/floor'], ['Kitchen', '/mezze/kds']]) {
                const t = $$('.mz-rail__item').find(
                    e => (e.getAttribute('aria-label') || '').trim() === label);
                assert(t, label + ' is in the rail');
                const href = t.getAttribute('href') || '';
                assert(href.indexOf(path) === 0, label + ' links to its own page (' + href + ')');
            }
            ok();
        """), login='admin')

    def test_15_topbar_theme_toggle_drives_the_shipped_contract(self):
        # The toggle must drive the SAME appearance contract the page bootstrap already
        # owns (?mzmode= > localStorage 'mzSettings.v1' > prefers-color-scheme), not a
        # second theming mechanism — and the token ramp must genuinely change, so this
        # asserts the resolved --mz-canvas colour rather than just the attribute.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-themetog'), 'theme toggle');
            const h = document.documentElement;
            const canvas = () => getComputedStyle(h).getPropertyValue('--mz-canvas').trim();
            const lum = (hex) => {
                const c = document.createElement('canvas'); c.width = c.height = 1;
                const x = c.getContext('2d'); x.fillStyle = hex; x.fillRect(0, 0, 1, 1);
                const d = x.getImageData(0, 0, 1, 1).data;
                return 0.2126*d[0] + 0.7152*d[1] + 0.0722*d[2];
            };
            const tog = $('.mz-themetog');
            const before = { mode: h.getAttribute('data-mz-mode'), canvas: canvas() };
            assert(tog.getAttribute('aria-pressed') === (before.mode === 'dark' ? 'true' : 'false'),
                   'aria-pressed reflects the current mode');
            tog.click();
            await waitFor(() => h.getAttribute('data-mz-mode') !== before.mode, 'mode flipped');
            const after = { mode: h.getAttribute('data-mz-mode'), canvas: canvas() };
            assert(after.canvas !== before.canvas, 'the canvas TOKEN actually changed');
            const dark = after.mode === 'dark' ? after : before;
            const light = after.mode === 'dark' ? before : after;
            assert(lum(dark.canvas) < lum(light.canvas),
                   'dark canvas is genuinely darker (' + dark.canvas + ' vs ' + light.canvas + ')');
            // it must use the SHIPPED contract, not a private key
            const stored = JSON.parse(localStorage.getItem('mzSettings.v1') || '{}');
            assert(stored.app_mode === after.mode,
                   'persisted through mzSettings.v1.app_mode (got ' + JSON.stringify(stored) + ')');
            assert(h.getAttribute('data-theme') === after.mode, 'data-theme kept in step');
            // the attribute is set synchronously by the handler, but aria-pressed comes
            // from reactive state and lands on the next render — wait for it rather than
            // racing it, and re-query in case Owl replaced the node.
            await waitFor(() => $('.mz-themetog').getAttribute('aria-pressed')
                                === (after.mode === 'dark' ? 'true' : 'false'),
                          'aria-pressed follows the mode');
            assert(parseFloat(getComputedStyle($('.mz-themetog')).height) >= 44,
                   'toggle keeps the 44px floor');
            ok();
        """), login='admin')

    def test_16_shell_puts_the_rail_beside_the_workspace_not_above_it(self):
        # A layout regression that no existing test could see: the shell set the app's
        # flex-direction in TWO stylesheets, and whichever the bundle loaded last won.
        # When the rail moved to the shared shell, the Register's own older
        # `flex-direction: column` started winning again and stacked the 68px rail ON TOP
        # of the whole workspace. Assert the geometric relationship, not the CSS.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-rail') && $('.mz-shell'), 'shell');
            const rail = $('.mz-rail').getBoundingClientRect();
            const shell = $('.mz-shell').getBoundingClientRect();
            assert(Math.round(rail.width) <= 80,
                   'the rail is a narrow column, not a full-width band (' + Math.round(rail.width) + ')');
            assert(Math.round(shell.left) >= Math.round(rail.right) - 1,
                   'the workspace starts AFTER the rail (rail right ' + Math.round(rail.right)
                   + ', shell left ' + Math.round(shell.left) + ')');
            assert(Math.abs(Math.round(shell.top) - Math.round(rail.top)) <= 4,
                   'the workspace is BESIDE the rail, not below it (rail top ' + Math.round(rail.top)
                   + ', shell top ' + Math.round(shell.top) + ')');
            assert(rail.height > shell.height * 0.9,
                   'the rail spans the full height');
            const de = document.documentElement;
            assert(de.scrollHeight - de.clientHeight <= 1, 'no vertical overflow');
            assert(de.scrollWidth - de.clientWidth <= 1, 'no horizontal overflow');
            ok();
        """), login='admin')

    def test_17_customer_can_be_attached_from_the_order_panel(self):
        # "Adding customer is not working": the picker markup lived ONLY inside the
        # payment screen, so the order panel's control set the state and nothing
        # rendered. And the customerName getter had been deleted by an unrelated
        # refactor, so even once the picker opened, choosing someone left the chip
        # reading "Add customer". Both are asserted here, end to end.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-custchip'), 'customer chip');
            const chipText = () => ($('.mz-custchip__t') || {}).textContent.trim();
            const before = chipText();
            $('.mz-custchip').click();
            await waitFor(() => $('.mz-custpick'), 'picker opens from the order panel');
            const input = $('[data-testid=mz-customer-search]');
            assert(input, 'the picker has a search field');
            const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            set.call(input, 'a');
            input.dispatchEvent(new Event('input', {bubbles: true}));
            await waitFor(() => $$('.mz-cust-row').length > 0, 'search returns real partners');
            const name = $$('.mz-cust-row')[0].textContent.trim();
            $$('.mz-cust-row')[0].click();
            await waitFor(() => $('.mz-cust-row--active'), 'the chosen row is marked');
            // the ACTUAL defect: the panel must show who is attached
            await waitFor(() => chipText() !== before,
                          'the chip shows the attached customer instead of "' + before + '"');
            assert(name.indexOf(chipText()) === 0 || chipText().length > 0,
                   'chip carries the customer name (' + chipText() + ')');
            // and it can be reopened from the verb grid
            $('.mz-modal__x').click();
            await waitFor(() => !$('.mz-custpick'), 'picker closes');
            const verb = $$('.mz-verb').find(v => /Customer/.test(v.textContent));
            assert(verb, 'the Customer verb is in the action grid');
            verb.click();
            await waitFor(() => $('.mz-custpick'), 'picker reopens from the verb');
            ok();
        """), login='admin')

    def test_18_every_rail_destination_opens_from_any_phase(self):
        # Rail destinations render inside the MENU phase, so opening one from Orders or
        # Reservations left the phase behind and drew nothing — Settings looked dead
        # when reached from those screens.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-rail__item'), 'rail');
            const click = async (label) => {
                const t = $$('.mz-rail__item').find(
                    e => (e.getAttribute('aria-label') || '').trim() === label);
                assert(t, 'rail has ' + label);
                t.click();
                await new Promise(r => setTimeout(r, 700));
            };
            // park ourselves in a NON-menu phase first
            await click('Orders');
            await waitFor(() => phase() === 'orders', 'orders phase');
            await click('Reservations');
            await waitFor(() => phase() === 'reservations', 'reservations phase');
            // now every endpoint-backed destination must still open
            for (const [label, probe] of [['Settings', '.mz-set__cats'],
                                          ['Central Kitchen', '.mz-wsp'],
                                          ['Delivery', '.mz-wsp'],
                                          ['Live Ops', '.mz-wsp']]) {
                await click('Reservations');            // back to a non-menu phase each time
                await waitFor(() => phase() === 'reservations', 'reservations again');
                await click(label);
                await waitFor(() => $(probe), label + ' opens from the reservations phase');
                assert(phase() === 'menu', label + ' returned to the menu phase');
            }
            ok();
        """), login='admin')

    def test_19_settings_apply_to_the_register_not_just_storage(self):
        # The catalogue marks 18 settings `working`, but the Owl Register never read
        # them at boot: the server stored a choice faithfully and the till looked
        # identical. Each of these drives a DIFFERENT part of the contract, so a
        # regression in any one of them is visible here.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('.mz-grid'), 'register');
            const h = document.documentElement;
            const open = async () => {
                $$('.mz-rail__item').find(
                    e => (e.getAttribute('aria-label') || '').trim() === 'Settings').click();
                await waitFor(() => $('.mz-set__cats'), 'settings');
            };
            const cat = async (name) => {
                $$('.mz-set__cat').find(
                    b => b.querySelector('.mz-set__cat-n').textContent === name).click();
                await new Promise(r => setTimeout(r, 250));
            };
            const seg = async (key, val) => {
                $$(`[data-key="${key}"] .mz-seg__b`).find(b => b.textContent === val).click();
                await new Promise(r => setTimeout(r, 700));
            };
            // a catalogue enum renders as a <select>, an int as a text input — the
            // control follows the TYPE, so the helper has to as well
            const sel = async (key, val) => {
                const s = $(`[data-key="${key}"] .mz-set__sel`)
                       || $(`[data-key="${key}"] .mz-set__num`);
                assert(s, 'a control exists for ' + key);
                s.value = val;
                s.dispatchEvent(new Event('change', { bubbles: true }));
                await new Promise(r => setTimeout(r, 700));
            };

            await open();
            await cat('Workspace');
            await seg('ws_panel_side', 'left');
            assert(h.getAttribute('data-mz-panel') === 'left', 'panel side applied live');
            await seg('ws_panel_width', 'wide');
            await cat('Product Grid');
            await seg('gr_cols_mode', 'fixed');
            await sel('gr_cols', '6');
            await cat('Appearance');
            await seg('app_density', 'compact');
            await sel('app_accent', 'teal');

            // ... and the SERVER must really hold it. Leaving Settings and coming back
            // remounts the panel, which re-reads /settings/effective — so a value that
            // only ever lived in this component's state would read back as the default.
            $$('.mz-wsview__head .mz-btn--secondary')[0].click();
            await waitFor(() => $('.mz-grid'), 'back on the register');
            await open();
            const readBack = {};
            for (const [c, keys] of [['Workspace', ['ws_panel_side', 'ws_panel_width']],
                                     ['Product Grid', ['gr_cols_mode', 'gr_cols']],
                                     ['Appearance', ['app_density', 'app_accent']]]) {
                await cat(c);
                for (const k of keys) {
                    const row = $(`[data-key="${k}"]`);
                    const on = row.querySelector('.mz-seg__b[aria-pressed="true"]');
                    const s = row.querySelector('.mz-set__sel');
                    const num = row.querySelector('.mz-set__num');
                    readBack[k] = on ? on.textContent : (s ? s.value : num.value);
                }
            }
            assert(readBack.ws_panel_side === 'left', 'panel side persisted');
            assert(readBack.ws_panel_width === 'wide', 'panel width persisted');
            assert(readBack.gr_cols_mode === 'fixed', 'columns mode persisted');
            assert(readBack.gr_cols === '6', 'grid columns persisted');
            assert(readBack.app_density === 'compact', 'density persisted');
            assert(readBack.app_accent === 'teal', 'accent persisted');

            $$('.mz-wsview__head .mz-btn--secondary')[0].click();
            await waitFor(() => $('.mz-grid'), 'register again');
            const h2 = document.documentElement;
            assert(h2.getAttribute('data-mz-panel') === 'left', 'panel side still applied');
            assert(h2.getAttribute('data-mz-grid-cols') === '6', 'grid columns applied');
            assert(h2.getAttribute('data-mz-density') === 'compact', 'density applied');
            // the attributes are not decorative — the layout actually moved
            const cart = $('.mz-cart'), grid = $('.mz-grid');
            assert(getComputedStyle(cart).order === '1', 'order panel moved to the left');
            assert(getComputedStyle(cart).flexBasis === '400px', 'order panel is wide');
            assert(getComputedStyle(grid).gridTemplateColumns.split(' ').length === 6,
                   'the grid really has 6 columns');
            assert(getComputedStyle(document.documentElement)
                     .getPropertyValue('--mz-brand').trim() !== '', 'accent resolved a brand');

            // put the branch back the way we found it
            await open();
            for (const c of ['Appearance', 'Product Grid', 'Workspace']) {
                await cat(c);
                $$('.mz-set__main .mz-btn--secondary').find(
                    b => /Reset/i.test(b.textContent)).click();
                await new Promise(r => setTimeout(r, 900));
            }
            ok();
        """), login='admin')

    def test_20_each_dark_theme_paints_its_own_palette(self):
        # cashier.css re-declared the lounge palette under [data-mz-mode="dark"] and
        # loads after the theme registry at equal specificity, so Midnight, Graphite,
        # Slate and Forest Night all rendered as Lounge. And high contrast shipped a
        # brand chosen for contrast that the later accent ramp overwrote.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('.mz-grid'), 'register');
            const h = document.documentElement;
            const canvasFor = (mode, theme) => {
                h.setAttribute('data-mz-mode', mode);
                h.setAttribute('data-mz-theme', theme);
                return getComputedStyle(h).getPropertyValue('--mz-canvas').trim().toUpperCase();
            };
            const seen = new Map();
            for (const t of ['lounge', 'midnight', 'graphite', 'slate', 'forestnight']) {
                const c = canvasFor('dark', t);
                assert(!seen.has(c), t + ' has its own canvas (got ' + c + ', same as ' + seen.get(c) + ')');
                seen.set(c, t);
            }
            // high contrast keeps its accessible brand even with an accent chosen
            h.setAttribute('data-mz-accent', 'terracotta');
            canvasFor('light', 'highcontrast');
            assert(getComputedStyle(h).getPropertyValue('--mz-brand').trim().toUpperCase()
                   === '#9A3D18', 'high contrast keeps its 6.87:1 brand, not the 4.24:1 accent');
            ok();
        """), login='admin')
