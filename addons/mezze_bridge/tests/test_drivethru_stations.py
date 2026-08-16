"""The drive-thru's stations are reachable from each other.

Moving the 10-20 car board to ``?mode=ops`` (CONV-2b) gave the order taker a way IN —
"Open operations" — and no way back. An operator who opened the board was stuck there
unless somebody edited the URL, which on a pinned lane terminal means fetching a
keyboard mid-rush. The payment and pickup windows had the same problem in reverse: they
are their own URLs and nothing on screen named the others.

A crumb trail in the header now lists every station, marks the one you are standing at,
and makes the rest one click away. What is asserted here is the NAVIGATION, not the
decoration: from each station you can reach each other station, the current one is
named rather than offered as a dead link, and the trail follows the language toggle.
"""
from odoo.tests import tagged

from .common import MezzeHttpCase

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
const crumbs = () => $$('#crumbs .dtcrumb');
const modes = () => crumbs().map(c => c.getAttribute('data-mode'));
"""

STATIONS = ('order', 'ops', 'payment', 'pickup')


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_dt_stations')
class TestDriveThruStations(MezzeHttpCase):
    fixture_profile = 'POS'

    def test_01_every_station_lists_every_station(self):
        """Whichever station a terminal is pinned to, the others are named on it."""
        for mode in STATIONS:
            self.browser_js('/mezze/drivethru?mode=%s' % mode, _js(r"""
                const HERE = "%s";
                await waitFor(() => crumbs().length, 'the station crumbs');
                const seen = modes();
                for (const m of ["order","ops","payment","pickup"]) {
                    assert(seen.includes(m), m + ' is missing from the trail: ' + seen.join(','));
                }
                const here = crumbs().filter(c => c.getAttribute('aria-current') === 'page');
                assert(here.length === 1, 'exactly one station is marked current (' + here.length + ')');
                assert(here[0].getAttribute('data-mode') === HERE,
                       'and it is this one: ' + here[0].getAttribute('data-mode'));
                assert(here[0].tagName !== 'A', 'the station you are at is not a link to itself');
                assert(here[0].textContent.trim().length > 2, 'it is NAMED: ' + here[0].textContent);
                // every control on a lane touch screen, this one included
                for (const c of crumbs()) {
                    const r = c.getBoundingClientRect();
                    assert(r.height >= 44 && r.width >= 44,
                           'crumb below the touch floor: ' + c.textContent + ' ' + r.width + 'x' + r.height);
                }
                ok();
            """ % mode), login='admin')

    def test_02_the_operations_board_is_no_longer_a_dead_end(self):
        """The defect this exists for: ops could only be left by editing the URL.

        Asserted as the LINK, not as a click: a station is a URL, and the browser's own
        navigation is not the thing under test. That the destination works is asserted
        by test_01, which loads every station in turn.
        """
        self.browser_js('/mezze/drivethru?mode=ops', _js(r"""
            await waitFor(() => crumbs().length, 'the station crumbs');
            assert(document.body.getAttribute('data-mode') === 'ops', 'we start on the board');
            const back = crumbs().find(c => c.getAttribute('data-mode') === 'order');
            assert(back, 'the order taker is offered');
            assert(back.tagName === 'A' && back.getAttribute('href'),
                   'as a real link, openable in another tab: ' + back.outerHTML.slice(0, 80));
            assert(/[?&]mode=order\b/.test(back.getAttribute('href')),
                   'pointing at the order taker: ' + back.getAttribute('href'));
            assert(new URL(back.href).pathname === location.pathname,
                   'on this same board, not some other page');
            ok();
        """), login='admin')

    def test_03_every_other_station_is_one_link_away(self):
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => crumbs().length, 'the station crumbs');
            assert(document.body.getAttribute('data-mode') === 'order', 'default is ordering');
            for (const m of ["ops","payment","pickup"]) {
                const c = crumbs().find(x => x.getAttribute('data-mode') === m);
                assert(c.tagName === 'A' && new RegExp('[?&]mode=' + m + '\\b').test(c.href),
                       m + ' is reachable: ' + c.getAttribute('href'));
            }
            // and the one you are standing at is NOT a link to itself
            const here = crumbs().find(x => x.getAttribute('aria-current') === 'page');
            assert(here.tagName !== 'A', 'the current station is named, not linked');
            ok();
        """), login='admin')

    def test_04_the_trail_is_bilingual_and_mirrors(self):
        """The board is a bilingual operator surface; a new control joins that contract."""
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => crumbs().length, 'the station crumbs');
            const english = crumbs().map(c => c.textContent.trim());
            assert(english.every(t => /[A-Za-z]/.test(t)), 'English first: ' + english.join(' | '));
            $('#lang').click();
            await waitFor(() => document.documentElement.getAttribute('dir') === 'rtl', 'switched to Arabic');
            const arabic = crumbs().map(c => c.textContent.trim());
            assert(arabic.length === english.length, 'the trail survives the switch');
            assert(arabic.every(t => /[؀-ۿ]/.test(t)),
                   'every station is translated: ' + arabic.join(' | '));
            // and it stays inside the header rather than overflowing it under RTL
            const host = $('#crumbs').getBoundingClientRect();
            const head = document.querySelector('header').getBoundingClientRect();
            assert(host.left >= head.left - 1 && host.right <= head.right + 1,
                   'the trail stays within the header (' + host.left + '-' + host.right + ')');
            ok();
        """), login='admin')

    def test_06_switching_stations_does_not_reload_the_page(self):
        """The crumbs navigate in place: same document, new station, new URL.

        Every station is drawn from the board payload the page already polls, so a
        full document load to change stations re-downloaded the page, its stylesheets
        and the whole catalogue to show data that was already in memory. Proven by a
        marker on `window`: if the document had been replaced, it would be gone.
        """
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            await waitFor(() => crumbs().length, 'the station crumbs');
            window.__mzSameDocument = 'yes';
            const fetched = [];
            const orig = window.fetch;
            window.fetch = function(u){ fetched.push(String(u)); return orig.apply(this, arguments); };

            crumbs().find(c => c.getAttribute('data-mode') === 'ops').click();
            await waitFor(() => document.body.getAttribute('data-mode') === 'ops', 'the board');
            assert(window.__mzSameDocument === 'yes',
                   'the document was replaced — this is still a full page load');
            assert(/[?&]mode=ops\b/.test(location.search), 'and the URL followed: ' + location.search);
            // the SURFACE changed, not just the attribute: the ordering workspace is
            // gone and the board's own pane is showing (asserted on layout, because a
            // fixture branch may legitimately have no cars to list)
            assert(getComputedStyle($('.ot')).display === 'none',
                   'the ordering workspace is no longer displayed');
            assert(getComputedStyle($('.modes > .queue')).display !== 'none',
                   "and the board's pane is");
            assert(!fetched.some(u => /\/bootstrap\b/.test(u)),
                   'the catalogue was NOT re-fetched: ' + fetched.join(' '));

            // and back the other way, still in the same document
            crumbs().find(c => c.getAttribute('data-mode') === 'order').click();
            await waitFor(() => document.body.getAttribute('data-mode') === 'order', 'the order taker');
            assert(window.__mzSameDocument === 'yes', 'still the same document');
            assert($$('.mz-tile').length > 0, 'with its catalogue still mounted');
            window.fetch = orig;
            ok();
        """), login='admin')

    def test_07_browser_history_follows_the_stations(self):
        """A URL that changes without history is worse than no history at all."""
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => crumbs().length, 'the station crumbs');
            window.__mzSameDocument = 'yes';
            crumbs().find(c => c.getAttribute('data-mode') === 'payment').click();
            await waitFor(() => document.body.getAttribute('data-mode') === 'payment', 'the payment window');
            history.back();
            await waitFor(() => document.body.getAttribute('data-mode') === 'order', 'back at the order taker');
            assert(!/[?&]mode=payment\b/.test(location.search),
                   'the URL came back too: ' + location.search);
            assert(window.__mzSameDocument === 'yes', 'and it did it in place');
            ok();
        """), login='admin')

    def test_05_the_crumbs_do_not_disturb_the_workspace(self):
        """A header control must not push the ordering panes around.

        Measured against ITSELF rather than against numbers copied from another test:
        the panes are measured, the trail is removed, and they are measured again.
        """
        self.browser_js('/mezze/drivethru', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            await waitFor(() => crumbs().length, 'the station crumbs');
            const w = () => [$('.mz-catside'), $('#otcart'), $('.mz-grid')]
                              .map(e => Math.round(e.getBoundingClientRect().width));
            const trail = $('#crumbs').getBoundingClientRect();
            const side = $('.mz-catside').getBoundingClientRect();
            assert(trail.bottom <= side.top + 1, 'the trail sits above the workspace, not in it');
            const before = w();
            $('#crumbs').remove();
            await new Promise(r => setTimeout(r, 200));
            const after = w();
            assert(before.join(',') === after.join(','),
                   'the panes are the same width with and without the trail: '
                   + before.join(',') + ' vs ' + after.join(','));
            ok();
        """), login='admin')
