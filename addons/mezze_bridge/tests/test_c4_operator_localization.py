"""FINAL-C4 — bilingual localisation of the two remaining operator boards.

``courses.html`` is the waiter's **meal-coursing** board (hold / fire courses for a
table — nothing educational) and ``drivethru.html`` is the drive-thru lane board. Both
shipped English-only. C4 gives them the localisation contract that ``onboarding.html``
already used — a page-local ``T = {en, ar}`` dictionary plus ``data-t`` markup hooks —
rather than inventing a sixth mechanism.

The tests below lock three separate things:

* the dictionaries themselves (parity, coverage, no orphans, glossary agreement),
* the *architecture* (no new localisation mechanism, no new storage key),
* what a browser actually renders in each language.

The inventory comes from ``_c4_localization``, which is also what the closure report was
written from, so the two cannot drift apart.
"""
import re

from odoo.tests import tagged

from . import _c4_localization as c4
from .common import MezzeHttpCase

# Latin strings that stay Latin on purpose. Kept as an explicit allowlist so nothing can
# quietly join it: brand, and the two-letter language affordance on the toggle itself.
LATIN_BY_DESIGN = {'brand', 'langbtn'}

ARABIC_RE = re.compile(r'[؀-ۿ]')
ARABIC_INDIC_RE = re.compile(r'[٠-٩۰-۹]')

# The C2 glossary is the tie-breaker for shared concepts. Only terms that also exist in
# the staff apps are pinned here — page-specific wording is free, shared wording is not.
GLOSSARY = {
    'courses.html': {
        'hold': 'تأجيل',        # Hold (course) — must stay distinct from Park/تعليق
        'table': 'طاولة',
    },
    'drivethru.html': {
        'table': None,
    },
}

PRELUDE = (
    "function assert(c,m){if(!c)throw new Error('assert: '+m);}"
    "function waitFor(f,l,ms){ms=ms||15000;var t0=Date.now();"
    "return new Promise(function(res,rej){(function p(){try{if(f())return res(true);}catch(e){}"
    "if(Date.now()-t0>ms)return rej(new Error('timeout: '+l));setTimeout(p,100);})();});}"
    "function ok(){console.log('test successful');}"
)


def _js(body):
    return "(async () => {\n" + body + "\n})().catch(e => console.error(e.message || e));"


