"""CONV-2a — the canonical category navigation is ONE definition, consumed by both.

The desktop category sidebar was written for the Register and lived inside the
cashier's asset bundle, so no page outside that bundle could reach it — which is
why the drive-thru had only the chip strip at every width. This pass moved it to
``static/design/category-nav.css``.

Two things have to be true, and both are asserted here rather than assumed:

* the **Register moves by zero pixels** — same sidebar, same rows, same contract,
  same mirroring, same density behaviour as before the move;
* the shared sheet is **genuinely shareable** — self-contained, reachable from the
  drive-thru page, and enough on its own to render the canonical sidebar.

The responsive contract (>=1280 sidebar, <1280 chips, never both, never neither)
is swept across the breakpoint in a fixed-width iframe, because a contract that is
only ever checked at the test browser's own width is not checked at all.
"""
import os
import re

from odoo.tests import tagged

from .common import MezzeHttpCase

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED = os.path.join(ADDON, 'static', 'design', 'category-nav.css')
CASHIER = os.path.join(ADDON, 'static', 'src', 'cashier', 'cashier.css')
DRIVETHRU = os.path.join(ADDON, 'static', 'drivethru.html')
MANIFEST = os.path.join(ADDON, '__manifest__.py')

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
const px = (v) => parseFloat(v) || 0;

/* The canonical sidebar, as the Register renders it. Used to prove a surface can
   CONSUME the shared definition without importing the Register's components. */
const SIDEBAR = '<aside class="mz-catside" aria-label="Categories">'
  + '<div class="mz-catside__branch"><span class="mz-catside__dot"></span>'
  + '<span class="mz-catside__bname">Branch</span></div>'
  + '<p class="mz-catside__label">Categories</p><div class="mz-catside__list">'
  + '<button type="button" class="mz-catside__item mz-catside__item--active" aria-pressed="true">'
  + '<span class="mz-catside__n">All items</span><span class="mz-catside__c">172</span></button>'
  + '<button type="button" class="mz-catside__item" aria-pressed="false">'
  + '<span class="mz-catside__n">Drinks</span><span class="mz-catside__c">9</span></button>'
  + '</div></aside>';
const CATALOG = '<section class="mz-catalog"><nav class="mz-catbar">'
  + '<button type="button" class="mz-cat">All</button></nav></section>';

/* A standalone document carrying ONLY the shared DESIGN LAYER — tokens, canonical
   components, product browser, category navigation — at a chosen width. No cashier
   bundle, no Owl, no application code. If the sidebar renders correctly in here,
   the definition is genuinely shareable: it needs the platform's design layer (as
   every Mezze surface does, drive-thru included) and nothing of the Register.
   mezze-design.css is the token source, and it keys the token ramps off the
   appearance attributes every Mezze page is stamped with server-side — without
   them var(--mz-border) resolves to nothing and a border-inline-end declaration is
   dropped entirely, which is how this harness first lied about RTL. */
