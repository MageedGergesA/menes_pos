"""Mezze Design Platform — configuration cascade, templates, locks & audit (D1).

Implements the effective-setting cascade

    platform -> organization -> brand -> branch -> role -> user -> device

with per-scope lock policies (free / bounded / locked), reusable templates that
can be assigned by scope, and a resolver that returns, for every setting, the
resolved value + source scope + source record + lock policy + user override +
effective reason. A lower scope may NEVER bypass a higher-scope ``locked`` policy.

The catalog mirrors the front-end (static/mezze-design.js) so the running app and
the server agree on ids, types, defaults and allowed options; the SERVER is the
authority for the cascade, locks and provenance. Presentation-only ``session``
state (a temporary preview) lives in the browser and never writes durable rows.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..domain import settings_catalog as SC

# ordered low -> high; a value at a later scope overrides an earlier one unless a
# higher scope has locked the key.
SCOPE_ORDER = ['platform', 'organization', 'brand', 'branch', 'role', 'user', 'device']
POLICIES = ['free', 'bounded', 'locked']

# D3 — the AUTHORITATIVE catalog is the 101-setting source of truth extracted from
# Settings.html (domain/settings_catalog.py). ``CATALOG`` keeps the legacy 6-tuple
# shape for callers; STATUS/REASON carry the honest working|disabled|hidden state.
CATALOG = [(c[0], c[1], c[2], c[3], c[4], ('live' if c[5] == 'working' else 'pref'))
           for c in SC.CATALOG_101]
_STATUS = {c[0]: c[5] for c in SC.CATALOG_101}
_REASON = {c[0]: c[6] for c in SC.CATALOG_101}


class MezzeSettingDef(models.Model):
    _name = 'mezze.setting.def'
    _description = 'Mezze setting catalog entry'
    _order = 'category, key'

    key = fields.Char(required=True, index=True)
    category = fields.Char(required=True)
    value_type = fields.Selection([('enum', 'Enum'), ('bool', 'Bool'), ('int', 'Int'), ('key', 'Key')], default='enum', required=True)
    default_value = fields.Char()
    options = fields.Char(help='Comma-separated allowed values for enum; "min..max" for int.')
    effect = fields.Selection([('live', 'Live'), ('pref', 'Preference')], default='live')
    # D3 honest status: working (real runtime effect), disabled (read-only + reason),
    # hidden (not presented). Never an enabled control with no effect.
    status = fields.Selection([('working', 'Working'), ('disabled', 'Disabled'),
                               ('hidden', 'Hidden')], default='working')
    reason = fields.Char(help='Runtime consumer (working) or the accurate disabled/hidden reason.')

    _sql_constraints = [('mezze_setting_def_key_uniq', 'unique(key)', 'Setting key must be unique.')]

    @api.model
    def seed_catalog(self):
        """Idempotently ensure every catalog entry (all 101) exists / is up to date."""
        existing = {r.key: r for r in self.sudo().search([])}
        wanted = set()
        for key, cat, vt, dv, opts, eff in CATALOG:
            wanted.add(key)
            vals = {'category': cat, 'value_type': vt, 'default_value': dv, 'options': opts,
                    'effect': eff, 'status': _STATUS.get(key, 'working'),
                    'reason': _REASON.get(key, '')}
            if key in existing:
                existing[key].sudo().write(vals)
            else:
                self.sudo().create(dict(vals, key=key))
        # D3 — prune stale pre-101 definitions so the catalog is EXACTLY the 101 ids.
        stale = self.sudo().search([('key', 'not in', list(wanted))])
        if stale:
            stale.unlink()
        return True

    def allowed_options(self):
        self.ensure_one()
        return [o for o in (self.options or '').split(',') if o]

    def is_valid(self, value):
        self.ensure_one()
        v = '' if value is None else str(value)
        if self.value_type == 'bool':
            return v.lower() in ('true', 'false', '1', '0')
        if self.value_type == 'key':
            return len(v) <= 24                       # a shortcut binding string
        if self.value_type == 'int':
            try:
                n = int(v)
            except (TypeError, ValueError):
                return False
            # server-side range validation for "min..max" bounded ints (not just JS clamp)
            if self.options and '..' in self.options:
                lo, hi = self.options.split('..', 1)
                try:
                    return int(lo) <= n <= int(hi)
                except (TypeError, ValueError):
                    return True
            return True
        opts = self.allowed_options()
        return (not opts) or (v in opts)

    def allowed_range(self):
        """(min, max) for a bounded int, else None."""
        self.ensure_one()
        if self.value_type == 'int' and self.options and '..' in self.options:
            lo, hi = self.options.split('..', 1)
            try:
                return (int(lo), int(hi))
            except (TypeError, ValueError):
                return None
        return None

    @api.model
    def validate_kv(self, key, value):
        rec = self.sudo().search([('key', '=', key)], limit=1)
        return bool(rec) and rec.is_valid(value)


class MezzeConfigValue(models.Model):
    _name = 'mezze.config.value'
    _description = 'Mezze scoped configuration value'
    _order = 'setting_key'

    setting_key = fields.Char(required=True, index=True)
    scope = fields.Selection([(s, s.title()) for s in SCOPE_ORDER], required=True, index=True)
    scope_ref = fields.Char(default='', index=True,
                            help='Identifier within the scope (company id, branch/config id, role, '
                                 'user/cashier id, device identifier). Empty for platform.')
    value = fields.Char(required=True)
    policy = fields.Selection([(p, p.title()) for p in POLICIES], default='free', required=True)
    bounded_options = fields.Char(help='For policy=bounded: comma-separated subset a lower scope may pick from.')
    template_id = fields.Many2one('mezze.config.template', ondelete='set null')
    source_note = fields.Char()

    _sql_constraints = [
        ('mezze_config_value_uniq', 'unique(setting_key, scope, scope_ref)',
         'One value per setting per scope target.'),
    ]

    @api.constrains('scope', 'policy', 'setting_key', 'value')
    def _check_valid(self):
        Def = self.env['mezze.setting.def'].sudo()
        for r in self:
            if r.scope not in SCOPE_ORDER:
                raise ValidationError('Unknown scope %s' % r.scope)
            d = Def.search([('key', '=', r.setting_key)], limit=1)
            if d and not d.is_valid(r.value):
                raise ValidationError('Value %r is not allowed for %s.' % (r.value, r.setting_key))


class MezzeConfigTemplate(models.Model):
    _name = 'mezze.config.template'
    _description = 'Mezze configuration template'
    _order = 'name'

    name = fields.Char(required=True)
    kind = fields.Selection([('organization', 'Organization'), ('brand', 'Brand'), ('branch', 'Branch/Store'),
                             ('role', 'Role'), ('user', 'User'), ('device', 'Register/Device')],
                            default='role', required=True)
    state = fields.Selection([('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')],
                             default='draft', required=True)
    version = fields.Integer(default=1)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many('mezze.config.template.line', 'template_id')
    assignment_ids = fields.One2many('mezze.config.assignment', 'template_id')
    line_count = fields.Integer(compute='_compute_counts')

    def _compute_counts(self):
        for r in self:
            r.line_count = len(r.line_ids)

    def action_publish(self):
        for r in self:
            r.state = 'published'
        return True

    def action_archive(self):
        for r in self:
            r.state = 'archived'
            r.active = False
        return True

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault('name', '%s (copy)' % self.name)
        default.setdefault('state', 'draft')
        return super().copy(default)

    def new_version(self):
        self.ensure_one()
        dup = self.copy({'name': self.name, 'version': self.version + 1, 'state': 'draft'})
        return dup


class MezzeConfigTemplateLine(models.Model):
    _name = 'mezze.config.template.line'
    _description = 'Mezze configuration template line'

    template_id = fields.Many2one('mezze.config.template', required=True, ondelete='cascade')
    setting_key = fields.Char(required=True)
    value = fields.Char(required=True)
    policy = fields.Selection([(p, p.title()) for p in POLICIES], default='free', required=True)
    bounded_options = fields.Char()


class MezzeConfigAssignment(models.Model):
    _name = 'mezze.config.assignment'
    _description = 'Mezze template assignment to a scope target'
    _order = 'scope, scope_ref'

    template_id = fields.Many2one('mezze.config.template', required=True, ondelete='cascade')
    scope = fields.Selection([(s, s.title()) for s in SCOPE_ORDER], required=True)
    scope_ref = fields.Char(default='')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('mezze_assignment_uniq', 'unique(scope, scope_ref, template_id)',
         'A template is assigned once per scope target.'),
    ]


class MezzeSettings(models.AbstractModel):
    """Resolver service — the ONE place the effective cascade is computed."""
    _name = 'mezze.settings'
    _description = 'Mezze effective settings resolver'

    # --- catalog snapshot -----------------------------------------------------
    @api.model
    def catalog(self):
        """Read-only catalog snapshot. Reads the seeded ``mezze.setting.def`` rows;
        if the table is empty (never migrated), falls back to the in-memory CATALOG
        constant WITHOUT writing — so this is safe on read-only request cursors."""
        out = {}
        for d in self.env['mezze.setting.def'].sudo().search([]):
            out[d.key] = {'category': d.category, 'type': d.value_type,
                          'default': d.default_value, 'options': d.allowed_options(),
                          'range': d.allowed_range(), 'effect': d.effect,
                          'status': d.status, 'reason': d.reason or ''}
        if not out:
            for cid, sec, typ, dv, opts, status, reason, old in SC.CATALOG_101:
                out[cid] = {'category': sec, 'type': typ, 'default': dv,
                            'options': [o for o in opts.split(',') if o and '..' not in o],
                            'range': None, 'effect': ('live' if status == 'working' else 'pref'),
                            'status': status, 'reason': reason}
        return out

    @api.model
    def _coerce(self, key, raw):
        d = self.env['mezze.setting.def'].sudo().search([('key', '=', key)], limit=1)
        if d and d.value_type == 'bool':
            return str(raw).lower() in ('true', '1', 'yes')
        return raw

    @api.model
    def _scope_targets(self, ctx):
        """Map each scope to the concrete ref for this principal (or None to skip)."""
        return {
            'platform': '',                                   # global
            'organization': str(ctx.get('company_id') or '') or None,
            'brand': str(ctx.get('brand_id') or '') or None,
            'branch': str(ctx.get('branch_id') or '') or None,
            'role': (ctx.get('role') or None),
            'user': (str(ctx.get('user_ref')) if ctx.get('user_ref') else None),
            'device': (str(ctx.get('device_ref')) if ctx.get('device_ref') else None),
        }

    @api.model
    def resolve(self, ctx):
        """Resolve the effective settings for a principal context ``ctx`` with keys:
        company_id, brand_id, branch_id, role, user_ref, device_ref.

        Returns {effective, provenance, locks, overrides}. A higher-scope ``locked``
        policy freezes the value for every lower scope (including user/device).
        """
        cat = self.catalog()
        CV = self.env['mezze.config.value'].sudo()
        Asg = self.env['mezze.config.assignment'].sudo()

        effective = {k: self._coerce(k, cat[k]['default']) for k in cat}
        provenance = {k: {'scope': 'default', 'source': 'catalog', 'lock': 'free', 'reason': 'default'} for k in cat}
        locks = {}
        lock_scope_idx = {}     # key -> index of the scope that locked it

        targets = self._scope_targets(ctx)
        for idx, scope in enumerate(SCOPE_ORDER):
            ref = targets.get(scope)
            if ref is None:
                continue
            # gather this scope's contributions: published-template lines first, then
            # direct values (direct overrides the template at the same scope).
            contributions = {}   # key -> (value, policy, source, bounded)
            asgs = Asg.search([('scope', '=', scope), ('scope_ref', '=', ref or ''), ('active', '=', True)])
            for a in asgs:
                if a.template_id.state != 'published':
                    continue
                for ln in a.template_id.line_ids:
                    contributions[ln.setting_key] = (ln.value, ln.policy, 'template:%s' % a.template_id.name, ln.bounded_options)
            for v in CV.search([('scope', '=', scope), ('scope_ref', '=', ref or '')]):
                contributions[v.setting_key] = (v.value, v.policy, v.source_note or ('%s:%s' % (scope, ref or '*')), v.bounded_options)

            for key, (val, policy, source, bounded) in contributions.items():
                if key not in cat:
                    continue
                # a higher scope lock cannot be overridden by this (lower/equal-later) scope
                if key in lock_scope_idx and lock_scope_idx[key] < idx:
                    continue
                effective[key] = self._coerce(key, val)
                provenance[key] = {'scope': scope, 'source': source, 'lock': policy,
                                   'reason': '%s scope %s' % (policy, scope)}
                if policy == 'locked':
                    locks[key] = 'locked'
                    lock_scope_idx[key] = idx
                elif policy == 'bounded':
                    locks[key] = 'bounded'
                    if bounded:
                        provenance[key]['bounded_options'] = bounded
                else:
                    locks.pop(key, None)

        # user overrides = direct config.value rows at scope 'user' (already folded
        # above); expose them separately for the UI's "personal vs effective" view.
        overrides = {}
        if targets.get('user'):
            for v in CV.search([('scope', '=', 'user'), ('scope_ref', '=', targets['user'])]):
                if v.setting_key in cat and locks.get(v.setting_key) != 'locked':
                    overrides[v.setting_key] = self._coerce(v.setting_key, v.value)

        return {'effective': effective, 'provenance': provenance, 'locks': locks, 'overrides': overrides}

    # --- persistence ----------------------------------------------------------
    @api.model
    def save_user(self, ctx, values, actor=None):
        """Persist a user's personal overrides (scope='user'), rejecting locked keys
        (fail-closed) and validating bounded ranges. Returns {saved, rejected}."""
        user_ref = str(ctx.get('user_ref') or '')
        if not user_ref:
            raise UserError('No authenticated user for settings persistence.')
        resolved = self.resolve(ctx)
        locks = resolved['locks']
        CV = self.env['mezze.config.value'].sudo()
        Def = self.env['mezze.setting.def'].sudo()
        saved, rejected = [], []
        for key, val in (values or {}).items():
            d = Def.search([('key', '=', key)], limit=1)
            if not d or not d.is_valid(val):
                rejected.append(key)
                continue
            # D3: a non-'working' setting is not user-writable (disabled=read-only,
            # hidden=absent) — the API refuses it so no no-effect value is persisted.
            if d.status and d.status != 'working':
                rejected.append(key)
                continue
            if locks.get(key) == 'locked':
                rejected.append(key)                          # cannot bypass a higher lock
                continue
            sval = 'true' if val is True else 'false' if val is False else str(val)
            row = CV.search([('setting_key', '=', key), ('scope', '=', 'user'), ('scope_ref', '=', user_ref)], limit=1)
            old = row.value if row else None
            if row:
                row.value = sval
            else:
                CV.create({'setting_key': key, 'scope': 'user', 'scope_ref': user_ref, 'value': sval, 'policy': 'free'})
            saved.append(key)
            self._audit('config.user_save', actor, 'user:%s' % user_ref, key, old, sval)
        return {'saved': saved, 'rejected': rejected}

    @api.model
    def reset_user(self, ctx, section=None, actor=None):
        user_ref = str(ctx.get('user_ref') or '')
        if not user_ref:
            return {'reset': 0}
        CV = self.env['mezze.config.value'].sudo()
        dom = [('scope', '=', 'user'), ('scope_ref', '=', user_ref)]
        if section and section != 'all':
            keys = [d.key for d in self.env['mezze.setting.def'].sudo().search([('category', '=', section)])]
            dom.append(('setting_key', 'in', keys or ['__none__']))
        rows = CV.search(dom)
        n = len(rows)
        for r in rows:
            self._audit('config.user_reset', actor, 'user:%s' % user_ref, r.setting_key, r.value, None)
        rows.unlink()
        return {'reset': n}

    # --- audit ----------------------------------------------------------------
    @api.model
    def _audit(self, event, actor, scope, key, old, new, reason=None, subjects=None):
        import json
        try:
            self.env['mezze.audit.log'].sudo().log(
                event, severity='info',
                detail=json.dumps({'actor': actor or 'system', 'scope': scope, 'setting': key,
                                   'old': old, 'new': new, 'reason': reason or '',
                                   'subjects': subjects or ''}))
        except Exception:  # noqa: BLE001
            pass
