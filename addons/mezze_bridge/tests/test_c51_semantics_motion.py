"""FINAL-C5.1 — two bounded certification cleanups.

**A. Document semantics on the storefront.** `lang` declares the human language and `dir`
declares the base writing direction; they are related but independent, and both have to be
re-declared when the language changes. A fresh `?lang=ar` load was already correct because
the deferred `mezze-customer.js` re-derives `dir` from `lang` after boot — but nothing
re-runs it on a live switch, so `dir` went stale while the page visibly flipped via
`body.rtl`. C5.1 makes the switched state identical to the (already certified) fresh state.

**B. `prefers-reduced-motion` at runtime.** F11 listed this as "no emulation available".
That was wrong: the same CDP path C3 used for `forced-colors` drives it. These tests prove
the media state with `matchMedia` first, then measure *computed* animation — never the
stylesheet.
"""
import contextlib
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import ChromeBrowser

from .common import MezzeHttpCase

STORE = 'c51store'

PRELUDE = (
    "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
    "function waitFor(f,l,ms){ms=ms||20000;var t0=Date.now();"
    "return new Promise(function(res,rej){(function p(){try{if(f())return res(true);}catch(e){}"
    "if(Date.now()-t0>ms)return rej(new Error('timeout: '+l));setTimeout(p,100);})();});}"
    "function sleep(ms){return new Promise(function(r){setTimeout(r,ms);});}"
    "function ok(){console.log('test successful');}"
    "function de(){return document.documentElement;}"
    "function sem(){return de().lang+'/'+de().getAttribute('dir');}"
    # a probe carrying a real product class, so we measure the shipped CSS contract
    "function probe(cls,parent){var e=document.createElement('div');e.className=cls;"
    "(parent||document.body).appendChild(e);return e;}"
)


def _js(body):
    return "(async () => {\n" + body + "\n})().catch(e => console.error(e.message || e));"


SHOP_BOOT = r"""
    await waitFor(() => document.querySelectorAll('#grid .prod').length, 'shop menu');
    for (const t of [...document.querySelectorAll('#grid .prod')].slice(0, 8)) {
        t.click(); await sleep(350);
        const a = document.querySelector('#opt-add');
        if (a && a.offsetParent) { a.click(); await sleep(350); }
        if (document.querySelector('.mz-stepper__btn')) break;
    }
    document.querySelector('#viewcart, #cartbar button').click(); await sleep(600);
"""


