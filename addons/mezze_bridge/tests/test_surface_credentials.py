# -*- coding: utf-8 -*-
"""Getting a bearer token out of the URL bar.

Three standalone screens — the lane board, the customer display and the course
station — were reachable only as static files under ``/mezze_bridge/static/``. A
static file cannot be handed a credential, so the only way to give one was
``?token=`` in the query string, which puts a bearer token into access logs, browser
history, the Referer of every link the page follows, and any URL an operator
bookmarks or shares in a group chat.

The worse half is what token that is. With no route to MINT one, the operator pastes
in whichever they have, and that is normally the shared admin token: unlimited
capability, no branch scope. On the customer display that credential is sitting in
the URL bar of a screen pointed at the public.

The lane board was fixed earlier. These cover the other two, and the thing worth
testing is not that the route exists — it is that each surface is given the LEAST
privilege that lets it work:

* the customer display holds ``orders.read`` and nothing else. It shows one snapshot
  and hangs where anyone can reach it, so it must not be replayable into a till;
* the course station fires and holds courses, which are order actions, so it gets
  what a till gets and no more;
* neither token is ever written into a URL, and the response carrying it is
  uncacheable.

The ``?token=`` fallback is now RETIRED. It survived for a while on purpose —
dropping it breaks every bookmarked screen in an estate, which is an operator's call
and not a side effect of adding a safer route — and that call has been made. Each
page now reads the injected credential and nothing else.
"""
from odoo.tests import tagged

from .common import MezzeHttpCase
from ..domain import authz


@tagged('post_install', '-at_install', 'mezze_surface_auth')
class TestSurfaceCredentials(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.env.flush_all()

    def _get(self, path):
        self.authenticate('admin', 'admin')
        return self.url_open(path)

    def _terminal(self, identifier):
        return self.env['mezze.terminal'].sudo().with_context(
            active_test=False).search([('identifier', '=', identifier)], limit=1)

    # ── the display holds almost nothing ─────────────────────────────────
    def test_01_a_display_role_can_only_read(self):
        # THE point of the role. A screen facing the public must not be
        # replayable into one that sells.
        caps = authz.ROLE_CAPS['display']
        self.assertEqual(set(caps), {authz.ORDERS_READ})
        for forbidden in (authz.ORDERS_PAY, authz.ORDERS_WRITE, authz.ORDERS_REFUND,
                          authz.KITCHEN_UPDATE, authz.HARDWARE_DRAWER):
            self.assertNotIn(forbidden, caps,
                             '%s is reachable from a customer display' % forbidden)

    def test_02_the_display_route_mints_that_role(self):
        r = self._get('/mezze/cfd')
        self.assertEqual(r.status_code, 200, r.text[:200])
        term = self._terminal('cfd-%s' % self.pos_config.id)
        self.assertTrue(term, 'no terminal was minted for the display')
        self.assertEqual(term.role, 'display',
                         'the customer display was given a %s principal' % term.role)
        self.assertEqual(term.branch_id, self.pos_config)

    def test_03_the_course_station_gets_till_privileges(self):
        # Firing a course is an order action; this one genuinely needs them.
        r = self._get('/mezze/courses')
        self.assertEqual(r.status_code, 200, r.text[:200])
        term = self._terminal('courses-%s' % self.pos_config.id)
        self.assertTrue(term, 'no terminal was minted for the course station')
        self.assertEqual(term.role, 'terminal')

    def test_04_the_lane_board_is_unchanged(self):
        # Guard against fixing two surfaces by breaking the one already done.
        r = self._get('/mezze/drivethru')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._terminal('drivethru-%s' % self.pos_config.id).role,
                         'terminal')

    # ── the credential is in the page, not the URL ───────────────────────
    def test_10_the_token_is_injected_not_linked(self):
        r = self._get('/mezze/cfd')
        self.assertIn('id="mezze-boot"', r.text,
                      'the display was served without a boot payload')
        self.assertNotIn('?token=', r.text,
                         'a token was written into a URL on the page')

    def test_11_the_page_prefers_the_injected_token(self):
        """Reading the query string FIRST would make the safe route pointless.

        Asserted on the ORDER, not on a substring: an earlier version of this test
        looked for ``BOOT.token||`` and passed with the precedence reversed, because
        ``Q.get('token')||BOOT.token||''`` still contains it.
        """
        import re
        for page in ('cfd.html', 'courses.html'):
            src = self._page_source(page)
            m = re.search(r'var TOKEN\s*=\s*([^,;]+)', src)
            self.assertTrue(m, '%s does not assign TOKEN at all' % page)
            expr = m.group(1)
            boot_at = expr.find('BOOT.token')
            url_at = expr.find("Q.get('token')")
            self.assertNotEqual(boot_at, -1,
                                '%s never reads the injected credential' % page)
            self.assertTrue(url_at == -1 or boot_at < url_at,
                            '%s reads the URL before the injected token: %s'
                            % (page, expr))

    def test_12_a_response_carrying_a_token_is_never_cached(self):
        for path in ('/mezze/cfd', '/mezze/courses'):
            r = self._get(path)
            cache = (r.headers.get('Cache-Control') or '').lower()
            self.assertIn('no-store', cache,
                          '%s may be cached with a live token in it' % path)

    def test_13_each_surface_gets_its_own_terminal(self):
        # One shared principal would mean revoking the display revokes the lane.
        for path in ('/mezze/cfd', '/mezze/courses', '/mezze/drivethru'):
            self._get(path)
        idents = {'cfd', 'courses', 'drivethru'}
        found = {self._terminal('%s-%s' % (k, self.pos_config.id)) for k in idents}
        self.assertEqual(len(found), 3, 'the surfaces share a principal')

    def test_14_reopening_a_screen_rotates_its_token(self):
        # A credential handed out twice is one that outlives the device it was for.
        self._get('/mezze/cfd')
        first = self._terminal('cfd-%s' % self.pos_config.id).token_fingerprint
        self._get('/mezze/cfd')
        second = self._terminal('cfd-%s' % self.pos_config.id).token_fingerprint
        self.assertTrue(first and second)
        self.assertNotEqual(first, second, 'the display token was reused')

    # ── nothing was taken away ───────────────────────────────────────────
    def test_20_no_page_reads_a_credential_from_the_url(self):
        """The fallback is retired — by decision, not by accident.

        It was kept for a while on purpose: dropping it breaks every bookmarked
        screen in an estate, which is an operator's call. That call has been made,
        so the rule is enforced here instead of the exception being protected.
        """
        for page in ('cfd.html', 'courses.html', 'drivethru.html'):
            page_src = self._page_source(page)
            self.assertNotIn(
                "Q.get('token')", page_src,
                '%s still accepts a bearer token from the query string' % page)
            self.assertIn('BOOT.token', page_src,
                          '%s no longer reads the injected credential' % page)

    def _page_source(self, name):
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, '..', 'static', name), encoding='utf-8') as fh:
            return fh.read()


