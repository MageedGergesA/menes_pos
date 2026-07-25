"""Mezze Design Platform — settings & admin HTTP API (D1).

Thin JSON endpoints over the ``mezze.settings`` resolver and the config platform
models. Authentication reuses the canonical ``_resolve_principal`` (per-terminal
token -> scoped principal; never trusts client-supplied company/branch). Admin
operations are gated by scoped admin roles derived from the resolved principal,
and every template / assignment / lock / reset write is audited.
"""
import json

from odoo import http
from odoo.http import request

from .main import MezzeBridgeController, API_PREFIX
from ..models.config_platform import SCOPE_ORDER


# scoped admin roles and the capabilities each grants over the config platform.
# D3 — the internal cap names below carry the Permission-Service concepts:
#   ui_template.read/manage  <- template.write   ui_assignment.manage <- assign.write
#   ui_policy.manage         <- lock.write        ui_audit.read/export <- audit.read
#   ui_admin.open            <- any admin_role     ui_rollback.execute  <- template.write
#   ui_theme.manage          <- lock.write (theme scope)
# Personal settings caps (settings.read_self/write_self) are held by every
# authenticated principal for its OWN settings (gated on ORDERS_READ + resolver
# scoping); settings.read_device/write_device require an admin_role (device policy).
ADMIN_CAPS = {
    'org_admin': {'template.write', 'assign.write', 'lock.write', 'audit.read', 'audit.export', 'permissions.read',
                  'ui_template.manage', 'ui_assignment.manage', 'ui_policy.manage', 'ui_theme.manage',
                  'ui_audit.read', 'ui_audit.export', 'ui_rollback.execute', 'settings.write_device'},
    'store_manager': {'template.write', 'assign.write', 'lock.write', 'audit.read', 'permissions.read',
                      'ui_template.manage', 'ui_assignment.manage', 'ui_policy.manage', 'ui_audit.read',
                      'settings.write_device'},
    'role_manager': {'template.write', 'assign.write', 'audit.read', 'permissions.read',
                     'ui_template.manage', 'ui_assignment.manage', 'ui_audit.read'},
    'auditor': {'audit.read', 'audit.export', 'permissions.read', 'ui_audit.read', 'ui_audit.export'},
}


