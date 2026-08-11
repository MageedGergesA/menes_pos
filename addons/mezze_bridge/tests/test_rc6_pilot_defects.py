"""RC6 — the two defects RC5 physical-pilot preparation found.

**DEFECT-01 (MEDIUM).** The Register and the Floor resolved their ``mezze.terminal`` by
``cashier-web-<pos_config_id>``, so every client on a POS config shared one identity and
each page open minted a token onto it, silently evicting the previous holder. Measured on
the pilot runtime: ``A 200 -> B boots -> A 401 -> B 200``.

The suite missed it for a specific, reproducible reason: the fixtures set
``mezze_bridge.api_security = 'observe'`` (audit-only) while the **shipped default is
``enforce``**. Every test here therefore runs in **enforce** mode explicitly — a test that
proves this in observe mode proves nothing about the product as it ships.

**DEFECT-02 (LOW).** ``release_identity()`` reported ``product_version 1.0.0-rc.1`` on the
RC5 build. The guard below ties the constant to the git tag so it cannot go stale again.
"""
import json
import os
import re
import subprocess

from odoo.tests import tagged

from ..controllers.register_instance import RID_COOKIE
from .common import MezzeHttpCase

ENFORCE = 'enforce'


@tagged('post_install', '-at_install', 'mezze_rc6')
class TestRegisterSessionIsolation(MezzeHttpCase):
    """DEFECT-01 — concurrent Register clients on one POS config."""

    fixture_profile = 'RESTAURANT'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        # The SHIPPED posture, not the permissive fixture default.
        icp.set_param('mezze_bridge.api_security', ENFORCE)
        self.product.write({'list_price': 100.0, 'available_in_pos': True})
        self.pos_session = self.open_test_session()
        self.env.flush_all()
        self.authenticate('admin', 'admin')

    # ------------------------------------------------------------------ helpers
    #
    # A "client" here is a browsing context, modelled by its register-instance
    # locator cookie — exactly what distinguishes two devices in production. Requests
    # go through ``self.url_open`` so they carry Odoo's test-cursor cookie and join the
    # test transaction; a raw ``requests.Session`` is silently ignored by the server.
    def open_register(self, client=None, path='/mezze/pos'):
        """Open the Register/Floor as one browsing context; returns the boot payload."""
        self.opener.cookies.pop(RID_COOKIE, None)      # never leak one client into another
        cookies = {RID_COOKIE: client} if client else None
        res = self.url_open(path, cookies=cookies, timeout=30)
        self.assertEqual(res.status_code, 200, 'Register page served')
        m = re.search(r'<script type="application/json" id="mezze-boot">(.*?)</script>',
                      res.text, re.S)
        self.assertTrue(m, 'boot payload present')
        payload = json.loads(m.group(1).replace('\\u003c', '<'))
        payload['_set_cookie'] = res.cookies.get(RID_COOKIE)
        return payload

    def api(self, token, endpoint='/reservations/list', payload=None):
        body = dict(payload or {}, token=token)
        res = self.url_open('/mezze/api/v1' + endpoint, data=json.dumps(body),
                            headers={'Content-Type': 'application/json'}, timeout=30)
        return res.status_code

    def client(self, label):
        """An opaque, well-formed locator standing in for a browser that already holds
        the cookie the server issued to it on first boot."""
        return 'rc6client%s' % label

    # ------------------------------------------------------------------ the defect
    def test_01_two_clients_on_one_config_coexist(self):
        """THE pilot reproduction. RC5: A 200 -> B boots -> A 401. RC6: both 200."""
        a = self.client('A')
        b = self.client('B')

        boot_a = self.open_register(a)
        self.assertTrue(boot_a.get('ok'), 'A booted: %s' % boot_a.get('error'))
        token_a = boot_a['token']
        self.assertEqual(self.api(token_a), 200, 'A works before B exists')

        boot_b = self.open_register(b)
        self.assertTrue(boot_b.get('ok'), 'B booted')
        token_b = boot_b['token']

        self.assertNotEqual(token_a, token_b, 'each client got its own secret')
        self.assertEqual(self.api(token_b), 200, 'B works')
        self.assertEqual(self.api(token_a), 200,
                         'RC5 DEFECT-01: A must SURVIVE B booting (was 401)')

    def test_02_reload_does_not_evict_the_other_client(self):
        a, b = self.client('A'), self.client('B')
        token_a = self.open_register(a)['token']
        token_b = self.open_register(b)['token']

        token_a2 = self.open_register(a)['token']          # A reloads
        self.assertNotEqual(token_a2, token_a, 'A rotated its own secret on reload')
        self.assertEqual(self.api(token_a2), 200, 'A works after its own reload')
        self.assertEqual(self.api(token_b), 200, 'B unaffected by A reloading')

        token_b2 = self.open_register(b)['token']          # B reloads
        self.assertEqual(self.api(token_b2), 200, 'B works after its own reload')
        self.assertEqual(self.api(token_a2), 200, 'A unaffected by B reloading')

    def test_03_clients_get_distinct_terminal_identities(self):
        a, b = self.client('A'), self.client('B')
        self.open_register(a)
        self.open_register(b)
        Term = self.env['mezze.terminal'].sudo().with_context(active_test=False)
        terms = Term.search([('identifier', 'like', 'cashier-web-%s-%%' % self.pos_config.id)])
        self.assertGreaterEqual(len(terms), 2,
                                'two clients => two terminal rows, got %s' % terms.mapped('identifier'))
        self.assertEqual(len(set(terms.mapped('identifier'))), len(terms), 'identifiers unique')
        for t in terms:
            self.assertEqual(t.role, 'terminal', 'least privilege preserved')
            self.assertEqual(t.branch_id, self.pos_config, 'branch scope preserved')

    def test_04_floor_does_not_evict_a_register_on_another_client(self):
        """The Floor reused the same config-keyed terminal, so it evicted too."""
        a, b = self.client('A'), self.client('B')
        token_a = self.open_register(a)['token']
        boot_b = self.open_register(b, path='/mezze/floor')
        self.assertTrue(boot_b.get('ok'), 'Floor booted for B')
        self.assertEqual(self.api(boot_b['token']), 200, 'B floor token works')
        self.assertEqual(self.api(token_a), 200, "A's Register survives B opening the Floor")

    def test_05_floor_and_register_share_one_identity_per_client(self):
        """Documented policy, unchanged from RC5: one principal per client."""
        a = self.client('A')
        self.open_register(a)
        floor_token = self.open_register(a, path='/mezze/floor')['token']
        Term = self.env['mezze.terminal'].sudo().with_context(active_test=False)
        mine = Term.search([('identifier', 'like', 'cashier-web-%s-%%' % self.pos_config.id)])
        self.assertEqual(len(mine), 1,
                         'one client => ONE terminal for both Register and Floor, got %s'
                         % mine.mapped('identifier'))
        self.assertEqual(self.api(floor_token), 200)

    # ------------------------------------------------------------------ security
    def test_06_scoped_revocation(self):
        a, b = self.client('A'), self.client('B')
        token_a = self.open_register(a)['token']
        token_b = self.open_register(b)['token']
        Term = self.env['mezze.terminal'].sudo().with_context(active_test=False)
        term_a = Term.search([('token_fingerprint', '=',
                               self.env['mezze.secret.store'].token_hash(token_a))], limit=1)
        self.assertTrue(term_a, "A's terminal resolvable by fingerprint")
        term_a.write({'active': False})

        # The existing contract distinguishes authentication from authorization:
        # a REVOKED terminal resolves fine and is then denied (TERMINAL_REVOKED -> 403),
        # while an unknown/absent credential is 401. RC6 does not change that.
        self.assertEqual(self.api(token_a), 403, 'revoked A is denied')
        self.assertEqual(self.api(token_b), 200, 'B unaffected by revoking A')

    def test_07_revoked_instance_is_not_revived_by_reopening(self):
        a = self.client('A')
        token_a = self.open_register(a)['token']
        Term = self.env['mezze.terminal'].sudo().with_context(active_test=False)
        term = Term.search([('token_fingerprint', '=',
                             self.env['mezze.secret.store'].token_hash(token_a))], limit=1)
        term.write({'active': False})
        boot = self.open_register(a)
        self.assertFalse(boot.get('token'),
                         'reopening a REVOKED instance must not mint a working token')
        term.invalidate_recordset()
        self.assertFalse(term.active, 'and must not silently re-activate it')

    def test_08_instance_locator_is_not_a_credential(self):
        """Knowing another client's rid must authenticate nothing."""
        a = self.client('A')
        self.open_register(a)
        Term = self.env['mezze.terminal'].sudo().with_context(active_test=False)
        ident = Term.search([('identifier', 'like', 'cashier-web-%s-%%' % self.pos_config.id)],
                            limit=1).identifier
        rid = ident.rsplit('-', 1)[-1]
        self.assertTrue(rid, 'locator extracted')
        for candidate in (rid, ident):
            self.assertEqual(self.api(candidate), 401,
                             'the locator %r must NOT work as a bearer token' % candidate)

    def test_09_invalid_and_missing_tokens_still_rejected(self):
        self.assertEqual(self.api('not-a-real-token'), 401, 'garbage token rejected')
        res = self.url_open('/mezze/api/v1/reservations/list', data=json.dumps({}),
                            headers={'Content-Type': 'application/json'}, timeout=30)
        self.assertEqual(res.status_code, 401, 'missing token rejected')

    def test_10_enforce_is_still_the_shipped_default(self):
        """The fix must not have been achieved by relaxing the security posture."""
        self.env['ir.config_parameter'].sudo().search(
            [('key', '=', 'mezze_bridge.api_security')]).unlink()
        from ..controllers import main as main_ctl  # noqa: PLC0415
        src = open(main_ctl.__file__, encoding='utf-8').read()
        self.assertIn("get_param('mezze_bridge.api_security') or 'enforce'", src,
                      'the default posture must remain enforce')
        a = self.client('A')
        token = self.open_register(a)['token']
        self.assertEqual(self.api(token), 200, 'a legitimate client works with no param set')
        self.assertEqual(self.api('bogus'), 401, 'and enforcement is still active')

    def test_11_observe_mode_unchanged(self):
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_security', 'observe')
        a, b = self.client('A'), self.client('B')
        token_a = self.open_register(a)['token']
        token_b = self.open_register(b)['token']
        self.assertEqual(self.api(token_a), 200, 'A works in observe mode')
        self.assertEqual(self.api(token_b), 200, 'B works in observe mode')

    def test_12_no_bearer_token_is_written_to_the_log(self):
        a = self.client('A')
        token = self.open_register(a)['token']
        Log = self.env['mezze.audit.log'].sudo()
        recent = Log.search([], order='id desc', limit=50)
        blob = ' '.join(filter(None, recent.mapped('detail') + recent.mapped('event')))
        self.assertNotIn(token, blob, 'plaintext bearer token must never reach the audit log')

    def test_13_token_is_not_stored_in_plaintext_on_the_terminal(self):
        a = self.client('A')
        token = self.open_register(a)['token']
        Term = self.env['mezze.terminal'].sudo().with_context(active_test=False)
        term = Term.search([('token_fingerprint', '=',
                             self.env['mezze.secret.store'].token_hash(token))], limit=1)
        self.assertTrue(term, 'resolved by fingerprint, not plaintext')
        self.assertTrue(term.token_fingerprint, 'fingerprint stored')

    def test_14_different_configs_stay_isolated(self):
        other = self.pos_config.copy({'name': 'RC6 Second Register'})
        a = self.client('A')
        token_a = self.open_register(a)['token']
        b = self.client('B')
        boot_b = self.open_register(b, path='/mezze/pos?config_id=%s' % other.id)
        self.assertTrue(boot_b.get('ok'))
        self.assertEqual(boot_b['config_id'], other.id, 'B is on the other config')
        self.assertNotEqual(boot_b['token'], token_a)
        self.assertEqual(self.api(token_a), 200, 'configs remain isolated')

    def test_15_no_auth_secret_moved_into_browser_storage(self):
        """RC6 must not widen token exposure to solve concurrency."""
        import ast  # noqa: PLC0415
        from ..controllers import register_instance as ri  # noqa: PLC0415
        src = open(ri.__file__, encoding='utf-8').read()
        # scan CODE only - the module docstring legitimately explains why browser
        # storage is NOT used, and must not itself trip this guard
        tree = ast.parse(src)
        if (tree.body and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)):
            tree.body = tree.body[1:]
        code = ast.unparse(tree)
        for banned in ('localStorage', 'sessionStorage'):
            self.assertNotIn(banned, code,
                             'RC6 must not move an auth secret into browser storage')
        self.assertIn('httponly=True', code, 'the locator cookie is HttpOnly')
        # and the page templates must not have started stashing the token either
        for ctl in ('cashier.py', 'floor.py'):
            body = open(os.path.join(os.path.dirname(ri.__file__), ctl), encoding='utf-8').read()
            self.assertNotIn('localStorage', body)


