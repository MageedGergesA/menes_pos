"""S1.1A — Edge connectivity contract.

Three independent concepts, never collapsed into one ``online`` boolean:
  * LOCAL SERVER   — client-derived (if this RPC succeeds, the local server is ONLINE;
                     the server never claims it is UNAVAILABLE while answering).
  * WAN / INTERNET — backend-derived by probing multiple configurable HTTPS targets.
  * EXTERNAL SVCS  — backend-derived from actually-configured Mezze integrations.

The WAN probe is cached in-process (per worker) so it never storms the network and
never runs synchronously on every request. Probe failure must never break local
restaurant workflows. Read-only; no writes, no secrets in the payload.
"""
import logging
import time
import urllib.request

from odoo import api, models

_logger = logging.getLogger(__name__)

# per-process WAN probe cache: {dbname: {ts_monotonic, state, checked_at, last_success_at}}
_WAN_CACHE = {}

WAN_ONLINE, WAN_OFFLINE, WAN_UNKNOWN = 'online', 'offline', 'unknown'
EXT_ONLINE, EXT_DEGRADED, EXT_PAUSED, EXT_NA, EXT_UNKNOWN = 'online', 'degraded', 'paused', 'n/a', 'unknown'


class MezzeEdgeConnectivity(models.AbstractModel):
    _name = 'mezze.edge.connectivity'
    _description = 'Mezze Edge connectivity status (deployment mode / WAN / external services)'

    # ------------------------------------------------------------------ config
    @api.model
    def deployment_mode(self):
        """'edge' or 'cloud'. Explicit only: env var first, then a config param,
        default 'cloud' (preserves current behavior; the WAN UI stays hidden).
        Never inferred from hostname/db/printer/path."""
        import os
        mode = (os.environ.get('MEZZE_DEPLOYMENT_MODE')
                or self.env['ir.config_parameter'].sudo().get_param('mezze_bridge.deployment_mode')
                or 'cloud').strip().lower()
        return mode if mode in ('cloud', 'edge') else 'cloud'

    @api.model
    def _probe_targets(self):
        import os
        raw = (os.environ.get('MEZZE_WAN_PROBE_URLS')
               or self.env['ir.config_parameter'].sudo().get_param('mezze_bridge.wan_probe_urls')
               or '')
        return [u.strip() for u in raw.split(',') if u.strip()]

    @api.model
    def _probe_interval(self):
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param('mezze_bridge.wan_probe_interval') or 20)
        except (TypeError, ValueError):
            return 20

    @api.model
    def _probe_timeout(self):
        try:
            return float(self.env['ir.config_parameter'].sudo().get_param('mezze_bridge.wan_probe_timeout') or 3.0)
        except (TypeError, ValueError):
            return 3.0

    # ------------------------------------------------------------------ probe
    @api.model
    def _http_ok(self, url, timeout):
        """Single read-only reachability probe. No auth, no POST, no tracking.
        Overridden in tests so no test ever touches the real Internet."""
        try:
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — configurable HTTPS targets
                return 200 <= getattr(resp, 'status', 200) < 500
        except Exception:  # noqa: BLE001 — any failure = this target unreachable
            return False

    @api.model
    def _probe_wan(self, force=False):
        """Cached WAN probe. Returns {state, checked_at, last_success_at}.
        any target ok -> online ; all fail -> offline ; none configured / error -> unknown."""
        db = self.env.cr.dbname
        now = time.monotonic()
        cached = _WAN_CACHE.get(db)
        interval = self._probe_interval()
        if cached and not force and (now - cached['ts']) < interval:
            return {k: cached[k] for k in ('state', 'checked_at', 'last_success_at')}

        targets = self._probe_targets()
        last_success = cached['last_success_at'] if cached else None
        checked_at = self._now_iso()
        try:
            if not targets:
                state = WAN_UNKNOWN
            else:
                timeout = self._probe_timeout()
                ok = any(self._http_ok(u, timeout) for u in targets)
                state = WAN_ONLINE if ok else WAN_OFFLINE
                if ok:
                    last_success = checked_at
        except Exception:  # noqa: BLE001 — probe subsystem error must never break callers
            _logger.exception("Mezze WAN probe subsystem error")
            state = WAN_UNKNOWN
        _WAN_CACHE[db] = {'ts': now, 'state': state, 'checked_at': checked_at,
                          'last_success_at': last_success}
        return {'state': state, 'checked_at': checked_at, 'last_success_at': last_success}

    @api.model
    def _now_iso(self):
        from odoo import fields
        return fields.Datetime.to_string(fields.Datetime.now())

    # ------------------------------------------------- external service health
    @api.model
    def external_services(self, wan_state):
        """Derive external-service status from ACTUAL configured integrations.
        Never 'healthy just because Internet works'."""
        services = {}
        # aggregator: configured iff an active channel exists
        try:
            aggs = self.env['mezze.aggregator'].sudo().search([('active', '=', True)])
            if aggs:
                # DEGRADED if any active channel is missing its secret (misconfigured)
                broken = aggs.filtered(lambda a: not a.sudo().secret_enc)
                services['aggregator'] = 'degraded' if broken else 'online'
        except Exception:  # noqa: BLE001
            pass
        # remote/off-site backup: configured iff the param is set to enabled
        try:
            off = str(self.env['ir.config_parameter'].sudo().get_param(
                'mezze_bridge.offsite_backup_enabled', '')).strip().lower() in ('1', 'true', 'yes')
            if off:
                services['remote_backup'] = 'configured'
        except Exception:  # noqa: BLE001
            pass
        # outbox backlog is a local concern, not an external service; not reported here.

        if not services:
            return {'state': EXT_NA, 'services': {}}
        if wan_state == WAN_OFFLINE:
            # every WAN-dependent configured service is paused during a WAN outage
            paused = {k: 'paused' for k in services}
            return {'state': EXT_PAUSED, 'services': paused}
        if wan_state == WAN_UNKNOWN:
            return {'state': EXT_UNKNOWN, 'services': services}
        # WAN online: degraded if any configured service is unhealthy/misconfigured
        unhealthy = [k for k, v in services.items() if v in ('degraded', 'error', 'backlogged')]
        return {'state': EXT_DEGRADED if unhealthy else EXT_ONLINE, 'services': services}

    # ------------------------------------------------------------------ status
    @api.model
    def status(self):
        """Full read-only connectivity contract. No 'local_server' field — the
        frontend derives that from whether THIS RPC succeeds."""
        wan = self._probe_wan()
        ext = self.external_services(wan['state'])
        return {
            'deployment_mode': self.deployment_mode(),
            'wan': {
                'state': wan['state'],
                'checked_at': wan['checked_at'],
                'last_success_at': wan['last_success_at'],
            },
            'external_services': ext,
        }