class MezzeSettingsController(MezzeBridgeController):

    # ------------------------------------------------------------------ helpers
    def _principal_ctx(self, env):
        """Authenticate and build the resolver context. Returns (ctx, err_response)."""
        p = self._resolve_principal(env)
        if not p.get('ok'):
            return None, self._json({'ok': False, 'error': p.get('reason', 'authentication_failed')}, status=401)
        cashier = p.get('cashier')
        terminal = p.get('terminal')
        role = (cashier.role if cashier else None) or p.get('principal_type') or 'cashier'
        dev = terminal.identifier if terminal else None
        user_ref = ('cashier:%s' % cashier.id) if cashier else (('terminal:%s' % dev) if dev else p.get('principal'))
        ctx = {
            'company_id': p.get('company_id'),
            'brand_id': None,
            'branch_id': p.get('branch_id'),
            'role': role,
            'user_ref': user_ref,
            'device_ref': dev,
            'is_admin': p.get('is_admin'),
            'principal': p.get('principal'),
            'admin_role': self._admin_role(p, role),
        }
        return ctx, None

    def _admin_role(self, p, role):
        # Admin authority is derived from the SERVER-resolved principal only, and is
        # primarily a HUMAN principal (an attached cashier whose role is admin /
        # manager / auditor). A bare terminal/integration principal has NO config-admin
        # authority. The shared-admin token maps to org_admin ONLY as a development
        # fallback — in the production profile the shared token is disabled entirely,
        # so production admin access is 100% human.
        if role == 'admin':
            return 'org_admin'
        if role == 'manager':
            return 'store_manager'
        if role == 'supervisor':
            return 'role_manager'
        if role == 'auditor':
            return 'auditor'
        if p.get('is_admin'):
            return 'org_admin'          # dev-only shared-admin fallback
        return None

    def _can(self, ctx, cap):
        return cap in ADMIN_CAPS.get(ctx.get('admin_role') or '', set())

    # ------------------------------------------------------------------ settings
    @http.route(f'{API_PREFIX}/settings/effective', type='json2', auth='none',
                methods=['POST'], csrf=False)
    def settings_effective(self, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        res = env['mezze.settings'].resolve(ctx)
        res.update({
            'ok': True,
            'is_admin': bool(ctx.get('admin_role')),
            'admin_role': ctx.get('admin_role'),
            'admin_caps': sorted(ADMIN_CAPS.get(ctx.get('admin_role') or '', set())),
            'catalog': env['mezze.settings'].catalog(),
        })
        return self._json(res)

    @http.route(f'{API_PREFIX}/settings/save', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def settings_save(self, values=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        if not isinstance(values, dict):
            return self._json({'ok': False, 'error': 'bad_values'}, status=400)
        out = env['mezze.settings'].save_user(ctx, values, actor=ctx.get('user_ref'))
        return self._json({'ok': True, 'saved': out['saved'], 'rejected': out['rejected']})

    @http.route(f'{API_PREFIX}/settings/reset', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def settings_reset(self, section=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        out = env['mezze.settings'].reset_user(ctx, section=section, actor=ctx.get('user_ref'))
        return self._json({'ok': True, 'reset': out['reset']})

    # -------------------------------------------------------------------- admin
    def _deny(self):
        return self._json({'ok': False, 'error': 'permission_denied'}, status=403)

    @http.route(f'{API_PREFIX}/admin/templates', type='json2', auth='none',
                methods=['POST'], csrf=False)
    def admin_templates(self, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        if not ctx.get('admin_role'):
            return self._deny()
        rows = []
        for t in env['mezze.config.template'].sudo().search([]):
            rows.append({'id': t.id, 'name': t.name, 'kind': t.kind, 'state': t.state,
                         'version': t.version, 'count': t.line_count})
        return self._json({'ok': True, 'templates': rows})

    @http.route(f'{API_PREFIX}/admin/assignments', type='json2', auth='none',
                methods=['POST'], csrf=False)
    def admin_assignments(self, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        if not ctx.get('admin_role'):
            return self._deny()
        rows = []
        for a in env['mezze.config.assignment'].sudo().search([]):
            rows.append({'id': a.id, 'scope': a.scope, 'target': a.scope_ref or '*',
                         'template': a.template_id.name, 'effective': a.active and a.template_id.state == 'published'})
        return self._json({'ok': True, 'assignments': rows})

    @http.route(f'{API_PREFIX}/admin/locks', type='json2', auth='none',
                methods=['POST'], csrf=False)
    def admin_locks(self, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        if not ctx.get('admin_role'):
            return self._deny()
        rows = []
        for v in env['mezze.config.value'].sudo().search([('policy', 'in', ['bounded', 'locked'])]):
            rows.append({'setting': v.setting_key, 'scope': v.scope, 'policy': v.policy,
                         'value': v.value, 'affects': self._affects(v.scope)})
        return self._json({'ok': True, 'locks': rows})

    def _affects(self, scope):
        i = SCOPE_ORDER.index(scope)
        return ', '.join(SCOPE_ORDER[i + 1:]) or 'none'

    def _default_ref(self, ctx, scope, provided):
        """When an admin omits scope_ref, target the admin's OWN scope so an
        organization/branch lock keys off the admin's company/branch (the ref the
        resolver looks up for principals in that org/branch)."""
        if provided:
            return provided
        if scope == 'platform':
            return ''
        if scope == 'organization':
            return str(ctx.get('company_id') or '')
        if scope == 'branch':
            return str(ctx.get('branch_id') or '')
        return provided or ''

    @http.route(f'{API_PREFIX}/admin/permissions', type='json2', auth='none',
                methods=['POST'], csrf=False)
    def admin_permissions(self, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        if not ctx.get('admin_role'):
            return self._deny()
        roles = [{'role': r, 'caps': sorted(c)} for r, c in ADMIN_CAPS.items()]
        return self._json({'ok': True, 'roles': roles})

    @http.route(f'{API_PREFIX}/admin/audit', type='json2', auth='none',
                methods=['POST'], csrf=False)
    def admin_audit(self, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        if not self._can(ctx, 'audit.read'):
            return self._deny()
        rows = []
        logs = env['mezze.audit.log'].sudo().search(
            [('event', 'like', 'config.%')], order='id desc', limit=100)
        for lg in logs:
            d = {}
            try:
                d = json.loads(lg.detail or '{}')
            except Exception:  # noqa: BLE001
                d = {}
            rows.append({'at': str(lg.create_date or ''), 'actor': d.get('actor', ''),
                         'event': lg.event, 'scope': d.get('scope', ''),
                         'old': d.get('old', ''), 'new': d.get('new', '')})
        return self._json({'ok': True, 'entries': rows})

    # ---- admin writes ----
    @http.route(f'{API_PREFIX}/admin/template/create', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def admin_template_create(self, name=None, kind='role', **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        if not self._can(ctx, 'template.write'):
            return self._deny()
        if not name:
            return self._json({'ok': False, 'error': 'missing_name'}, status=400)
        t = env['mezze.config.template'].sudo().create({'name': name, 'kind': kind, 'state': 'draft'})
        env['mezze.settings']._audit('config.template_create', ctx.get('user_ref'),
                                     'template:%s' % t.id, 'name', None, name)
        return self._json({'ok': True, 'id': t.id})

    @http.route(f'{API_PREFIX}/admin/template/duplicate', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def admin_template_duplicate(self, template_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        if not self._can(ctx, 'template.write'):
            return self._deny()
        t = env['mezze.config.template'].sudo().browse(int(template_id or 0))
        if not t.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        dup = t.copy()
        env['mezze.settings']._audit('config.template_duplicate', ctx.get('user_ref'),
                                     'template:%s' % dup.id, 'from', str(t.id), str(dup.id))
        return self._json({'ok': True, 'id': dup.id})

    @http.route(f'{API_PREFIX}/admin/template/publish', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def admin_template_publish(self, template_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        if not self._can(ctx, 'template.write'):
            return self._deny()
        t = env['mezze.config.template'].sudo().browse(int(template_id or 0))
        if not t.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        old = t.state
        t.action_publish()
        env['mezze.settings']._audit('config.template_publish', ctx.get('user_ref'),
                                     'template:%s' % t.id, 'state', old, 'published')
        return self._json({'ok': True})

    @http.route(f'{API_PREFIX}/admin/template/archive', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def admin_template_archive(self, template_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        if not self._can(ctx, 'template.write'):
            return self._deny()
        t = env['mezze.config.template'].sudo().browse(int(template_id or 0))
        if not t.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        old = t.state
        t.action_archive()
        env['mezze.settings']._audit('config.template_archive', ctx.get('user_ref'),
                                     'template:%s' % t.id, 'state', old, 'archived')
        return self._json({'ok': True})

    @http.route(f'{API_PREFIX}/admin/lock', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def admin_lock(self, setting_key=None, scope='branch', scope_ref='', value=None,
                   policy='locked', **kw):
        """Set a scoped value + lock policy (free/bounded/locked). Shows nothing new
        to lower scopes beyond the audited change; enforcement is in the resolver."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        if not self._can(ctx, 'lock.write'):
            return self._deny()
        if not setting_key or value is None:
            return self._json({'ok': False, 'error': 'missing_args'}, status=400)
        if not env['mezze.setting.def'].validate_kv(setting_key, value):
            return self._json({'ok': False, 'error': 'invalid_value'}, status=400)
        # store_manager may only lock at/below its own branch
        if ctx.get('admin_role') == 'store_manager' and scope not in ('branch', 'role', 'user', 'device'):
            return self._deny()
        scope_ref = self._default_ref(ctx, scope, scope_ref)
        CV = env['mezze.config.value'].sudo()
        sval = 'true' if value is True else 'false' if value is False else str(value)
        row = CV.search([('setting_key', '=', setting_key), ('scope', '=', scope), ('scope_ref', '=', scope_ref or '')], limit=1)
        old = row.policy if row else None
        if row:
            row.write({'value': sval, 'policy': policy})
        else:
            CV.create({'setting_key': setting_key, 'scope': scope, 'scope_ref': scope_ref or '',
                       'value': sval, 'policy': policy, 'source_note': 'admin_lock'})
        env['mezze.settings']._audit('config.lock_set', ctx.get('user_ref'),
                                     '%s:%s' % (scope, scope_ref or '*'), setting_key, old, policy,
                                     subjects=self._affects(scope))
        return self._json({'ok': True})

    @http.route(f'{API_PREFIX}/admin/assign', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def admin_assign(self, template_id=None, scope='role', scope_ref='', **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        ctx, err = self._principal_ctx(env)
        if err:
            return err
        if not self._can(ctx, 'assign.write'):
            return self._deny()
        t = env['mezze.config.template'].sudo().browse(int(template_id or 0))
        if not t.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        scope_ref = self._default_ref(ctx, scope, scope_ref)
        Asg = env['mezze.config.assignment'].sudo()
        existing = Asg.search([('template_id', '=', t.id), ('scope', '=', scope), ('scope_ref', '=', scope_ref or '')], limit=1)
        if not existing:
            Asg.create({'template_id': t.id, 'scope': scope, 'scope_ref': scope_ref or '', 'active': True})
        env['mezze.settings']._audit('config.assign', ctx.get('user_ref'),
                                     '%s:%s' % (scope, scope_ref or '*'), 'template', None, t.name,
                                     subjects=self._affects(scope))
        return self._json({'ok': True})