@tagged('post_install', '-at_install', 'mezze_c51')
class TestSemanticsAndMotion(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.store_token_%s' % self.pos_config.id, STORE)
        self.product.write({'list_price': 100.0, 'available_in_pos': True})
        self.pos_session = self.open_test_session()
        self.env.flush_all()

    def shop_url(self, lang='en'):
        return '/mezze_bridge/static/shop.html?store=%s&lang=%s' % (STORE, lang)

    @contextlib.contextmanager
    def emulated_media(self, features):
        """CDP media emulation on the browser browser_js builds (the C3 pattern)."""
        original = ChromeBrowser.navigate_to

        def navigate_to(browser_self, url, wait_stop=False):
            browser_self._websocket_request('Emulation.setEmulatedMedia', params={
                'features': [{'name': k, 'value': v} for k, v in features.items()]})
            return original(browser_self, url, wait_stop=wait_stop)

        with patch.object(ChromeBrowser, 'navigate_to', navigate_to):
            yield

    def media_js(self, url, body, features, login='admin'):
        with self.emulated_media(features):
            self.browser_js(url, PRELUDE + _js(body), login=login)

    # ==================================================================
    # A — shop document semantics
    # ==================================================================
    def test_01_shop_english_declares_ltr(self):
        self.browser_js(self.shop_url('en'), PRELUDE + _js(r"""
            await waitFor(() => document.querySelector('#lang'), 'boot');
            assert(sem() === 'en/ltr', 'English declares en/ltr, got ' + sem());
            assert(getComputedStyle(document.body).direction === 'ltr', 'visually ltr');
            assert(!document.body.classList.contains('rtl'), 'no rtl class in English');
            ok();
        """), login='admin')

    def test_02_shop_arabic_declares_rtl(self):
        self.browser_js(self.shop_url('ar'), PRELUDE + _js(r"""
            await waitFor(() => document.querySelector('#lang'), 'boot');
            assert(sem() === 'ar/rtl', 'Arabic declares ar/rtl, got ' + sem());
            assert(getComputedStyle(document.body).direction === 'rtl', 'visually rtl');
            assert(document.body.classList.contains('rtl'), 'rtl class present');
            ok();
        """), login='admin')

    def test_03_live_switch_moves_lang_and_dir_together(self):
        """EN→AR→EN→AR: the two attributes must never disagree, at any point."""
        self.browser_js(self.shop_url('en'), PRELUDE + _js(SHOP_BOOT + r"""
            const seen = [];
            const check = want => { seen.push(sem());
                assert(sem() === want, 'expected ' + want + ', got ' + sem()
                       + ' (sequence: ' + seen.join(' -> ') + ')');
                const visual = getComputedStyle(document.body).direction;
                assert(visual === want.split('/')[1],
                       'declared ' + sem() + ' but computed direction is ' + visual);
                assert(document.body.classList.contains('rtl') === (want === 'ar/rtl'),
                       'body.rtl disagrees with ' + sem());
                assert(de().scrollWidth - de().clientWidth <= 1,
                       'overflow after switch: ' + (de().scrollWidth - de().clientWidth));
            };
            check('en/ltr');
            for (const want of ['ar/rtl', 'en/ltr', 'ar/rtl']) {
                document.querySelector('#lang').click(); await sleep(800); check(want);
            }
            ok();
        """), login='admin')

    def test_04_accessible_names_follow_the_switch(self):
        """C5's localised stepper names and C5.1's direction must move together."""
        self.browser_js(self.shop_url('en'), PRELUDE + _js(SHOP_BOOT + r"""
            const names = () => [...document.querySelectorAll('.mz-stepper__btn')]
                .map(b => b.getAttribute('aria-label'));
            const EN = ['Decrease quantity', 'Increase quantity'];
            const AR = ['تقليل الكمية', 'زيادة الكمية'];
            const all = w => names().length >= 2 && names().every(n => w.includes(n));
            assert(all(EN) && sem() === 'en/ltr', 'English names + en/ltr');
            document.querySelector('#lang').click(); await sleep(800);
            assert(all(AR), 'Arabic names after switch: ' + JSON.stringify(names()));
            assert(sem() === 'ar/rtl', 'and ar/rtl, got ' + sem());
            document.querySelector('#lang').click(); await sleep(800);
            assert(all(EN), 'English names again: ' + JSON.stringify(names()));
            assert(sem() === 'en/ltr', 'and en/ltr, got ' + sem());
            ok();
        """), login='admin')

    def test_05_quantity_and_content_survive_the_switch(self):
        """The direction fix must not disturb content, bidi or the cart."""
        self.browser_js(self.shop_url('en'), PRELUDE + _js(SHOP_BOOT + r"""
            const prices = () => [...document.querySelectorAll('#grid .prod .pp')]
                .slice(0, 4).map(e => e.textContent.trim()).join('|');
            const qty = () => (document.querySelector('.mz-stepper__value') || {}).textContent;
            const p0 = prices(), q0 = qty();
            assert(p0.length, 'prices rendered');
            document.querySelector('#lang').click(); await sleep(800);
            assert(prices() === p0, 'price strings must not reorder in RTL: ' + prices());
            assert(qty() === q0, 'quantity preserved across the switch');
            document.querySelector('#lang').click(); await sleep(800);
            assert(prices() === p0, 'price strings identical again');
            assert(qty() === q0, 'quantity still preserved');
            ok();
        """), login='admin')

    # ==================================================================
    # B — prefers-reduced-motion, proved at runtime
    # ==================================================================
    def test_10_reduced_motion_is_really_emulated(self):
        """F11 said this could not be emulated. It can — both states, proved."""
        for value, expected in (('reduce', 'true'), ('no-preference', 'false')):
            self.media_js(self.shop_url('en'), r"""
                const m = matchMedia('(prefers-reduced-motion: reduce)').matches;
                assert(String(m) === %r, 'reduce matches should be %s here, got ' + m);
                assert(matchMedia('(prefers-reduced-motion: no-preference)').matches === !m,
                       'the two states are mutually exclusive');
                ok();
            """ % (expected, expected), {'prefers-reduced-motion': value})

    def test_11_canonical_spinner_animates_normally(self):
        self.media_js(self.shop_url('en'), r"""
            assert(!matchMedia('(prefers-reduced-motion: reduce)').matches, 'no-preference active');
            const s = probe('mz-spinner');
            const cs = getComputedStyle(s);
            assert(cs.animationName !== 'none', 'spinner animates normally, got ' + cs.animationName);
            assert(parseFloat(cs.animationDuration) > 0, 'with a real duration: ' + cs.animationDuration);
            assert(cs.animationIterationCount === 'infinite', 'continuously: ' + cs.animationIterationCount);
            s.remove(); ok();
        """, {'prefers-reduced-motion': 'no-preference'})

    def test_12_canonical_spinner_stops_but_stays_visible(self):
        self.media_js(self.shop_url('en'), r"""
            assert(matchMedia('(prefers-reduced-motion: reduce)').matches, 'reduce active');
            const s = probe('mz-spinner');
            const cs = getComputedStyle(s);
            assert(cs.animationName === 'none',
                   'spinner must STOP under reduce, got ' + cs.animationName
                   + ' (' + cs.animationDuration + ', ' + cs.animationIterationCount + ')');
            // the cue must not disappear: still sized, still bordered, still contrasting
            const r = s.getBoundingClientRect();
            assert(r.width > 0 && r.height > 0, 'loading cue keeps a box');
            assert(parseFloat(cs.borderTopWidth) > 0, 'loading cue keeps its ring');
            assert(cs.borderTopColor !== cs.borderBottomColor,
                   'a static arc remains distinguishable from the track ('
                   + cs.borderTopColor + ' vs ' + cs.borderBottomColor + ')');
            assert(cs.visibility !== 'hidden' && cs.display !== 'none' && cs.opacity !== '0',
                   'loading cue stays visible');
            s.remove(); ok();
        """, {'prefers-reduced-motion': 'reduce'})

    def test_13_kds_spinner_stops_but_stays_visible(self):
        self.media_js('/mezze/kds', r"""
            await waitFor(() => document.querySelector('.mz-kds-app,.mz-kds-splash,.mz-kds-state'),
                          'kds shell');
            assert(matchMedia('(prefers-reduced-motion: reduce)').matches, 'reduce active');
            const s = document.querySelector('.mz-kds-spinner') || probe('mz-kds-spinner');
            const cs = getComputedStyle(s);
            assert(cs.animationName === 'none',
                   'KDS spinner must STOP under reduce, got ' + cs.animationName);
            assert(parseFloat(cs.borderTopWidth) > 0, 'KDS loading cue keeps its ring');
            assert(cs.borderTopColor !== cs.borderBottomColor, 'static arc remains');
            ok();
        """, {'prefers-reduced-motion': 'reduce'})

    def test_14_kds_late_meaning_survives_without_motion(self):
        """P3G: LATE may use motion as an EXTRA cue, never as the only one."""
        self.media_js('/mezze/kds', r"""
            await waitFor(() => document.querySelector('.mz-kds-app,.mz-kds-splash,.mz-kds-state'),
                          'kds shell');
            assert(matchMedia('(prefers-reduced-motion: reduce)').matches, 'reduce active');
            const card = probe('mz-card mz-kds-card mz-kds-card--late');
            const timer = probe('mz-kds-timer', card);
            const cs = getComputedStyle(timer);
            assert(cs.animationName === 'none',
                   'the LATE pulse must stop under reduce, got ' + cs.animationName);
            // meaning must survive in colour-independent, motion-independent form
            const cardCs = getComputedStyle(card);
            assert(parseFloat(cardCs.borderTopWidth) > 0, 'LATE keeps a border');
            assert(cardCs.borderTopColor !== 'rgba(0, 0, 0, 0)', 'LATE border is painted');
            card.remove(); ok();
        """, {'prefers-reduced-motion': 'reduce'})

    def test_15_status_dot_pulse_stops(self):
        self.media_js(self.shop_url('en'), r"""
            assert(matchMedia('(prefers-reduced-motion: reduce)').matches, 'reduce active');
            const s = probe('mz-status mz-status--active');
            const dot = probe('mz-status__dot', s);
            assert(getComputedStyle(dot).animationName === 'none',
                   'the live/active dot must stop pulsing under reduce, got '
                   + getComputedStyle(dot).animationName);
            s.remove(); ok();
        """, {'prefers-reduced-motion': 'reduce'})

    def test_16_finite_motion_respects_the_preference(self):
        """Dialogs, toasts and chips use transitions — those must not run under reduce."""
        self.media_js(self.shop_url('en'), r"""
            assert(matchMedia('(prefers-reduced-motion: reduce)').matches, 'reduce active');
            // measured in normal mode first: toast 0.2s, stepper/chip/nav 0.1s
            // transitions, and the dialog panel a finite 0.14s mz-dialog-pop.
            const cases = [['mz-alert mz-alert--toast', 'toast'],
                           ['mz-stepper__btn', 'stepper button'],
                           ['mz-filter-chip', 'filter chip'],
                           ['mz-nav__item', 'nav item'],
                           ['mz-dialog__panel', 'dialog panel'],
                           ['mz-dialog__backdrop', 'dialog backdrop']];
            const bad = [];
            for (const [cls, label] of cases) {
                const e = probe(cls); const cs = getComputedStyle(e);
                const dur = (cs.transitionDuration || '').split(',')
                    .map(v => parseFloat(v) || 0).reduce((a, b) => Math.max(a, b), 0);
                const anim = (cs.animationDuration || '').split(',')
                    .map(v => parseFloat(v) || 0).reduce((a, b) => Math.max(a, b), 0);
                if (dur > 0.05 || (cs.animationName !== 'none' && anim > 0.05)) {
                    bad.push(label + ' transition=' + cs.transitionDuration
                             + ' animation=' + cs.animationName + '/' + cs.animationDuration);
                }
                e.remove();
            }
            assert(bad.length === 0, 'finite motion still running under reduce: ' + bad.join(' | '));
            ok();
        """, {'prefers-reduced-motion': 'reduce'})

    def test_17_no_continuous_motion_survives_reduce(self):
        """Sweep every element actually rendered: nothing may animate forever."""
        for url in (self.shop_url('ar'), '/mezze_bridge/static/kiosk.html?store=%s' % STORE,
                    '/mezze/kds'):
            self.media_js(url, r"""
                await waitFor(() => document.body && document.body.children.length, 'body');
                await sleep(800);
                assert(matchMedia('(prefers-reduced-motion: reduce)').matches, 'reduce active');
                const running = [];
                for (const e of document.querySelectorAll('*')) {
                    const cs = getComputedStyle(e);
                    if (cs.animationName !== 'none'
                        && cs.animationIterationCount.split(',').some(v => v.trim() === 'infinite')
                        && parseFloat(cs.animationDuration) > 0) {
                        running.push((e.id || e.className || e.tagName) + ':' + cs.animationName);
                    }
                }
                assert(running.length === 0,
                       'continuous animation under reduce: ' + running.slice(0, 5).join(', '));
                ok();
            """, {'prefers-reduced-motion': 'reduce'})

    def test_18_emulation_resets(self):
        """A later test must not inherit the override."""
        self.browser_js(self.shop_url('en'), PRELUDE + _js(r"""
            assert(!matchMedia('(prefers-reduced-motion: reduce)').matches,
                   'no emulation leaks into a plain browser_js run');
            ok();
        """), login='admin')

    def test_19_responsive_switch_has_no_overflow(self):
        """The direction fix must hold at the storefront's real widths.

        ``resize_window`` does not change the top-level CSS viewport in this environment
        (F4–F9 §method), so this uses the established same-origin iframe harness: the
        iframe's ``innerWidth`` IS a real CSS viewport and every case asserts it matches
        the intended width before measuring anything.
        """
        self.browser_js(self.shop_url('en'), PRELUDE + _js(r"""
            const url = %r;
            const f = document.createElement('iframe');
            f.style.border = '0'; f.style.height = '820px';
            document.body.appendChild(f);
            const load = (w) => new Promise(res => {
                f.style.width = w + 'px';
                f.onload = () => setTimeout(res, 2200);
                f.src = url + '&nc=' + Date.now() + '&w=' + w;
            });
            const bad = [];
            for (const w of [360, 390, 430, 768]) {
                await load(w);
                const cw = f.contentWindow, cd = f.contentDocument;
                assert(cw.innerWidth === w,
                       'iframe is a real ' + w + 'px viewport, got ' + cw.innerWidth);
                await waitFor(() => cd.querySelector('#lang'), 'shop boot at ' + w);
                const state = () => cd.documentElement.lang + '/'
                                    + cd.documentElement.getAttribute('dir');
                const ovf = () => cd.documentElement.scrollWidth - cd.documentElement.clientWidth;
                const painted = () => cw.getComputedStyle(cd.body).direction;
                for (const want of ['en/ltr', 'ar/rtl', 'en/ltr']) {
                    if (state() !== want) { cd.querySelector('#lang').click(); await sleep(700); }
                    if (state() !== want) bad.push(w + ': expected ' + want + ' got ' + state());
                    if (painted() !== want.split('/')[1]) {
                        bad.push(w + ': declared ' + state() + ' painted ' + painted());
                    }
                    if (ovf() > 1) bad.push(w + ' ' + state() + ': overflow ' + ovf() + 'px');
                    // the controls a customer needs must stay reachable at every width
                    if (!cd.querySelector('#grid .prod')) bad.push(w + ': no menu tiles');
                    if (!cd.querySelector('#cats button, .cat')) bad.push(w + ': no categories');
                }
            }
            f.remove();
            assert(bad.length === 0, bad.join(' | '));
            ok();
        """ % self.shop_url('en')), login='admin')