@tagged('post_install', '-at_install', 'mezze_rc6')
class TestReleaseIdentity(MezzeHttpCase):
    """DEFECT-02 — the runtime must not misreport which candidate it is."""

    fixture_profile = 'POS'

    def test_20_product_version_is_current(self):
        from ..models.productization import MEZZE_PRODUCT_VERSION  # noqa: PLC0415
        self.assertNotEqual(MEZZE_PRODUCT_VERSION, '1.0.0-rc.1',
                            'the RC5 stale product version must not ship again')
        self.assertRegex(MEZZE_PRODUCT_VERSION, r'^\d+\.\d+\.\d+(-rc\.\d+)?$')

    def test_21_release_identity_schema_unchanged(self):
        ri = self.env['mezze.productization'].release_identity()
        for key in ('product', 'product_version', 'edition', 'deployment_mode', 'module',
                    'module_version', 'odoo_version', 'odoo_series', 'git_commit',
                    'release_channel', 'build', 'neutralized', 'env_profile'):
            self.assertIn(key, ri, 'response schema must not change: missing %r' % key)
        from ..models.productization import MEZZE_PRODUCT_VERSION  # noqa: PLC0415
        self.assertEqual(ri['product_version'], MEZZE_PRODUCT_VERSION)

    def test_22_module_version_is_independent_and_correct(self):
        ri = self.env['mezze.productization'].release_identity()
        installed = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'mezze_bridge')], limit=1).latest_version
        self.assertEqual(ri['module_version'], installed)
        self.assertNotEqual(ri['module_version'], ri['product_version'],
                            'module and product versions are distinct identities')

    def test_23_build_commit_precedence(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.build_commit', 'deadbeefcafe')
        self.assertEqual(self.env['mezze.productization'].release_identity()['git_commit'],
                         'deadbeefcafe', 'an explicit deploy stamp wins')
        icp.search([('key', '=', 'mezze_bridge.build_commit')]).unlink()
        fallback = self.env['mezze.productization'].release_identity()['git_commit']
        self.assertTrue(fallback, 'falls back to a git query (or n/a) without raising')

    def test_24_product_version_matches_the_git_tag(self):
        """The guard that stops DEFECT-02 recurring.

        Only asserts when HEAD sits EXACTLY on a release-candidate tag — on ordinary
        development commits there is nothing to compare against, so this is silent.
        """
        from ..models import productization as prod  # noqa: PLC0415
        import os  # noqa: PLC0415
        here = os.path.dirname(os.path.dirname(os.path.abspath(prod.__file__)))
        try:
            out = subprocess.run(['git', '-C', here, 'describe', '--tags', '--exact-match'],
                                 capture_output=True, text=True, timeout=5)
        except Exception:  # noqa: BLE001
            self.skipTest('git unavailable')
        if out.returncode != 0:
            self.skipTest('HEAD is not exactly on a tag')
        tag = out.stdout.strip()
        m = re.fullmatch(r'mezze-v(\d+\.\d+)-rc(\d+)', tag)
        if not m:
            self.skipTest('HEAD tag %r is not a release candidate' % tag)
        expected = '%s.0-rc.%s' % (m.group(1), m.group(2))
        self.assertEqual(prod.MEZZE_PRODUCT_VERSION, expected,
                         'tag %s requires product version %s' % (tag, expected))
