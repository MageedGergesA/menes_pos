"""D1 Design Platform — runtime proofs (tagged mezze_runtime / mezze_invariants).

Covers: catalog seeding; the effective cascade platform->...->device with
provenance; free/bounded/locked policy enforcement (a lower scope can NEVER bypass
a higher-scope lock); user override persistence + reset; template publish/assign;
the HTTP settings + admin API with scoped-admin gating; and structural guards that
the theme registry is contrast-validated and that arbitrary user colours are
impossible (no free-text colour setting exists).
"""
import json
import os

from odoo.tests import common, tagged


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestCascade(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.S = self.env['mezze.settings']
        self.CV = self.env['mezze.config.value'].sudo()
        self.env['mezze.setting.def'].seed_catalog()
        self.ctx = {'company_id': 7, 'brand_id': None, 'branch_id': 22,
                    'role': 'cashier', 'user_ref': 'cashier:5', 'device_ref': 'DEV-1'}

    def _clear(self):
        # full isolation: clear scoped values AND template assignments so a
        # published-template contribution (e.g. a role assignment committed by a
        # sibling HttpCase) can't leak into these default-cascade assertions.
        self.CV.search([]).unlink()
        self.env['mezze.config.assignment'].sudo().search([]).unlink()

    def test_catalog_seeded(self):
        keys = self.env['mezze.setting.def'].sudo().search([]).mapped('key')
        for k in ('app_mode', 'app_theme', 'app_dark_theme', 'app_accent', 'app_density', 'app_scale',
                  'gr_cols_mode', 'cd_img', 'ws_panel_side', 'ac_dir', 'ac_contrast'):
            self.assertIn(k, keys)

    def test_backend_seeds_101_with_status(self):
        Def = self.env['mezze.setting.def'].sudo()
        self.assertEqual(Def.search_count([]), 101)
        self.assertEqual(Def.search([('key', '=', 'app_mode')]).status, 'working')
        self.assertEqual(Def.search([('key', '=', 'ad_debug')]).status, 'hidden')
        dis = Def.search([('key', '=', 'app_dim')])
        self.assertEqual(dis.status, 'disabled')
        self.assertTrue(dis.reason)
        self.assertEqual(Def.search_count([('status', '=', 'working')]), 18)

    def test_disabled_setting_not_user_writable(self):
        self._clear()
        out = self.S.save_user(self.ctx, {'app_dim': 'true', 'app_density': 'compact'}, actor='u')
        self.assertIn('app_dim', out['rejected'])
        self.assertIn('app_density', out['saved'])

    def test_bounded_int_validated_server_side(self):
        d = self.env['mezze.setting.def'].sudo().search([('key', '=', 'gr_cols')])
        self.assertTrue(d.is_valid('4'))
        self.assertFalse(d.is_valid('99'))
        self.assertFalse(d.is_valid('1'))

    def test_defaults_when_no_values(self):
        self._clear()
        r = self.S.resolve(self.ctx)
        self.assertEqual(r['effective']['app_theme'], 'classic')
        self.assertEqual(r['effective']['app_accent'], 'terracotta')
        self.assertEqual(r['provenance']['app_theme']['scope'], 'default')

    def test_cascade_precedence(self):
        self._clear()
        # org sets density=compact; branch overrides to comfortable; user overrides to standard
        self.CV.create({'setting_key': 'app_density', 'scope': 'organization', 'scope_ref': '7', 'value': 'compact'})
        r = self.S.resolve(self.ctx)
        self.assertEqual(r['effective']['app_density'], 'compact')
        self.assertEqual(r['provenance']['app_density']['scope'], 'organization')
        self.CV.create({'setting_key': 'app_density', 'scope': 'branch', 'scope_ref': '22', 'value': 'comfortable'})
        r = self.S.resolve(self.ctx)
        self.assertEqual(r['effective']['app_density'], 'comfortable')
        self.assertEqual(r['provenance']['app_density']['scope'], 'branch')
        self.CV.create({'setting_key': 'app_density', 'scope': 'user', 'scope_ref': 'cashier:5', 'value': 'standard'})
        r = self.S.resolve(self.ctx)
        self.assertEqual(r['effective']['app_density'], 'standard')
        self.assertEqual(r['provenance']['app_density']['scope'], 'user')
        self.assertEqual(r['overrides']['app_density'], 'standard')

    def test_higher_lock_blocks_lower(self):
        self._clear()
        # organization LOCKS accent=blue; user tries to override -> must be refused
        self.CV.create({'setting_key': 'app_accent', 'scope': 'organization', 'scope_ref': '7',
                        'value': 'blue', 'policy': 'locked'})
        r = self.S.resolve(self.ctx)
        self.assertEqual(r['effective']['app_accent'], 'blue')
        self.assertEqual(r['locks'].get('app_accent'), 'locked')
        out = self.S.save_user(self.ctx, {'app_accent': 'teal'}, actor='cashier:5')
        self.assertIn('app_accent', out['rejected'])
        self.assertNotIn('app_accent', out['saved'])
        r2 = self.S.resolve(self.ctx)
        self.assertEqual(r2['effective']['app_accent'], 'blue')      # lock held

    def test_bounded_policy_marked(self):
        self._clear()
        self.CV.create({'setting_key': 'app_scale', 'scope': 'branch', 'scope_ref': '22',
                        'value': '110', 'policy': 'bounded', 'bounded_options': '100,110,120'})
        r = self.S.resolve(self.ctx)
        self.assertEqual(r['locks'].get('app_scale'), 'bounded')
        # bounded is NOT locked: a user override is still accepted
        out = self.S.save_user(self.ctx, {'app_scale': '120'}, actor='cashier:5')
        self.assertIn('app_scale', out['saved'])

    def test_invalid_value_rejected(self):
        self._clear()
        out = self.S.save_user(self.ctx, {'app_accent': 'chartreuse', 'app_theme': 'classic'}, actor='u')
        self.assertIn('app_accent', out['rejected'])         # not in registry
        self.assertIn('app_theme', out['saved'])

    def test_reset_user(self):
        self._clear()
        self.S.save_user(self.ctx, {'app_density': 'compact', 'app_accent': 'teal'}, actor='u')
        self.assertTrue(self.CV.search_count([('scope', '=', 'user'), ('scope_ref', '=', 'cashier:5')]))
        n = self.S.reset_user(self.ctx, section='all', actor='u')
        self.assertEqual(n['reset'], 2)
        self.assertFalse(self.CV.search_count([('scope', '=', 'user'), ('scope_ref', '=', 'cashier:5')]))

    def test_published_template_contributes_draft_does_not(self):
        self._clear()
        Tpl = self.env['mezze.config.template'].sudo()
        t = Tpl.create({'name': 'RoleT', 'kind': 'role', 'state': 'draft'})
        self.env['mezze.config.template.line'].sudo().create(
            {'template_id': t.id, 'setting_key': 'cd_img', 'value': 'text'})
        self.env['mezze.config.assignment'].sudo().create(
            {'template_id': t.id, 'scope': 'role', 'scope_ref': 'cashier', 'active': True})
        r = self.S.resolve(self.ctx)
        self.assertEqual(r['effective']['cd_img'], 'standard')   # draft: no effect
        t.action_publish()
        r = self.S.resolve(self.ctx)
        self.assertEqual(r['effective']['cd_img'], 'text')       # published: applies
        self.assertTrue(r['provenance']['cd_img']['source'].startswith('template:'))


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestSettingsHttp(common.HttpCase):

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.api_security', 'enforce')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        ICP.set_param('mezze_bridge.signing_mode.terminal', 'observe')
        self.shared = 'dp-shared'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        cfg = self.env['pos.config'].search([], limit=1)
        self.term = self.env['mezze.terminal'].create({
            'name': 'DP', 'identifier': 'DP-T', 'token': 'dp-term-tok',
            'branch_id': cfg.id, 'role': 'terminal', 'active': True})
        self.env['mezze.setting.def'].seed_catalog()
        # isolation: HttpCase requests commit, so clear any scoped values/locks left
        # by a sibling test so each method starts from the catalog defaults.
        self.env['mezze.config.value'].sudo().search([]).unlink()
        self.env['mezze.config.assignment'].sudo().search([]).unlink()
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def test_effective_requires_auth(self):
        st, b = self._post('/settings/effective', {'token': 'nope'})
        self.assertFalse(b.get('ok'))

    def test_effective_and_save_roundtrip(self):
        st, b = self._post('/settings/effective', {'token': 'dp-term-tok'})
        self.assertTrue(b.get('ok'))
        self.assertIn('effective', b)
        self.assertIn('provenance', b)
        self.assertEqual(b['effective']['app_accent'], 'terracotta')
        self.assertFalse(b.get('is_admin'))                       # bare terminal is not admin
        st, b = self._post('/settings/save', {'token': 'dp-term-tok', 'values': {'app_accent': 'teal', 'bogus': 'x'}})
        self.assertTrue(b.get('ok'))
        self.assertIn('app_accent', b['saved'])
        st, b = self._post('/settings/effective', {'token': 'dp-term-tok'})
        self.assertEqual(b['effective']['app_accent'], 'teal')        # persisted + resolved
        self.assertEqual(b['overrides'].get('app_accent'), 'teal')

    def test_admin_denied_for_terminal(self):
        st, b = self._post('/admin/templates', {'token': 'dp-term-tok'})
        self.assertEqual(b.get('error'), 'permission_denied')

    def test_admin_flow_for_shared_admin(self):
        # shared-admin (development) -> org_admin
        st, b = self._post('/admin/templates', {'token': self.shared})
        self.assertTrue(b.get('ok'))
        st, b = self._post('/admin/template/create', {'token': self.shared, 'name': 'HTTP Tpl', 'kind': 'role'})
        self.assertTrue(b.get('ok'))
        tid = b['id']
        st, b = self._post('/admin/template/publish', {'token': self.shared, 'template_id': tid})
        self.assertTrue(b.get('ok'))
        st, b = self._post('/admin/assign', {'token': self.shared, 'template_id': tid, 'scope': 'role', 'scope_ref': 'cashier'})
        self.assertTrue(b.get('ok'))
        st, b = self._post('/admin/lock', {'token': self.shared, 'setting_key': 'app_accent', 'scope': 'organization', 'value': 'blue', 'policy': 'locked'})
        self.assertTrue(b.get('ok'))
        # audit records the operations
        st, b = self._post('/admin/audit', {'token': self.shared})
        self.assertTrue(b.get('ok'))
        events = [e['event'] for e in b['entries']]
        self.assertTrue(any(e.startswith('config.') for e in events))

    def test_admin_lock_enforced_over_http(self):
        # platform locks accent (global); a terminal save must be rejected end-to-end
        self._post('/admin/lock', {'token': self.shared, 'setting_key': 'app_accent',
                                   'scope': 'platform', 'value': 'plum', 'policy': 'locked'})
        st, b = self._post('/settings/save', {'token': 'dp-term-tok', 'values': {'app_accent': 'olive'}})
        self.assertIn('app_accent', b.get('rejected', []))


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestAdminHumanPrincipals(common.HttpCase):
    """D1.1 §12 — Admin Console via authenticated HUMAN admin principals (no
    dependence on the shared-admin machine token)."""

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.api_security', 'enforce')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        ICP.set_param('mezze_bridge.signing_mode.terminal', 'observe')
        cfg = self.env['pos.config'].search([], limit=1)
        self.term = self.env['mezze.terminal'].create({
            'name': 'HP', 'identifier': 'HP-T', 'token': 'hp-term-tok',
            'branch_id': cfg.id, 'role': 'terminal', 'active': True})
        C = self.env['mezze.cashier'].sudo()
        self.mgr = C.create({'name': 'Mgr', 'code': 'HP-M', 'role': 'manager', 'active': True})
        self.adm = C.create({'name': 'Adm', 'code': 'HP-A', 'role': 'admin', 'active': True})
        self.aud = C.create({'name': 'Aud', 'code': 'HP-U', 'role': 'auditor', 'active': True})
        self.cash = C.create({'name': 'Cash', 'code': 'HP-C', 'role': 'cashier', 'active': True})
        self.env['mezze.config.value'].sudo().search([]).unlink()
        self.env['mezze.config.assignment'].sudo().search([]).unlink()
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def test_manager_human_opens_admin_no_shared_token(self):
        st, b = self._post('/admin/templates', {'token': 'hp-term-tok', 'cashier_id': self.mgr.id})
        self.assertTrue(b.get('ok'), b)
        self.assertEqual(b.get('_raw', ''), '')
        # store_manager may create + publish templates
        st, b = self._post('/admin/template/create', {'token': 'hp-term-tok', 'cashier_id': self.mgr.id, 'name': 'HumanTpl'})
        self.assertTrue(b.get('ok'))

    def test_bare_terminal_denied(self):
        st, b = self._post('/admin/templates', {'token': 'hp-term-tok'})
        self.assertEqual(b.get('error'), 'permission_denied')

    def test_plain_cashier_denied(self):
        st, b = self._post('/admin/templates', {'token': 'hp-term-tok', 'cashier_id': self.cash.id})
        self.assertEqual(b.get('error'), 'permission_denied')

    def test_auditor_read_only(self):
        st, b = self._post('/admin/audit', {'token': 'hp-term-tok', 'cashier_id': self.aud.id})
        self.assertTrue(b.get('ok'), b)                              # can READ
        st, b = self._post('/admin/template/create', {'token': 'hp-term-tok', 'cashier_id': self.aud.id, 'name': 'Nope'})
        self.assertEqual(b.get('error'), 'permission_denied')       # cannot WRITE

    def test_org_admin_locks_org_scope_and_enforced(self):
        st, b = self._post('/admin/lock', {'token': 'hp-term-tok', 'cashier_id': self.adm.id,
                                           'setting_key': 'app_accent', 'scope': 'organization',
                                           'value': 'blue', 'policy': 'locked'})
        self.assertTrue(b.get('ok'), b)
        # the same-company terminal user cannot override the org lock
        st, b = self._post('/settings/save', {'token': 'hp-term-tok', 'values': {'app_accent': 'teal'}})
        self.assertIn('app_accent', b.get('rejected', []))


@tagged('post_install', '-at_install', 'mezze_invariants')
class TestDesignStructural(common.TransactionCase):

    def _static(self, name):
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(os.path.dirname(here), 'static', name)

    def test_contrast_gate_passes(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('gen_design', self._static('gen_design.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.validate(), [], 'theme contrast gate must pass')
        self.assertEqual(len(mod.LIGHT) + len(mod.DARK), 12)
        self.assertEqual(len(mod.ACCENTS), 5)

    def test_css_has_all_themes_and_accents(self):
        css = open(self._static('mezze-design.css'), encoding='utf-8').read()
        for tid in ('classic', 'corporate', 'coastal', 'forest', 'coffeehouse', 'highcontrast',
                    'midnight', 'lounge', 'graphite', 'forestnight', 'slate'):
            self.assertIn('data-mz-theme="%s"' % tid, css)
        for a in ('terracotta', 'blue', 'teal', 'plum', 'olive'):
            self.assertIn('data-mz-accent="%s"' % a, css)

    def test_no_arbitrary_colour_setting(self):
        # arbitrary user colours are impossible: every colour-bearing setting is an
        # enum over the approved registry; there is no free-text/colour input type.
        from ..models.config_platform import CATALOG
        for key, cat, vt, dv, opts, eff in CATALOG:
            self.assertIn(vt, ('enum', 'bool', 'int', 'key'))
            if key in ('app_accent', 'app_theme', 'app_dark_theme'):
                self.assertEqual(vt, 'enum')
                self.assertTrue(opts)

    def test_customer_surfaces_adopt_token_system(self):
        # D1.1 §8 — every customer-facing surface loads the shared design system
        # (tokens + customer bridge) and a FOUC-guarded appearance bootstrap.
        for name in ('shop', 'drivethru', 'qr', 'cfd', 'courses', 'feedback'):
            html = open(self._static('%s.html' % name), encoding='utf-8').read()
            self.assertIn('mezze-design.css', html, name)
            self.assertIn('mezze-customer.css', html, name)
            self.assertIn('mezze-customer.js', html, name)
            self.assertIn("data-appearance", html, name)

    def test_101_catalog_and_status(self):
        # D3 — the authoritative catalog is exactly the 101 Settings.html ids, each
        # classified working|disabled|hidden (13 sections). Working settings map to a
        # real runtime consumer; disabled carry a reason; hidden are absent from the UI.
        from ..domain import settings_catalog as C
        self.assertEqual(len(C.CATALOG_101), 101)
        self.assertEqual(len({c[0] for c in C.CATALOG_101}), 101)
        self.assertEqual(len(set(c[1] for c in C.CATALOG_101)), 13)
        self.assertEqual(len(C.WORKING) + len(C.DISABLED) + len(C.HIDDEN), 101)
        self.assertGreaterEqual(len(C.WORKING), 16)
        for c in C.CATALOG_101:
            self.assertIn(c[5], ('working', 'disabled', 'hidden'))
            if c[5] != 'working':
                self.assertTrue(c[6], 'disabled/hidden setting %s needs a reason' % c[0])

    def test_unimplemented_settings_are_disabled_not_faked(self):
        # D3 — set() refuses non-working settings; disabled controls render read-only.
        js = open(self._static('mezze-design.js'), encoding='utf-8').read()
        self.assertIn("status !== 'working'", js)           # set() refuses non-working
        self.assertIn('aria-disabled', js)                  # disabled control