@tagged('post_install', '-at_install', 'mezze_surface_auth')
class TestSurfaceGoLive(MezzeHttpCase):
    """The open decision, moved into the operator's own go-live report.

    Repeating a security caveat in a handover note puts it where nobody looks
    twice. The go-live check is the place an operator actually reads before
    switching a branch on, so that is where this belongs.

    The check reports from REAL state — whether each screen has ever been opened at
    its own authenticated route — rather than from a flag. A check whose PASS is a
    setting no code reads does not verify anything; it certifies a belief.
    """
    fixture_profile = 'POS'

    def _report(self):
        return {c['name']: c for c in
                self.env['mezze.golive.validator'].sudo().run()['checks']}

    def _open(self, path):
        self.authenticate('admin', 'admin')
        return self.url_open(path)

    def test_30_a_branch_that_never_opened_them_is_warned(self):
        self.env['mezze.terminal'].sudo().with_context(active_test=False).search(
            ['|', '|', ('identifier', '=like', 'cfd-%'),
             ('identifier', '=like', 'courses-%'),
             ('identifier', '=like', 'drivethru-%')]).unlink()
        check = self._report().get('surface_routes_in_use')
        self.assertTrue(check, 'the check is missing from the report')
        self.assertEqual(check['status'], 'WARNING')
        for name in ('customer display', 'course station', 'lane board'):
            self.assertIn(name, check['detail'])

    def test_31_it_names_the_route_to_use_instead(self):
        # A warning a reader cannot act on is a warning they learn to skip.
        detail = self._report()['surface_routes_in_use']['detail']
        for route in ('/mezze/cfd', '/mezze/courses', '/mezze/drivethru'):
            self.assertIn(route, detail)

    def test_32_opening_all_three_clears_it(self):
        for path in ('/mezze/cfd', '/mezze/courses', '/mezze/drivethru'):
            self.assertEqual(self._open(path).status_code, 200)
        self.env.invalidate_all()
        self.assertEqual(self._report()['surface_routes_in_use']['status'], 'PASS')

    def test_33_one_screen_left_behind_still_warns(self):
        # The half-migrated estate is the state this exists to catch.
        self.env['mezze.terminal'].sudo().with_context(active_test=False).search(
            ['|', '|', ('identifier', '=like', 'cfd-%'),
             ('identifier', '=like', 'courses-%'),
             ('identifier', '=like', 'drivethru-%')]).unlink()
        self._open('/mezze/courses')
        self._open('/mezze/drivethru')
        self.env.invalidate_all()
        check = self._report()['surface_routes_in_use']
        self.assertEqual(check['status'], 'WARNING')
        self.assertIn('customer display', check['detail'])
        self.assertNotIn('course station', check['detail'])
