"""FINAL-C5 — localised accessible names on the customer quantity steppers.

The quantity buttons on `shop.html`, `qr.html` and `kiosk.html` are icon controls
(`−` / `+`), so their visible content is not a usable action name and an `aria-label`
supplies it. Those labels were hardcoded English, which meant an Arabic customer using
assistive technology heard "Decrease quantity" on an otherwise Arabic page.

Two independent layers are proved here:

* **DOM** — the rendered `aria-label` of a real, interacted-with stepper in each language.
* **Accessibility tree** — the *computed* AX name, read over the DevTools Protocol
  (`Accessibility.queryAXTree`). Reading `getAttribute('aria-label')` alone would only
  prove an attribute exists, not that the browser computed it as the name.

Neither is a screen-reader walkthrough, and none is claimed.
"""
import contextlib
import re
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import ChromeBrowser

from .common import MezzeHttpCase

STORE = 'c5store'

# The one approved pair, shared with the operator boards localised in FINAL-C4.
EN = {'dec': 'Decrease quantity', 'inc': 'Increase quantity'}
AR = {'dec': 'تقليل الكمية', 'inc': 'زيادة الكمية'}

PAGES = ('shop.html', 'qr.html', 'kiosk.html')

PRELUDE = (
    "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
    "function waitFor(f,l,ms){ms=ms||20000;var t0=Date.now();"
    "return new Promise(function(res,rej){(function p(){try{if(f())return res(true);}catch(e){}"
    "if(Date.now()-t0>ms)return rej(new Error('timeout: '+l));setTimeout(p,100);})();});}"
    "function sleep(ms){return new Promise(function(r){setTimeout(r,ms);});}"
    "function ok(){console.log('test successful');}"
    "function names(){return [].map.call(document.querySelectorAll('.mz-stepper__btn'),"
    "  function(b){return b.getAttribute('aria-label');});}"
)


def _js(body):
    return "(async () => {\n" + body + "\n})().catch(e => console.error(e.message || e));"


# Per-page driver: bring a real quantity stepper on screen, then assert its DOM names.
# Each ends with ok(); the AX query runs afterwards, while the page is still live.
DRIVERS = {
    'shop.html': r"""
        await waitFor(() => document.querySelectorAll('#grid .prod').length,
                      'shop menu (grid: ' + ((document.querySelector('#grid')||{}).innerHTML||'').slice(0,120) + ')');
        const tiles = [...document.querySelectorAll('#grid .prod')];
        for (const t of tiles.slice(0, 8)) {
            t.click(); await sleep(400);
            const add = document.querySelector('#opt-add');
            if (add && add.offsetParent) { add.click(); await sleep(400); }
            if (document.querySelector('.mz-stepper__btn')) break;
        }
        await waitFor(() => document.querySelector('.mz-stepper__btn'), 'cart stepper');
        // the cart stepper lives in the cart sheet: open it, which is also the only
        // state in which a customer can actually reach it (and measure it).
        document.querySelector('#viewcart, #cartbar button').click(); await sleep(700);
        await waitFor(() => { const b = document.querySelector('.mz-stepper__btn');
                              return b && b.getBoundingClientRect().height > 0; }, 'cart sheet open');
    """,
    'qr.html': r"""
        await waitFor(() => document.querySelectorAll('.qr-add').length, 'menu');
        for (const b of [...document.querySelectorAll('.qr-add')]) {
            b.click(); await sleep(400);
            if (document.querySelector('.mz-stepper__btn')) break;
            const x = document.querySelector('#modx'); if (x) { x.click(); await sleep(250); }
        }
        await waitFor(() => document.querySelector('.mz-stepper__btn'), 'qr stepper');
    """,
    # Kiosk V2 (the approved Claude Design): welcome -> service -> a product's detail
    # screen, which is where the customer first meets a quantity control.
    'kiosk.html': r"""
        await waitFor(() => { const b = document.querySelector('#k-start');
                              return b && !b.disabled; }, 'kiosk splash');
        document.querySelector('#k-start').click(); await sleep(400);
        const svc = document.querySelectorAll('.k-choice');
        if (svc.length) { svc[0].click(); }
        await waitFor(() => document.querySelectorAll('.k-card').length, 'kiosk menu');
        document.querySelectorAll('.k-card')[0].click(); await sleep(600);
        await waitFor(() => document.querySelector('.mz-stepper__btn'), 'kiosk stepper');
    """,
}


