"""R-1 — the settings catalog exists because the MODULE INSTALLED it.

This test deliberately uses a plain ``TransactionCase`` (NOT ``MezzeFixtureMixin``) and
does NOT call ``seed_catalog()`` / any fixture catalog factory. It therefore proves the
101-setting authoritative catalog is materialised by module installation
(``data/settings_catalog_bootstrap.xml``), not by test provisioning. If R-1 regresses,
this fails while the hermetic fixtures would still (wrongly) mask it.

Counts are checked BOTH against the exact documented split (101 / 18 / 76 / 7) AND
against the authoritative source (``domain/settings_catalog.py``) so a future catalog
change is caught rather than silently drifting.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.mezze_bridge.domain import settings_catalog as SC


@tagged('post_install', '-at_install', 'mezze_invariants')
class TestSettingsCatalogInstalled(TransactionCase):

    def test_catalog_installed_by_module_not_fixture(self):
        Def = self.env['mezze.setting.def'].sudo()
        rows = Def.search([])

        # exact documented split
        self.assertEqual(len(rows), 101, 'module install must materialise 101 setting defs')
        by_status = {}
        for r in rows:
            by_status[r.status] = by_status.get(r.status, 0) + 1
        self.assertEqual(by_status.get('working', 0), 18, 'Working count')
        self.assertEqual(by_status.get('disabled', 0), 76, 'Disabled count')
        self.assertEqual(by_status.get('hidden', 0), 7, 'Hidden count')

        # consistent with the single source of truth
        self.assertEqual(len(rows), len(SC.CATALOG_101), 'DB catalog matches source count')
        src_status = {t[0]: t[5] for t in SC.CATALOG_101}
        self.assertEqual(set(rows.mapped('key')), set(src_status), 'DB keys match source keys')

        # key uniqueness
        keys = rows.mapped('key')
        self.assertEqual(len(keys), len(set(keys)), 'setting keys are unique')

    def test_representative_keys_and_statuses(self):
        Def = self.env['mezze.setting.def'].sudo()
        src_status = {t[0]: t[5] for t in SC.CATALOG_101}
        for key in ('app_mode', 'app_theme', 'app_density', 'ws_panel_side', 'gr_cols',
                    'cd_img', 'ac_dir', 'pf_virtual', 'ad_debug'):
            rec = Def.search([('key', '=', key)], limit=1)
            self.assertTrue(rec, 'representative key %r present after install' % key)
            self.assertEqual(rec.status, src_status[key],
                             'status of %r matches the authoritative catalog' % key)


@tagged('post_install', '-at_install', 'mezze_invariants')
class TestBootstrapIdempotent(TransactionCase):
    """Calling the install bootstrap repeatedly is a no-op on final state (§14)."""

    def test_bootstrap_twice_is_idempotent(self):
        Def = self.env['mezze.setting.def'].sudo()
        before = Def.search_count([])
        # a scoped override to prove bootstrap never destroys user data
        self.env['mezze.config.value'].sudo().create({
            'setting_key': 'app_mode', 'scope': 'user', 'scope_ref': 'user:R1',
            'value': 'dark', 'policy': 'free'})
        Def._bootstrap_authoritative_catalog()
        Def._bootstrap_authoritative_catalog()
        after = Def.search_count([])
        self.assertEqual(after, before, 'bootstrap must not add/remove definitions')
        self.assertEqual(after, 101, 'catalog remains exactly 101 after repeated bootstrap')
        keys = Def.search([]).mapped('key')
        self.assertEqual(len(keys), len(set(keys)), 'no duplicate keys after repeated bootstrap')
        # override survived
        self.assertTrue(self.env['mezze.config.value'].sudo().search_count(
            [('setting_key', '=', 'app_mode'), ('scope_ref', '=', 'user:R1')]),
            'bootstrap (prune=False) must not delete user overrides')

    def test_bootstrap_does_not_prune(self):
        """A non-catalog key is left untouched by the install bootstrap (upsert-only)."""
        Def = self.env['mezze.setting.def'].sudo()
        Def.create({'key': 'zz_third_party_probe', 'category': 'Ext', 'value_type': 'bool',
                    'default_value': 'false', 'status': 'working'})
        Def._bootstrap_authoritative_catalog()
        self.assertTrue(Def.search_count([('key', '=', 'zz_third_party_probe')]),
                        'bootstrap must not prune non-catalog keys (migrations own pruning)')
        # cleanup so other tests see a clean catalog
        Def.search([('key', '=', 'zz_third_party_probe')]).unlink()
