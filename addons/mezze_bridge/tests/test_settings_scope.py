"""A theme chosen once should look the same on every screen in the branch.

Settings were stored per PRINCIPAL: `user_ref` for a machine principal is
``terminal:<identifier>``, so a theme picked at the Register was saved against the
Register. The Kitchen Display is a different terminal, so it resolved to catalogue
defaults and kept its own look — the Register went Coastal and the kitchen stayed
Classic. That is right for a personal preference and wrong for the branch's
appearance, which every screen shares.

These tests cover the branch scope that closes it, and the authorization that keeps
it from being abused: re-theming every screen in a branch is an administrative act,
not something one till does by itself.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestSettingsScope(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'sc-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, token='sc-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def _ctx(self, user_ref):
        """A principal context standing in for one device in this branch."""
        return {'company_id': self.company.id, 'branch_id': self.pos_config.id,
                'role': 'terminal', 'user_ref': user_ref}

    def test_a_device_save_does_not_reach_another_device(self):
        # This is the reported behaviour, kept as the baseline: it is correct for a
        # personal preference and is exactly why the branch scope had to exist.
        S = self.env['mezze.settings']
        S.save_user(self._ctx('terminal:register-1'), {'app_theme': 'coastal'})
        register = S.resolve(self._ctx('terminal:register-1'))
        kitchen = S.resolve(self._ctx('terminal:kitchen-display-1'))
        self.assertEqual(register['effective']['app_theme'], 'coastal')
        self.assertEqual(kitchen['effective']['app_theme'], 'classic',
                         'a device preference stays on that device')

    def test_a_branch_save_reaches_every_device(self):
        S = self.env['mezze.settings']
        S.save_branch(self._ctx('terminal:register-1'), {'app_theme': 'forest'})
        for device in ('terminal:register-1', 'terminal:kitchen-display-1',
                       'terminal:floor-1', 'terminal:never-seen-before'):
            r = S.resolve(self._ctx(device))
            self.assertEqual(r['effective']['app_theme'], 'forest',
                             '%s follows the branch theme' % device)
            self.assertEqual(r['provenance']['app_theme']['scope'], 'branch')

    def test_a_branch_save_clears_the_device_override_it_replaces(self):
        # Otherwise the till that set the branch theme would be the one screen not
        # showing it — its own older device value would still win.
        S = self.env['mezze.settings']
        ctx = self._ctx('terminal:register-1')
        S.save_user(ctx, {'app_theme': 'coastal'})
        S.save_branch(ctx, {'app_theme': 'forest'})
        self.assertEqual(S.resolve(ctx)['effective']['app_theme'], 'forest')

    def test_a_device_may_still_differ_after_a_branch_theme(self):
        # The hierarchy is not abolished: a device can still opt out afterwards.
        S = self.env['mezze.settings']
        S.save_branch(self._ctx('terminal:register-1'), {'app_theme': 'forest'})
        S.save_user(self._ctx('terminal:kitchen-display-1'), {'app_theme': 'highcontrast'})
        self.assertEqual(
            S.resolve(self._ctx('terminal:kitchen-display-1'))['effective']['app_theme'],
            'highcontrast')
        self.assertEqual(
            S.resolve(self._ctx('terminal:floor-1'))['effective']['app_theme'], 'forest')

    def test_a_plain_terminal_cannot_retheme_the_branch_over_http(self):
        # A till holds orders.read (enough for its own preferences) but not
        # admin.settings, so it cannot change what every screen in the branch shows.
        term = self.env['mezze.terminal'].create(
            {'name': 'Till', 'identifier': 'SC-T', 'token': 'sc-term-tok',
             'branch_id': self.pos_config.id, 'role': 'terminal', 'active': True})
        self.assertTrue(term)
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_security', 'enforce')
        self.env.flush_all()
        r = self.url_open('/mezze/api/v1/settings/branch',
                          data=json.dumps({'values': {'app_theme': 'coastal'},
                                           'token': 'sc-term-tok'}),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        self.assertIn(r.status_code, (401, 403), r.text[:200])
        self.assertNotEqual(
            self.env['mezze.settings'].resolve(self._ctx('terminal:x'))['effective']['app_theme'],
            'coastal', 'nothing was written')

    def test_a_principal_with_no_branch_is_told_so(self):
        # The shared admin token HAS the capability but is not branch-scoped, so
        # there is no branch for the value to belong to. That is a 400 with a reason,
        # not a traceback.
        code, res = self._post('/settings/branch', {'values': {'app_theme': 'coastal'}})
        self.assertEqual(code, 400, res)
        self.assertEqual(res.get('error'), 'no_branch')

    def test_an_unknown_scope_is_refused_not_downgraded(self):
        # Quietly saving to a narrower scope than asked would be its own kind of lie.
        code, res = self._post('/settings/save',
                               {'values': {'app_theme': 'coastal'}, 'scope': 'planet'})
        self.assertEqual(code, 400)
        self.assertEqual(res.get('error'), 'bad_scope')

    def test_asking_settings_save_for_a_branch_save_points_at_the_right_route(self):
        # The branch write has its own capability, so it has its own endpoint; a
        # caller using the old shape is told where to go, not silently narrowed.
        code, res = self._post('/settings/save',
                               {'values': {'app_theme': 'coastal'}, 'scope': 'branch'})
        self.assertEqual(code, 400)
        self.assertEqual(res.get('error'), 'use_settings_branch')

    def test_a_branch_save_still_refuses_a_setting_that_does_not_work(self):
        # The branch scope is a different destination, not a way around validation.
        S = self.env['mezze.settings']
        out = S.save_branch(self._ctx('terminal:register-1'),
                            {'app_theme': 'forest', 'not_a_real_setting': 'x'})
        self.assertIn('app_theme', out['saved'])
        self.assertIn('not_a_real_setting', out['rejected'])