async function sheet(width, dir){
  const fr = document.createElement('iframe');
  fr.setAttribute('width', width);
  fr.style.cssText = 'width:' + width + 'px;height:700px;border:0;position:fixed;left:-9999px;top:0';
  fr.srcdoc = '<!doctype html><html dir="' + (dir || 'ltr') + '"'
    + ' data-appearance="mezze" data-mz-theme="classic" data-mz-mode="light"><head>'
    + '<link rel="stylesheet" href="/mezze_bridge/static/design/foundation.css">'
    + '<link rel="stylesheet" href="/mezze_bridge/static/design/components.css">'
    + '<link rel="stylesheet" href="/mezze_bridge/static/design/product-browser.css">'
    + '<link rel="stylesheet" href="/mezze_bridge/static/design/category-nav.css">'
    + '<link rel="stylesheet" href="/mezze_bridge/static/mezze-design.css">'
    + '</head><body style="margin:0"><div class="mz-workspace" style="display:flex">'
    + SIDEBAR + CATALOG + '</div></body></html>';
  document.body.appendChild(fr);
  await new Promise((res) => { fr.onload = res; });
  const d = fr.contentDocument;
  /* stylesheets can still be in flight after load in headless */
  await waitFor(() => d.styleSheets.length >= 5, 'the shared design layer at ' + width);
  await waitFor(() => {
    const s = d.querySelector('.mz-catside');
    return s && parseFloat(fr.contentWindow.getComputedStyle(s).flexBasis) === 201
        || (width < 1280 && fr.contentWindow.getComputedStyle(s).display === 'none');
  }, 'shared sheet applied at ' + width);
  return fr;
}
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_conv2a')
class TestCategoryNavSource(MezzeHttpCase):
    """Source-level: ONE definition, wired into both surfaces."""
    fixture_profile = 'POS'

    def _read(self, path):
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_01_the_shared_definition_exists_and_carries_the_sidebar(self):
        css = self._read(SHARED)
        for rule in ('.mz-catside{', '.mz-catside__branch{', '.mz-catside__label{',
                     '.mz-catside__list{', '.mz-catside__item{', '.mz-catside__c{'):
            self.assertIn(rule, css, '%s belongs to the canonical sidebar' % rule)
        self.assertIn('@media (min-width:1280px)', css,
                      'the desktop breakpoint travels with the component')

    def test_02_the_cashier_no_longer_defines_the_sidebar(self):
        """One effective source. A leftover copy in the bundle would silently win.

        CONV-2a left exactly one rule behind — the ``data-mz-panel="left"`` swap,
        whose other two thirds were order-panel rules. CONV-2b extracted the order
        panel, so that family moved as a unit into design/order-panel.css and the
        carve-out is gone: the cashier now declares NOTHING about the sidebar.
        """
        stripped = re.sub(r'/\*.*?\*/', '', self._read(CASHIER), flags=re.S)
        offenders = [m.strip() for m in re.findall(r'[^{}]*\.mz-catside[^{]*\{', stripped)]
        self.assertEqual(offenders, [],
                         'the cashier still declares sidebar rules: %s' % offenders)

    def test_03_the_contract_travels_with_the_component(self):
        """>=1280 hides the chip strip. Split across two files it is not a contract."""
        shared = self._read(SHARED)
        cashier = re.sub(r'/\*.*?\*/', '', self._read(CASHIER), flags=re.S)
        self.assertIn(':has(.mz-catside)', shared)
        self.assertNotIn(':has(.mz-catside)', cashier)

    def test_04_both_surfaces_load_it(self):
        manifest = self._read(MANIFEST)
        self.assertIn('design/category-nav.css', manifest,
                      'the cashier bundle loads the shared sheet')
        # ...before cashier.css, so every later cashier rule still wins as before
        self.assertLess(manifest.index('design/category-nav.css'),
                        manifest.index('static/src/cashier/**'),
                        'shared sheet must load BEFORE the cashier styles')
        self.assertIn('design/category-nav.css', self._read(DRIVETHRU),
                      'the drive-thru page links the same file')

    def test_05_no_physical_direction_in_the_shared_sheet(self):
        """RTL: the sidebar must mirror, so nothing here may name a physical side."""
        css = re.sub(r'/\*.*?\*/', '', self._read(SHARED), flags=re.S)
        banned = re.findall(
            r'(?<![-\w])(?:margin|padding|border)-(?:left|right)\s*:|'
            r'(?<![-\w])(?:left|right)\s*:', css)
        self.assertEqual(banned, [], 'physical left/right in a shared component: %s' % banned)

    def test_06_density_never_buys_space_from_the_touch_target(self):
        css = self._read(SHARED)
        self.assertIn('min-height:44px', css, 'the row keeps the 44px floor')
        # the density overrides may only touch padding
        for line in css.splitlines():
            if 'data-mz-density' in line and '.mz-catside' in line:
                self.assertIn('padding-block:', line)
                self.assertNotIn('min-height', line)
                self.assertNotIn('height:', line.replace('min-height', ''))


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_conv2a')
class TestCategoryNavRegister(MezzeHttpCase):
    """The Register must be indistinguishable from before the move."""
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
        cls.env.flush_all()

    def test_10_the_register_still_renders_the_canonical_sidebar(self):
        """Headless Chrome runs at 1366 wide, i.e. above the 1280 breakpoint."""
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-catside'), 'category sidebar');
            const side = $('.mz-catside');
            const cs = getComputedStyle(side);
            assert(cs.display === 'flex', 'sidebar is laid out (' + cs.display + ')');
            /* 201 CONTENT + 20 padding + 1 rule = the design's 222px column.
               The TOTAL is the invariant: it is what the design measures and what
               decides how many product columns fit beside it. The basis is a
               consequence of it and of the column's own padding, so it moves
               whenever the padding does. SCREEN01_DIFF row 11 took the padding from
               12px 12px to the design's 12px 10px, which turns a 197px basis into a
               201px one and leaves the 222px column exactly where it was. The
               operator ruled the design values stand, so the basis follows the
               padding and the total is asserted alongside it. */
            assert(px(cs.flexBasis) === 201, 'canonical 201px basis (' + cs.flexBasis + ')');
            assert(px(cs.borderInlineEndWidth) === 1, 'canonical trailing rule');
            assert(Math.round(side.getBoundingClientRect().width) === 222,
                   'the column measures ' + Math.round(side.getBoundingClientRect().width)
                   + ', the design measures 222');

            const rows = $$('.mz-catside__item');
            assert(rows.length >= 2, 'the sidebar lists categories (' + rows.length + ')');
            for (const r of rows) {
                const rc = getComputedStyle(r);
                assert(px(rc.minHeight) >= 44, 'row meets the touch floor (' + rc.minHeight + ')');
                assert(r.getBoundingClientRect().height >= 44, 'row is really 44+');
                assert(px(rc.borderRadius) === 11, 'canonical 11px radius (' + rc.borderRadius + ')');
                /* SCREEN01_DIFF row 15 — the design's row is 12.5px. 13 was ours,
                   carried over from before the frozen file was the authority. */
                assert(px(rc.fontSize) === 12.5, 'canonical 12.5px row (' + rc.fontSize + ')');
                /* 'start' is what the sheet says; a browser may serialise it as the
                   resolved side. The claim is that the row is not centred. */
                assert(['start', 'left'].includes(rc.textAlign),
                       'row text hugs the reading edge (' + rc.textAlign + ')');
                assert(r.hasAttribute('aria-pressed'), 'row states selection to AT');
                assert(r.querySelector('.mz-catside__c'), 'row carries its live count');
            }
            const active = $('.mz-catside__item--active');
            assert(active && active.getAttribute('aria-pressed') === 'true',
                   'the active category is announced, not only coloured');
            ok();
        """), login='admin')

    def test_11_exactly_one_category_navigation_is_visible(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-catside') && $('.mz-catbar'), 'both navigations exist');
            const side = getComputedStyle($('.mz-catside')).display;
            const bar  = getComputedStyle($('.mz-catbar')).display;
            assert(side !== 'none', 'at this width the sidebar is the navigation');
            assert(bar === 'none', 'the chip strip stands down beside it (' + bar + ')');
            ok();
        """), login='admin')

    def test_12_the_sidebar_keeps_a_visible_focus_ring(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => $('.mz-catside__item'), 'a category row');
            let found = false;
            for (const ss of document.styleSheets) {
                let rules; try { rules = ss.cssRules; } catch (e) { continue; }
                for (const r of rules) {
                    const walk = (rule) => {
                        if (rule.selectorText && /\.mz-catside__item:focus-visible/.test(rule.selectorText)
                            && /solid/.test(rule.style.outline || rule.style.outlineStyle || '')) found = true;
                        if (rule.cssRules) { for (const rr of rule.cssRules) walk(rr); }
                    };
                    walk(r);
                }
            }
            assert(found, 'the category row keeps its focus-visible outline');
            ok();
        """), login='admin')


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_conv2a')
class TestCategoryNavShareable(MezzeHttpCase):
    """The shared sheet must work on its own, and the drive-thru must reach it."""
    fixture_profile = 'POS'

    def test_20_the_responsive_contract_holds_across_the_breakpoint(self):
        """Never both, never neither — swept, not sampled at one width."""
        self.browser_js('/mezze/drivethru', _js(r"""
            const widths = [1024, 1100, 1279, 1280, 1281, 1440, 1920];
            const seen = [];
            for (const w of widths) {
                const fr = await sheet(w);
                const W = fr.contentWindow, d = fr.contentDocument;
                const side = W.getComputedStyle(d.querySelector('.mz-catside')).display;
                const bar  = W.getComputedStyle(d.querySelector('.mz-catbar')).display;
                seen.push(w + ':' + side + '/' + bar);
                assert(!(side !== 'none' && bar !== 'none'), 'both navigations at ' + w);
                assert(!(side === 'none' && bar === 'none'), 'no navigation at all at ' + w);
                assert((w >= 1280) === (side !== 'none'),
                       'the sidebar belongs to >=1280 (' + w + ' -> ' + side + ')');
                fr.remove();
            }
            assert(seen.length === widths.length, 'every width was swept: ' + seen.join(' '));
            ok();
        """), login='admin')

    def test_21_the_shared_sheet_needs_no_cashier_bundle(self):
        """Design layer only — no Owl, no cashier bundle — and the geometry lands."""
        self.browser_js('/mezze/drivethru', _js(r"""
            const fr = await sheet(1440);
            const W = fr.contentWindow, d = fr.contentDocument;
            assert(!d.querySelector('link[href*="assets_cashier"]'), 'no cashier bundle here');
            const side = d.querySelector('.mz-catside'), item = d.querySelector('.mz-catside__item');
            const cs = W.getComputedStyle(side), ci = W.getComputedStyle(item);
            assert(cs.display === 'flex', 'sidebar laid out from the shared sheet alone');
            assert(px(cs.flexBasis) === 201, 'canonical 201px (' + cs.flexBasis + ')');
            assert(Math.round(side.getBoundingClientRect().width) === 222,
                   'the column measures ' + Math.round(side.getBoundingClientRect().width)
                   + ', the design measures 222');
            assert(px(ci.minHeight) === 44, 'canonical 44px row (' + ci.minHeight + ')');
            assert(px(ci.borderRadius) === 11, 'canonical 11px radius');
            assert(px(ci.fontSize) === 12.5, 'canonical 12.5px');
            assert(item.getBoundingClientRect().height >= 44, 'the row is really 44+');
            fr.remove();
            ok();
        """), login='admin')

    def test_22_the_sidebar_mirrors_under_rtl(self):
        """Mirroring is asserted GEOMETRICALLY.

        The first version of this test compared ``textAlign`` to the string
        'start' — which passes or fails on how a given Chrome serialises a
        computed value, not on where the text actually is. Where the name and the
        count sit inside the row is the thing an Arabic operator sees.
        """
        self.browser_js('/mezze/drivethru', _js(r"""
            const measure = async (dir) => {
                const fr = await sheet(1440, dir);
                const W = fr.contentWindow, d = fr.contentDocument;
                const side = W.getComputedStyle(d.querySelector('.mz-catside'));
                const item = d.querySelector('.mz-catside__item');
                const row = item.getBoundingClientRect();
                const name = item.querySelector('.mz-catside__n').getBoundingClientRect();
                const count = item.querySelector('.mz-catside__c').getBoundingClientRect();
                const out = {
                    bl: px(side.borderLeftWidth), br: px(side.borderRightWidth),
                    minH: px(W.getComputedStyle(item).minHeight),
                    height: row.height,
                    nameLead: name.left - row.left,        /* gap on the physical left */
                    countAfterName: count.left > name.left, /* count follows the name? */
                };
                fr.remove();
                return out;
            };
            const l = await measure('ltr');
            const r = await measure('rtl');

            assert(l.bl === 0 && l.br === 1, 'LTR: the sidebar rule is on the right edge');
            assert(r.bl === 1 && r.br === 0, 'RTL: the same logical rule moves to the left edge');

            assert(l.countAfterName, 'LTR: the count sits after the name');
            assert(!r.countAfterName, 'RTL: the count moves to the other side of the name');
            assert(r.nameLead > l.nameLead,
                   'RTL: the name is pushed off the leading (right) edge instead of the left ('
                   + l.nameLead + ' vs ' + r.nameLead + ')');

            assert(l.minH === 44 && r.minH === 44, 'the touch floor survives mirroring');
            assert(l.height >= 44 && r.height >= 44, 'and it holds in the real box');
            ok();
        """), login='admin')

    def test_23_density_reaches_the_shared_sidebar_without_shrinking_the_target(self):
        """The appearance cascade must drive every surface, including the new one."""
        self.browser_js('/mezze/drivethru', _js(r"""
            const fr = await sheet(1440);
            const W = fr.contentWindow, d = fr.contentDocument;
            const root = d.documentElement;
            root.setAttribute('data-appearance', 'mezze');
            const read = () => {
                const c = W.getComputedStyle(d.querySelector('.mz-catside__item'));
                return { pad: px(c.paddingBlockStart), min: px(c.minHeight),
                         box: d.querySelector('.mz-catside__item').getBoundingClientRect().height };
            };
            root.setAttribute('data-mz-density', 'compact');
            const compact = read();
            root.setAttribute('data-mz-density', 'comfortable');
            const comfy = read();
            fr.remove();

            assert(compact.pad > 0 && comfy.pad > compact.pad,
                   'density changes the rhythm (' + compact.pad + ' vs ' + comfy.pad + ')');
            assert(compact.min === 44 && comfy.min === 44, 'the 44px floor is never traded away');
            assert(compact.box >= 44 && comfy.box >= 44, 'and it holds in the real box');
            ok();
        """), login='admin')

    def test_24_the_drive_thru_page_actually_serves_the_shared_sheet(self):
        """A stylesheet that 404s is not shared — the board would just look normal."""
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => document.styleSheets.length > 0, 'stylesheets');
            const link = Array.from(document.querySelectorAll('link[rel=stylesheet]'))
                .map(l => l.getAttribute('href') || '')
                .find(h => h.indexOf('category-nav') >= 0);
            assert(link, 'the board links the shared category navigation');
            const res = await fetch(link);
            assert(res.status === 200, 'it is served (' + res.status + ')');
            const txt = await res.text();
            assert(txt.indexOf('.mz-catside__item') >= 0, 'and it really carries the sidebar');

            /* and it applies here, on the real board, to canonical markup */
            const host = document.createElement('div');
            host.className = 'mz-workspace';
            host.style.cssText = 'display:flex;position:fixed;left:-9999px;top:0';
            host.innerHTML = SIDEBAR;
            document.body.appendChild(host);
            const cs = getComputedStyle(host.querySelector('.mz-catside'));
            const ci = getComputedStyle(host.querySelector('.mz-catside__item'));
            const basis = px(cs.flexBasis), minH = px(ci.minHeight);
            const total = Math.round(host.querySelector('.mz-catside').getBoundingClientRect().width);
            host.remove();
            assert(basis === 201, 'canonical 201px on the drive-thru page (' + basis + ')');
            assert(total === 222, 'the drive-thru column measures ' + total
                                  + ', the design measures 222');
            assert(minH === 44, 'canonical 44px row on the drive-thru page (' + minH + ')');
            ok();
        """), login='admin')

    def test_25_the_board_consumes_the_shared_sidebar(self):
        """CONV-2a proved the board COULD consume it; CONV-2b made it do so.

        This test read the other way round until the Order Taker landed — it
        asserted that no sidebar was rendered yet. That was true of CONV-2a and is
        deliberately false now, so it asserts the same subject from the other side:
        the sidebar the board renders is the shared definition, not a copy.
        """
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-catside__item').length > 1, 'the sidebar');
            const cs = getComputedStyle($('.mz-catside'));
            const item = $('.mz-catside__item');
            assert(px(cs.flexBasis) === 201, 'canonical 201px basis (' + cs.flexBasis + ')');
            assert(px(getComputedStyle(item).minHeight) === 44, 'canonical 44px row');
            assert(px(getComputedStyle(item).borderRadius) === 11, 'canonical 11px radius');
            // and the compact form is still there, for the widths that use it
            assert($$('#cats .mz-cat').length > 1, 'the chip strip still exists');
            ok();
        """), login='admin')