@tagged('post_install', '-at_install', 'mezze_c4')
class TestOperatorBoardLocalization(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    # ------------------------------------------------------------------
    # dictionaries
    # ------------------------------------------------------------------
    def test_01_both_boards_have_a_dictionary(self):
        for page in c4.PAGES:
            self.assertIsNotNone(c4.audit(page),
                                 '%s must declare a T={en,ar} dictionary' % page)

    def test_02_english_and_arabic_keys_are_paired(self):
        for page in c4.PAGES:
            a = c4.audit(page)
            self.assertFalse(a['en'] - a['ar'], '%s: keys with no Arabic: %s'
                             % (page, sorted(a['en'] - a['ar'])))
            self.assertFalse(a['ar'] - a['en'], '%s: Arabic keys with no English: %s'
                             % (page, sorted(a['ar'] - a['en'])))
            self.assertGreaterEqual(len(a['en']), 20,
                                    '%s: a board this size cannot be covered by %d strings'
                                    % (page, len(a['en'])))

    def test_03_english_is_still_there(self):
        """C4 localises; it must not replace English. Both pages stay bilingual."""
        for page in c4.PAGES:
            a = c4.audit(page)
            en_block = re.search(r"en:\{(.*?)\},\s*\n?\s*ar:\{", a['src'], re.S).group(1)
            values = re.findall(r":\s*'([^']*)'", en_block)
            self.assertTrue(values, '%s: English block has no values' % page)
            for v in values:
                self.assertTrue(v.strip(), '%s: empty English value' % page)
                self.assertFalse(ARABIC_RE.search(v),
                                 '%s: Arabic leaked into the English dictionary (%r)' % (page, v))

    def test_04_arabic_values_are_arabic(self):
        for page in c4.PAGES:
            a = c4.audit(page)
            ar_block = re.search(r"ar:\{(.*?)\}\};", a['src'], re.S).group(1)
            for key, value in re.findall(r"(\w+)\s*:\s*'([^']*)'", ar_block):
                self.assertTrue(value.strip(), '%s: %s has an empty Arabic value' % (page, key))
                if key in LATIN_BY_DESIGN:
                    continue
                self.assertTrue(
                    ARABIC_RE.search(value),
                    '%s: %s=%r carries no Arabic script and is not allowlisted'
                    % (page, key, value))

    def test_05_every_hook_and_call_resolves(self):
        """A data-t / t() naming a key that does not exist renders blank in production."""
        for page in c4.PAGES:
            a = c4.audit(page)
            unknown = sorted((a['hooks'] | a['used']) - a['en'])
            self.assertFalse(unknown, '%s: references to undefined keys: %s' % (page, unknown))

    def test_06_no_orphan_translations(self):
        """Every translated key must actually reach the page."""
        for page in c4.PAGES:
            a = c4.audit(page)
            orphans = sorted(a['en'] - (a['hooks'] | a['used']))
            self.assertFalse(orphans, '%s: keys nothing references: %s' % (page, orphans))

    def test_07_identifiers_and_digits_are_not_localised(self):
        """Latin digits stay Latin — order numbers, lane numbers, timers, money."""
        for page in c4.PAGES:
            a = c4.audit(page)
            block = re.search(r"var T=\{(.*?)\}\};", a['src'], re.S).group(1)
            self.assertFalse(ARABIC_INDIC_RE.search(block),
                             '%s: Arabic-Indic digits in the dictionary — the product uses '
                             'Latin digits everywhere (order refs, prices, timers)' % page)

    def test_08_shared_terms_follow_the_glossary(self):
        for page, terms in GLOSSARY.items():
            a = c4.audit(page)
            ar_block = re.search(r"ar:\{(.*?)\}\};", a['src'], re.S).group(1)
            values = dict(re.findall(r"(\w+)\s*:\s*'([^']*)'", ar_block))
            for key, expected in terms.items():
                if expected is None or key not in values:
                    continue
                self.assertIn(expected, values[key],
                              '%s: %s should use the glossary term %r, got %r'
                              % (page, key, expected, values[key]))

    # ------------------------------------------------------------------
    # architecture — no sixth localisation mechanism
    # ------------------------------------------------------------------
    def test_09_reuses_the_existing_page_local_contract(self):
        """Same shape onboarding.html already shipped: T={en,ar} + data-t + a toggle."""
        for page in c4.PAGES:
            a = c4.audit(page)
            src = a['src']
            self.assertIn('data-t="', src, '%s: no data-t markup hooks' % page)
            self.assertRegex(src, r"id=\"lang\"", '%s: no language toggle control' % page)
            self.assertRegex(src, r"function\s+applyI18n", '%s: no applyI18n()' % page)
            # nothing new invented
            self.assertNotIn('_t(', src, '%s: the Odoo JS catalogue is for the Owl apps, '
                                         'not for a static page' % page)
            self.assertNotRegex(src, r"/web/webclient/translations",
                                '%s: must not pull the Owl catalogue' % page)
            self.assertNotRegex(src, r"\.json['\"]\s*\)\s*;?\s*//?\s*i18n|i18n\.json",
                                '%s: must not introduce a translation file' % page)

    def test_10_reuses_the_shared_preference_key(self):
        for page in c4.PAGES:
            src = c4.audit(page)['src']
            self.assertIn("'mezze_shop_lang'", src,
                          '%s: must reuse the shared language preference key' % page)
            # mzSettings.v1 is the canonical theme/FOUC guard key introduced by C1.
            known = {'mezze_shop_lang', 'mzSettings.v1'}
            keys = set(re.findall(r"localStorage\.\w+\('([^']+)'", src))
            self.assertEqual(keys - known, set(),
                             '%s: introduced a new storage key: %s'
                             % (page, sorted(keys - known)))

    def test_11_direction_and_language_are_stamped(self):
        for page in c4.PAGES:
            src = c4.audit(page)['src']
            self.assertRegex(src, r"setAttribute\('dir'\s*,\s*lang\s*===\s*'ar'\s*\?\s*'rtl'",
                             '%s: applyI18n must set dir from the language' % page)
            self.assertRegex(src, r"\.lang\s*=\s*lang", '%s: applyI18n must set lang' % page)

    def test_12_no_business_or_route_change(self):
        """C4 is presentation only — the boards' endpoints must be untouched."""
        expected = {
            'courses.html': ('/courses/board', '/courses/hold', '/courses/fire'),
            'drivethru.html': ('/drivethru/board',),
        }
        for page, routes in expected.items():
            src = c4.audit(page)['src']
            for route in routes:
                self.assertIn(route, src, '%s: route %s disappeared' % (page, route))

    # ------------------------------------------------------------------
    # rendered behaviour
    # ------------------------------------------------------------------
    def _render_js(self, expect_lang):
        rtl = 'true' if expect_lang == 'ar' else 'false'
        return PRELUDE + _js(r"""
            await waitFor(() => document.body && document.querySelector('#lang'), 'boot');
            const de = document.documentElement, want = '%s', rtl = %s;
            assert(de.lang === want, 'lang is ' + de.lang + ', expected ' + want);
            assert(de.getAttribute('dir') === (rtl ? 'rtl' : 'ltr'),
                   'dir is ' + de.getAttribute('dir'));
            assert(de.scrollWidth - de.clientWidth <= 1,
                   'horizontal overflow ' + (de.scrollWidth - de.clientWidth) + 'px');
            if (rtl) {
                assert(/Arabic/.test(getComputedStyle(document.body).fontFamily),
                       'Arabic face not applied: ' + getComputedStyle(document.body).fontFamily);
            }
            // every static hook must have been filled in
            const empty = [...document.querySelectorAll('[data-t]')]
                .filter(e => !(e.textContent || '').trim());
            assert(empty.length === 0, empty.length + ' data-t nodes rendered empty');
            if (rtl) {
                const latin = [...document.querySelectorAll('[data-t]')]
                    .filter(e => /[A-Za-z]{3,}/.test((e.textContent || '').trim()));
                assert(latin.length === 0, 'untranslated in Arabic: '
                       + latin.map(e => e.textContent.trim()).join(' | '));
            }
            // touch targets survive both languages
            const small = [...document.querySelectorAll('button')].filter(b => {
                const r = b.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && (r.height < 43.5 || r.width < 43.5); });
            assert(small.length === 0, 'sub-44px controls: '
                   + small.map(b => (b.id || b.className) + ' '
                     + Math.round(b.getBoundingClientRect().width) + 'x'
                     + Math.round(b.getBoundingClientRect().height)).join(', '));
            ok();
        """ % (expect_lang, rtl))

    def test_13_courses_renders_english(self):
        self.browser_js('/mezze_bridge/static/courses.html?lang=en',
                        self._render_js('en'), login='admin')

    def test_14_courses_renders_arabic(self):
        self.browser_js('/mezze_bridge/static/courses.html?lang=ar',
                        self._render_js('ar'), login='admin')

    def test_15_drivethru_renders_english(self):
        self.browser_js('/mezze_bridge/static/drivethru.html?lang=en',
                        self._render_js('en'), login='admin')

    def test_16_drivethru_renders_arabic(self):
        self.browser_js('/mezze_bridge/static/drivethru.html?lang=ar',
                        self._render_js('ar'), login='admin')

    def test_18_lane_and_header_controls_are_touch_sized(self):
        """The controls that only exist once a board has live rows.

        ``test_13``-``test_16`` load the boards unprovisioned, so no lane card is in the
        DOM and their touch check silently covers only the header. (Verified: reverting
        the ``.act`` fix left ``test_16`` green.) These probes carry the real product
        classes, so they measure the actual CSS contract instead of fixture data.
        """
        probes = {
            'drivethru.html': ('act', 'act p', 'act o', 'act x'),
            'courses.html': ('hbtn', 'hbtn ghost'),
        }
        for page, classes in probes.items():
            self.browser_js('/mezze_bridge/static/%s' % page, PRELUDE + _js(r"""
                await waitFor(() => document.body, 'body');
                const classes = %s, bad = [];
                for (const cls of classes) {
                    const b = document.createElement('button');
                    b.className = cls; b.textContent = '✕';
                    document.body.appendChild(b);
                    const r = b.getBoundingClientRect();
                    if (r.height < 43.5 || r.width < 43.5) {
                        bad.push(cls + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
                    }
                    b.remove();
                }
                assert(bad.length === 0, 'sub-44px lane/header controls: ' + bad.join(', '));
                ok();
            """ % repr(list(classes))), login='admin')

    def test_19_js_built_strings_are_localised_at_runtime(self):
        """Copy written by JS, not present in the markup, must follow the language.

        Both boards write a connection/status line from the dictionary when they cannot
        reach the API, which is exactly the unprovisioned case these tests run in — so
        it is a genuine runtime-translated string, not a ``data-t`` substitution.
        """
        expect = {
            'courses.html': ('#loading', 'تعذّر الاتصال.'),
            'drivethru.html': ('#connlbl', 'غير متصل'),
        }
        for page, (sel, arabic) in expect.items():
            self.browser_js('/mezze_bridge/static/%s?lang=ar' % page, PRELUDE + _js(r"""
                const sel = %r, want = %r;
                await waitFor(() => { const e = document.querySelector(sel);
                    return e && (e.textContent || '').trim() === want; },
                    'JS-built string localised (got: ' +
                    ((document.querySelector(sel) || {}).textContent || '') + ')');
                assert(document.documentElement.lang === 'ar', 'still Arabic');
                ok();
            """ % (sel, arabic)), login='admin')

    def test_20_accessible_names_are_localised_not_hardcoded(self):
        """No English accessible name may be baked into JS-built markup on these boards.

        This is the defect that still exists on shop/qr/kiosk (recorded as a separate
        certification condition); it must never appear on the two boards C4 owns.
        """
        for page in c4.PAGES:
            src = c4.audit(page)['src']
            script = src[src.index('<script>', src.index('</head>')):]
            literals = re.findall(r'aria-label="([^"\'+]+)"', script)
            self.assertFalse(literals,
                             '%s builds a hardcoded accessible name in JS: %s'
                             % (page, literals))
            # Every accessible name must come from the dictionary, by either route:
            # a t() call for JS-built markup, or a data-tal hook for static markup.
            for key in ('dec', 'inc', 'close'):
                self.assertTrue("t('%s')" % key in src or 'data-tal="%s"' % key in src,
                                '%s takes its %r accessible name from the dictionary'
                                % (page, key))

    def test_17_toggle_switches_both_ways_and_persists(self):
        for page in c4.PAGES:
            self.browser_js('/mezze_bridge/static/%s?lang=en' % page, PRELUDE + _js(r"""
                await waitFor(() => document.querySelector('#lang'), 'toggle');
                const de = document.documentElement, btn = document.querySelector('#lang');
                assert(de.lang === 'en', 'starts English');
                btn.click();
                await waitFor(() => de.lang === 'ar', 'switched to Arabic');
                assert(de.getAttribute('dir') === 'rtl', 'rtl after switch');
                assert(localStorage.getItem('mezze_shop_lang') === 'ar', 'preference stored');
                document.querySelector('#lang').click();
                await waitFor(() => de.lang === 'en', 'switched back to English');
                assert(de.getAttribute('dir') === 'ltr', 'ltr after switching back');
                assert(localStorage.getItem('mezze_shop_lang') === 'en',
                       'preference stored both ways');
                ok();
            """), login='admin')