@tagged('post_install', '-at_install', 'mezze_c5')
class TestStepperAccessibleNames(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.store_token_%s' % self.pos_config.id, STORE)
        self.product.write({'list_price': 100.0, 'available_in_pos': True})
        # NB: never assign to self.session — HttpCase uses that for the HTTP session.
        self.pos_session = self.open_test_session()
        self.table = self.tables[0].sudo()
        if not self.table.mezze_qr_token:
            self.table.mezze_qr_token = 'c5qrtok'
        self.env.flush_all()

    # ------------------------------------------------------------------ helpers
    def url_for(self, page, lang):
        if page == 'qr.html':
            # qr.html takes its language from navigator.language by design and has no
            # ?lang= parameter; the AR run drives its in-page toggle instead.
            return '/mezze_bridge/static/qr.html?table=%s&qr=%s' % (
                self.table.id, self.table.mezze_qr_token)
        return '/mezze_bridge/static/%s?store=%s&lang=%s' % (page, STORE, lang)

    @contextlib.contextmanager
    def ax_capture(self, queries, sink):
        """Run CDP Accessibility queries once the page's own JS has succeeded.

        ``_wait_code_ok`` returns with the document still open, which is the only
        moment the interacted-with stepper exists AND the browser is still alive.
        """
        original = ChromeBrowser._wait_code_ok

        def wrapped(browser_self, code, timeout, error_checker=None):
            result = original(browser_self, code, timeout, error_checker=error_checker)
            browser_self._websocket_request('DOM.enable')
            browser_self._websocket_request('Accessibility.enable')
            # _websocket_request already unwraps the CDP envelope's "result".
            doc = browser_self._websocket_request('DOM.getDocument', params={'depth': 1})
            root = doc['root']['nodeId']
            for label, params in queries:
                res = browser_self._websocket_request('Accessibility.queryAXTree', params={
                    'nodeId': root, **params})
                sink.setdefault(label, []).extend(res.get('nodes', []))
            return result

        with patch.object(ChromeBrowser, '_wait_code_ok', wrapped):
            yield

    def run_page(self, page, lang, switch=False):
        """Drive the page, assert DOM names, and capture computed AX names."""
        want = AR if lang == 'ar' else EN
        other = EN if lang == 'ar' else AR
        toggle = ''
        if switch:
            sel = '#k-lang' if page == 'kiosk.html' else '#lang'
            toggle = ("document.querySelector('%s').click(); await sleep(900);" % sel)

        body = DRIVERS[page] + toggle + r"""
            const want = %r, other = %r;
            const got = names();
            assert(got.length >= 2, 'a real stepper is on screen (got ' + got.length + ')');
            assert(got.every(n => n === want.dec || n === want.inc),
                   'every stepper name is in the active language: ' + JSON.stringify(got));
            assert(got.some(n => n === want.dec), 'decrease name present');
            assert(got.some(n => n === want.inc), 'increase name present');
            assert(!got.some(n => n === other.dec || n === other.inc),
                   'no stale name from the other language: ' + JSON.stringify(got));
            const btn = document.querySelector('.mz-stepper__btn');
            assert(btn.tagName === 'BUTTON' && btn.getAttribute('type') === 'button',
                   'native <button type=button>');
            const r = btn.getBoundingClientRect();
            assert(r.width >= 43.5 && r.height >= 43.5,
                   'stepper stays >=44px: ' + Math.round(r.width) + 'x' + Math.round(r.height));
            ok();
        """ % (want, other)

        sink = {}
        queries = [
            ('want_dec', {'accessibleName': want['dec'], 'role': 'button'}),
            ('want_inc', {'accessibleName': want['inc'], 'role': 'button'}),
            ('wrong_dec', {'accessibleName': other['dec'], 'role': 'button'}),
            ('wrong_inc', {'accessibleName': other['inc'], 'role': 'button'}),
        ]
        with self.ax_capture(queries, sink):
            self.browser_js(self.url_for(page, lang), PRELUDE + _js(body), login='admin')
        return sink

    def assert_ax(self, page, lang, sink):
        want = AR if lang == 'ar' else EN
        for key, label in (('want_dec', want['dec']), ('want_inc', want['inc'])):
            nodes = sink.get(key, [])
            self.assertTrue(nodes, '%s [%s]: the accessibility tree exposes no button named %r'
                                   % (page, lang, label))
            for node in nodes:
                self.assertEqual(node.get('role', {}).get('value'), 'button',
                                 '%s [%s]: %r is exposed as a button' % (page, lang, label))
                self.assertEqual(node.get('name', {}).get('value'), label,
                                 '%s [%s]: computed AX name' % (page, lang))
        for key in ('wrong_dec', 'wrong_inc'):
            self.assertFalse(sink.get(key), '%s [%s]: a wrong-language AX name is still exposed'
                                            % (page, lang))

    # ------------------------------------------------------------------ static contract
    def test_01_no_hardcoded_accessible_name_bypasses(self):
        """The generation paths must not bake an English name into markup.

        The English *dictionary values* legitimately contain these phrases, so the ban
        is on the markup pattern (`aria-label="Decrease quantity"`), not on the string.
        """
        from odoo.tools import file_open
        for page in PAGES:
            with file_open('mezze_bridge/static/%s' % page, 'r') as fh:
                src = fh.read()
            for phrase in (EN['dec'], EN['inc']):
                self.assertNotIn('aria-label="%s"' % phrase, src,
                                 '%s bypasses localisation with a hardcoded %r' % (page, phrase))
                self.assertIn("%s'" % phrase, src,
                              '%s keeps %r as an English dictionary value' % (page, phrase))
            # ...and the names must come from the dictionary
            self.assertIn("t('dec')", src, '%s builds the decrease name from t()' % page)
            self.assertIn("t('inc')", src, '%s builds the increase name from t()' % page)

    def test_02_translation_keys_exist_in_both_languages(self):
        from odoo.tools import file_open
        for page in PAGES:
            with file_open('mezze_bridge/static/%s' % page, 'r') as fh:
                src = fh.read()
            for key, en, ar in (('dec', EN['dec'], AR['dec']), ('inc', EN['inc'], AR['inc'])):
                self.assertEqual(src.count("%s:'" % key), 2,
                                 '%s defines %r exactly once per language' % (page, key))
                self.assertIn("%s:'%s'" % (key, en), src, '%s English %r' % (page, key))
                self.assertIn("%s:'%s'" % (key, ar), src, '%s Arabic %r' % (page, key))

    def test_03_arabic_values_are_arabic_and_consistent(self):
        from odoo.tools import file_open
        arabic = re.compile(r'[؀-ۿ]')
        seen = {}
        for page in PAGES:
            with file_open('mezze_bridge/static/%s' % page, 'r') as fh:
                src = fh.read()
            for key in ('dec', 'inc'):
                value = re.search(r"%s:'([^']*)'" % key, src.split("ar:{", 1)[1]).group(1)
                self.assertTrue(value.strip(), '%s: %r is empty in Arabic' % (page, key))
                self.assertTrue(arabic.search(value), '%s: %r is not Arabic (%r)'
                                                      % (page, key, value))
                self.assertNotIn(EN[key], value, '%s: %r still English' % (page, key))
                seen.setdefault(key, set()).add(value)
        for key, values in seen.items():
            self.assertEqual(len(values), 1,
                             'the three customer pages disagree on %r: %s' % (key, sorted(values)))

    def test_04_operator_boards_use_the_same_pair(self):
        """C4's boards and C5's customer pages must not drift apart."""
        from odoo.tools import file_open
        for page in ('courses.html', 'drivethru.html'):
            with file_open('mezze_bridge/static/%s' % page, 'r') as fh:
                src = fh.read()
            for key in ('dec', 'inc'):
                self.assertIn("%s:'%s'" % (key, EN[key]), src, '%s English %r' % (page, key))
                self.assertIn("%s:'%s'" % (key, AR[key]), src, '%s Arabic %r' % (page, key))

    # ------------------------------------------------------------------ rendered + AX
    def test_10_shop_english(self):
        self.assert_ax('shop.html', 'en', self.run_page('shop.html', 'en'))

    def test_11_shop_arabic(self):
        self.assert_ax('shop.html', 'ar', self.run_page('shop.html', 'ar'))

    def test_12_qr_english(self):
        self.assert_ax('qr.html', 'en', self.run_page('qr.html', 'en'))

    def test_13_qr_arabic_via_toggle(self):
        # qr.html has no ?lang=; the guest switches with the in-page control.
        self.assert_ax('qr.html', 'ar', self.run_page('qr.html', 'ar', switch=True))

    def test_14_kiosk_english(self):
        self.assert_ax('kiosk.html', 'en', self.run_page('kiosk.html', 'en'))

    def test_15_kiosk_arabic(self):
        self.assert_ax('kiosk.html', 'ar', self.run_page('kiosk.html', 'ar'))

    #: One page per test. Each browser_js builds its own Chrome, so looping both
    #: surfaces meant the second had to win its CDP handshake right after the first
    #: was torn down -- dying in setup, before any of this ran, when it lost. The
    #: script stays shared: both surfaces must survive the switch the SAME way.

    def _check_runtime_switch(self, cases):
        """EN → AR → EN, asserting the names after every switch."""
        # A helper handed an empty list would loop zero times and report green:
        # the exact shape of a test that passes without running.
        self.assertTrue(cases, 'no case to check — the split lost its surface')
        for page in cases:
            sel = '#k-lang' if page == 'kiosk.html' else '#lang'
            body = DRIVERS[page] + r"""
                const EN = %r, AR = %r, sel = %r;
                const all = n => names().every(x => x === n.dec || x === n.inc);
                assert(all(EN), 'starts English: ' + JSON.stringify(names()));
                document.querySelector(sel).click(); await sleep(900);
                assert(document.documentElement.lang === 'ar', 'document is Arabic');
                assert(all(AR), 'Arabic after switch: ' + JSON.stringify(names())
                       + ' | lines=' + document.querySelectorAll('#cart-lines .crow,#k-lines .crow').length
                       + ' | inCart=' + [...document.querySelectorAll('.mz-stepper__btn')]
                           .map(b => !!b.closest('#cart-lines,#k-lines')).join(','));
                document.querySelector(sel).click(); await sleep(900);
                assert(document.documentElement.lang === 'en', 'document is English again');
                assert(all(EN), 'English after switching back: ' + JSON.stringify(names()));
                ok();
            """ % (EN, AR, sel)
            self.browser_js(self.url_for(page, 'en'), PRELUDE + _js(body), login='admin')

    def test_16_the_shop_switch_leaves_no_stale_name(self):
        self._check_runtime_switch(('shop.html',))

    def test_16b_the_kiosk_switch_leaves_no_stale_name(self):
        self._check_runtime_switch(('kiosk.html',))

    def test_17_quantity_behaviour_unchanged(self):
        """C5 touched only names — stepping must still add, subtract and remove."""
        # Kiosk V2: from the product's detail screen, put it in the order and open the
        # order — that is where a customer changes a quantity.
        body = DRIVERS['kiosk.html'] + r"""
            document.querySelector('#k-cta').click();
            await waitFor(() => document.querySelectorAll('.k-card').length, 'back at the menu');
            document.querySelector('#k-cta').click();
            await waitFor(() => document.querySelector('.k-line'), 'the order');
            const val = () => document.querySelector('.k-line .mz-stepper__value');
            const btns = () => [...document.querySelectorAll('.k-line .mz-stepper__btn')];
            const rows = () => document.querySelectorAll('.k-line').length;
            const start = parseInt(val().textContent.trim(), 10);
            assert(rows() === 1, 'one line to begin with, got ' + rows());
            for (let i = 0; i < 3; i++) { btns()[1].click(); await sleep(200); }
            await waitFor(() => parseInt(val().textContent.trim(), 10) === start + 3,
                          'three taps add exactly three (got ' + val().textContent + ')');
            assert(rows() === 1, 'no duplicate line was created');
            for (let i = 0; i < 2; i++) { btns()[0].click(); await sleep(200); }
            await waitFor(() => parseInt(val().textContent.trim(), 10) === start + 1,
                          'two taps subtract exactly two');
            assert(rows() === 1, 'still one line');
            ok();
        """
        self.browser_js(self.url_for('kiosk.html', 'en'), PRELUDE + _js(body), login='admin')
