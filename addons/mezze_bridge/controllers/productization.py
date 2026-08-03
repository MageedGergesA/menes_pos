"""S5 — productization HTTP surface: release identity, go-live readiness,
support bundle, onboarding progress, audit export.

Thin JSON endpoints over the ``mezze.productization`` / ``mezze.golive.validator``
/ ``mezze.onboarding`` models. Every route is admin-gated by the canonical
``_authorize`` (the endpoints are registered as ADMIN_SETTINGS in domain.authz), so
there is no bespoke auth logic here. The support bundle is fully redacted by the
model before it is returned — no secret or PII path leaves through the controller.
Helper names are prefixed ``_prod_`` to stay unique within the addon's controller MRO.
"""
import json

from odoo import http
from odoo.http import request

from .main import MezzeBridgeController, API_PREFIX


class MezzeProductizationController(MezzeBridgeController):

    def _prod_actor(self, env):
        """Best-effort actor label for audit lines (never trusts client input)."""
        try:
            p = self._resolve_principal(env)
            c = p.get('cashier')
            return ('cashier:%s' % c.id) if c else p.get('principal', 'admin')
        except Exception:  # noqa: BLE001
            return 'admin'

    # ------------------------------------------------------------ release identity
    @http.route(f'{API_PREFIX}/admin/version', type='json2', auth='none',
                methods=['POST'], csrf=False)
    def admin_version(self, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        return self._json({'ok': True, 'release': env['mezze.productization'].release_identity()})

    # ------------------------------------------------------------- go-live readiness
    @http.route(f'{API_PREFIX}/admin/golive', type='json2', auth='none',
                methods=['POST'], csrf=False)
    def admin_golive(self, profile='golive', **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        report = env['mezze.golive.validator'].run(profile=profile)
        report['ok'] = True
        report['profiles'] = env['mezze.golive.validator'].profiles()
        return self._json(report)

    # -------------------------------------------------------------- support bundle
    @http.route(f'{API_PREFIX}/admin/support_bundle', type='json2', auth='none',
                methods=['POST'], csrf=False)
    def admin_support_bundle(self, profile='golive', **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        bundle = env['mezze.productization'].support_bundle(profile=profile)
        return self._json({'ok': True, 'bundle': bundle})

    # ------------------------------------------------------------------ onboarding
    @http.route(f'{API_PREFIX}/admin/onboarding', type='json2', auth='none',
                methods=['POST'], csrf=False)
    def admin_onboarding(self, profile='full', **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        return self._json(env['mezze.onboarding'].status(profile=profile))

    @http.route(f'{API_PREFIX}/admin/onboarding/ack', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def admin_onboarding_ack(self, step_id=None, done=True, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        if not step_id:
            return self._json({'ok': False, 'error': 'missing_step_id'}, status=400)
        return self._json(env['mezze.onboarding'].acknowledge(step_id, done=bool(done)))

    # --------------------------------------------------------------- audit export
    @http.route(f'{API_PREFIX}/admin/audit/export', type='json2', auth='none',
                methods=['POST'], csrf=False)
    def admin_audit_export(self, event=None, limit=500, **kw):
        """Full-trail audit query/export (the ``audit.export`` capability existed but
        had no endpoint). Bounded, redacted, and never returns order/PII content —
        only the audit metadata already stored on mezze.audit.log."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        from ..domain import redaction
        limit = max(1, min(int(limit or 500), 5000))
        dom = []
        if event:
            dom.append(('event', 'like', str(event)))
        rows = []
        for lg in env['mezze.audit.log'].sudo().search(dom, order='id desc', limit=limit):
            rows.append({
                'id': lg.id, 'at': str(lg.create_date or ''), 'event': lg.event,
                'severity': lg.severity, 'user': lg.user_id.login if lg.user_id else '',
                'terminal': lg.terminal_id.identifier if lg.terminal_id else '',
                'res_model': lg.res_model or '',
                'res_id': lg.res_id or 0, 'amount': lg.amount or 0.0,
                'detail': redaction.redact(lg.detail or ''),
            })
        return self._json({'ok': True, 'count': len(rows), 'limit': limit, 'entries': rows})
