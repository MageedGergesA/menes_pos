"""D3 — adopt the authoritative 101-setting catalog.

Re-seeds the catalog (now all 101 stable ids with working/disabled/hidden status)
and migrates existing scoped override rows from the pre-D3 engine keys onto their
stable ids (domain.settings_catalog.MIGRATION_MAP). Idempotent: an already-migrated
row is skipped, a value that no longer validates is dropped (its default resumes)
rather than discarded silently — the drop is recorded in the audit log. Never
touches financial/restaurant data.
"""
import json

from odoo import api, SUPERUSER_ID
from odoo.addons.mezze_bridge.domain import settings_catalog as SC


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['mezze.setting.def'].seed_catalog()
    CV = env['mezze.config.value'].sudo()
    Def = env['mezze.setting.def'].sudo()
    migrated, dropped = 0, 0
    for row in CV.search([]):
        old = row.setting_key
        if old in SC.STATUS:
            continue                                 # already a stable id
        new = SC.MIGRATION_MAP.get(old)
        if not new:
            continue
        # gridCols split: 'auto' -> gr_cols_mode=auto ; 'N' -> gr_cols_mode=fixed (+ gr_cols)
        if old == 'gridCols':
            val = 'auto' if str(row.value) == 'auto' else 'fixed'
            if str(row.value).isdigit():
                CV.search([('setting_key', '=', 'gr_cols'), ('scope', '=', row.scope),
                           ('scope_ref', '=', row.scope_ref)]) or CV.create(
                    {'setting_key': 'gr_cols', 'scope': row.scope, 'scope_ref': row.scope_ref,
                     'value': str(row.value), 'policy': row.policy})
            row.write({'setting_key': 'gr_cols_mode', 'value': val})
            migrated += 1
            continue
        d = Def.search([('key', '=', new)], limit=1)
        val = row.value
        # reduceMotion(bool)->ac_reduce(bool) fine; focusRing default true; others 1:1
        if d and not d.is_valid(val):
            row.unlink()
            dropped += 1
            continue
        # avoid a unique-constraint clash if a stable-id row already exists at this scope
        if CV.search_count([('setting_key', '=', new), ('scope', '=', row.scope),
                            ('scope_ref', '=', row.scope_ref)]):
            row.unlink()
        else:
            row.write({'setting_key': new})
        migrated += 1
    try:
        env['mezze.audit.log'].sudo().log(
            'config.migrate_101', severity='info',
            detail=json.dumps({'migrated': migrated, 'dropped': dropped, 'version': version}))
    except Exception:  # noqa: BLE001
        pass
