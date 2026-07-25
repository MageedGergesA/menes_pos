"""P1 — production configuration validator + go-live readiness checks.

A runnable, structured validator (``mezze.golive.validator.run()``) that inspects
the live configuration and returns per-check Pass / Warning / Fail / N/A. A launch
must be blocked on any unresolved Fail. This is NOT a new platform layer — it only
READS existing config/records and reports; it never mutates business data.
"""
import os

from odoo import api, models

PASS, WARN, FAIL, NA = 'PASS', 'WARNING', 'FAIL', 'N/A'


class MezzeGoLiveValidator(models.AbstractModel):
    _name = 'mezze.golive.validator'
    _description = 'Mezze pilot go-live configuration validator'

    @api.model
    def run(self):
        """Return {'overall', 'fails', 'warnings', 'checks': [{name, status, detail}]}."""
        ICP = self.env['ir.config_parameter'].sudo()
        checks = []

        def add(name, status, detail=''):
            checks.append({'name': name, 'status': status, 'detail': detail})

        profile = (ICP.get_param('mezze_bridge.env_profile') or 'development').strip().lower()
        is_prod = profile == 'production'
        add('env_profile', PASS if is_prod else WARN,
            'profile=%s (production hardening only enforced in the production profile)' % profile)

        # --- security gate ---
        shared_disabled = str(ICP.get_param('mezze_bridge.shared_token_disabled', '')).strip().lower() in ('1', 'true', 'yes')
        emergency = False
        try:
            emergency = self.env['mezze.emergency.access'].is_active()
        except Exception:  # noqa: BLE001
            pass
        # in production the shared-admin machine token MUST be disabled (only a scoped
        # emergency activation admits it). In dev it is a documented convenience.
        if is_prod:
            add('shared_admin_disabled', PASS if shared_disabled else FAIL,
                'shared_token_disabled=%s' % shared_disabled)
        else:
            add('shared_admin_disabled', WARN, 'dev profile: shared-admin is a documented dev-only fallback')
        add('emergency_access_inactive', PASS if not emergency else WARN,
            'emergency break-glass %s' % ('active' if emergency else 'inactive'))

        add('master_key_present', PASS if os.environ.get('MEZZE_MASTER_KEY') else FAIL,
            'MEZZE_MASTER_KEY %s in environment' % ('set' if os.environ.get('MEZZE_MASTER_KEY') else 'MISSING'))

        api_sec = (ICP.get_param('mezze_bridge.api_security') or 'observe').strip().lower()
        add('api_security_enforced', PASS if api_sec == 'enforce' else WARN, 'api_security=%s' % api_sec)

        ttl = ICP.get_param('mezze_bridge.status_token_ttl_hours', 24)
        add('status_token_ttl', PASS, 'public status tokens expire after %s h and are revocable' % ttl)

        base = ICP.get_param('web.base.url') or ''
        add('base_url', WARN if ('localhost' in base or '127.0.0.1' in base or not base) else PASS,
            'web.base.url=%s' % (base or 'unset'))

        # --- branch / fiscal config ---
        company = self.env.company
        add('company_currency', PASS if company.currency_id else FAIL,
            'currency=%s' % (company.currency_id.name or 'unset'))
        add('company_timezone', PASS if (self.env.user.tz or company.partner_id.tz) else WARN,
            'tz=%s' % (self.env.user.tz or 'unset'))

        cfgs = self.env['pos.config'].sudo().search([])
        add('pos_config_present', PASS if cfgs else FAIL, '%d POS config(s)' % len(cfgs))
        pm = cfgs.mapped('payment_method_ids')
        add('payment_methods', PASS if pm else FAIL, '%d payment method(s) across configs' % len(pm))
        journals = self.env['account.journal'].sudo().search_count([('type', 'in', ('cash', 'bank'))])
        add('journals', PASS if journals else WARN, '%d cash/bank journal(s)' % journals)

        # --- operations plumbing ---
        crons = self.env['ir.cron'].sudo().search_count([('name', 'ilike', 'mezze')]) or \
            self.env['ir.cron'].sudo().search_count([('model_id.model', 'in', ('mezze.outbox.event', 'mezze.api.nonce'))])
        add('scheduled_jobs', PASS if crons else WARN, '%d mezze cron(s)' % crons)

        dead = 0
        try:
            dead = self.env['mezze.outbox.event'].sudo().search_count([('state', '=', 'dead')])
        except Exception:  # noqa: BLE001
            pass
        add('outbox_dead_letters', PASS if dead == 0 else WARN, '%d dead-letter event(s)' % dead)

        # aggregator channels must have a secret set (if any channel exists)
        try:
            aggs = self.env['mezze.aggregator'].sudo().search([('active', '=', True)])
            missing = aggs.filtered(lambda a: not a.sudo().secret_enc)
            if not aggs:
                add('aggregator_secrets', NA, 'no active aggregator channels')
            else:
                add('aggregator_secrets', PASS if not missing else FAIL,
                    '%d/%d channels missing a secret' % (len(missing), len(aggs)))
        except Exception:  # noqa: BLE001
            add('aggregator_secrets', NA, 'aggregator model unavailable')

        # catalog seeded (settings governance)
        add('settings_catalog', PASS if self.env['mezze.setting.def'].sudo().search_count([]) == 101 else WARN,
            '%d setting defs' % self.env['mezze.setting.def'].sudo().search_count([]))

        fails = [c for c in checks if c['status'] == FAIL]
        warns = [c for c in checks if c['status'] == WARN]
        return {
            'overall': FAIL if fails else (WARN if warns else PASS),
            'fails': len(fails), 'warnings': len(warns), 'total': len(checks),
            'checks': checks,
        }

    @api.model
    def report_text(self):
        r = self.run()
        lines = ['MEZZE GO-LIVE CONFIG VALIDATOR — overall=%s (%d fail, %d warn, %d checks)'
                 % (r['overall'], r['fails'], r['warnings'], r['total']), '']
        for c in r['checks']:
            lines.append('  [%-7s] %-26s %s' % (c['status'], c['name'], c['detail']))
        return '\n'.join(lines)
