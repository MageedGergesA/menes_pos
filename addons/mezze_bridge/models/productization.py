"""S5 — productization runtime surface: release identity, support bundle, neutralized state.

This is NOT a new platform layer. It only READS existing config/version/deploy
facts and REPORTS them (support/diagnostics), reusing the go-live validator, the
edge-connectivity deployment-mode probe, and the secret store. Every diagnostic
export is scrubbed through :func:`..domain.redaction.redact` first — leakage = 0.
"""
import os
import subprocess

from odoo import api, models, release as odoo_release

from ..domain import redaction

# The Mezze PRODUCT version (distinct from the addon manifest version). Follows
# MAJOR.MINOR.PATCH; the pre-release suffix marks the release channel candidate.
MEZZE_PRODUCT_VERSION = '1.0.0-rc.1'
# Release channels: 'stable' (customer GA), 'rc' (release candidate / pilot),
# 'dev' (engineering). Overridable per-deployment via ir.config_parameter.
RELEASE_CHANNELS = ('stable', 'rc', 'dev')
DEFAULT_CHANNEL = 'rc'
# Editions — see docs/product/EDITIONS.md. Detected from the deployment mode.
EDITIONS = {'cloud': 'Mezze Cloud', 'edge': 'Mezze Edge'}


class MezzeProductization(models.AbstractModel):
    _name = 'mezze.productization'
    _description = 'Mezze product release identity, diagnostics & neutralized state'

    # ------------------------------------------------------------------ identity
    @api.model
    def _module_version(self):
        mod = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'mezze_bridge')], limit=1)
        return mod.latest_version or mod.installed_version or 'n/a'

    @api.model
    def _git_commit(self):
        """Best-effort build commit. Prefer an explicit deploy-stamped param
        (``mezze_bridge.build_commit``, set by the installer); fall back to a git
        query on the module tree; else 'n/a'. Never raises."""
        icp = self.env['ir.config_parameter'].sudo()
        stamped = (icp.get_param('mezze_bridge.build_commit') or '').strip()
        if stamped:
            return stamped
        try:
            here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            out = subprocess.run(['git', '-C', here, 'rev-parse', 'HEAD'],
                                 capture_output=True, text=True, timeout=3)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except Exception:  # noqa: BLE001
            pass
        return 'n/a'

    @api.model
    def deployment_mode(self):
        try:
            return self.env['mezze.edge.connectivity'].deployment_mode()
        except Exception:  # noqa: BLE001
            return 'cloud'

    @api.model
    def release_channel(self):
        icp = self.env['ir.config_parameter'].sudo()
        ch = (icp.get_param('mezze_bridge.release_channel') or DEFAULT_CHANNEL).strip().lower()
        return ch if ch in RELEASE_CHANNELS else DEFAULT_CHANNEL

    @api.model
    def release_identity(self):
        """The single answer to "what build is this?". Safe to expose to an
        authenticated admin — contains NO secrets."""
        mode = self.deployment_mode()
        icp = self.env['ir.config_parameter'].sudo()
        return {
            'product': 'Mezze POS',
            'product_version': MEZZE_PRODUCT_VERSION,
            'edition': EDITIONS.get(mode, EDITIONS['cloud']),
            'deployment_mode': mode,
            'module': 'mezze_bridge',
            'module_version': self._module_version(),
            'odoo_version': odoo_release.version,          # e.g. '19.0'
            'odoo_series': odoo_release.series,            # e.g. '19.0'
            'git_commit': self._git_commit(),
            'release_channel': self.release_channel(),
            'build': (icp.get_param('mezze_bridge.build_id') or 'n/a'),
            'neutralized': self.is_neutralized(),
            'env_profile': (icp.get_param('mezze_bridge.env_profile') or 'development'),
        }

    # -------------------------------------------------------------- neutralized
    @api.model
    def is_neutralized(self):
        """True when this database has been neutralized for staging/test — outbound
        side effects (aggregator callbacks, live online charging, notifications,
        real terminals) MUST be treated as inert. Honors Odoo's own neutralization
        marker as well as the Mezze one so a standard ``odoo neutralize`` is
        respected."""
        icp = self.env['ir.config_parameter'].sudo()
        if str(icp.get_param('mezze_bridge.neutralized', '')).strip().lower() in ('1', 'true', 'yes'):
            return True
        # Odoo core sets this during `odoo-bin neutralize`.
        return str(icp.get_param('database.is_neutralized', '')).strip().lower() in ('1', 'true', 'yes')

    # ------------------------------------------------------------- support bundle
    @api.model
    def support_bundle(self, profile='golive'):
        """A one-call, fully-redacted diagnostic bundle support can read WITHOUT DB
        archaeology. Contains: release identity, deployment facts, validator report,
        a config summary, and a redacted recent-log tail. NEVER contains a DB dump,
        orders, credentials, or PII — every text field passes through redact()."""
        icp = self.env['ir.config_parameter'].sudo()
        validator = self.env['mezze.golive.validator'].run(profile=profile)
        bundle = {
            'generated_by': 'mezze.productization.support_bundle',
            'release': self.release_identity(),
            'deployment': {
                'mode': self.deployment_mode(),
                'neutralized': self.is_neutralized(),
                'base_url': icp.get_param('web.base.url') or '',
                'db': self.env.cr.dbname,
            },
            'validator': {
                'profile': validator.get('profile'),
                'profile_label': validator.get('profile_label'),
                'overall': validator.get('overall'),
                'fails': validator.get('fails'),
                'warnings': validator.get('warnings'),
                'total': validator.get('total'),
                'checks': validator.get('checks'),
            },
            'config_summary': self._config_summary(),
            'log_tail': self._log_tail(),
        }
        # Defence in depth: serialize + redact the whole thing so nothing (a config
        # value, a log line, a check detail) leaks a secret even if a new field is
        # added later without thinking about redaction.
        return redaction.redact_json(bundle)

    @api.model
    def _config_summary(self):
        """Non-secret, support-relevant config keys. Values are redacted anyway; we
        only surface keys that are safe operational facts, never raw secrets."""
        icp = self.env['ir.config_parameter'].sudo()
        keys = [
            'mezze_bridge.env_profile', 'mezze_bridge.api_security',
            'mezze_bridge.shared_token_disabled', 'mezze_bridge.status_token_ttl_hours',
            'mezze_bridge.deployment_mode', 'mezze_bridge.release_channel',
            'mezze_bridge.neutralized', 'web.base.url',
        ]
        out = {}
        for k in keys:
            out[k] = redaction.redact(icp.get_param(k) or '')
        # counts, not contents
        out['_counts'] = {
            'pos_configs': self.env['pos.config'].sudo().search_count([]),
            'payment_methods': self.env['pos.payment.method'].sudo().search_count([]),
            'aggregator_channels': self.env['mezze.aggregator'].sudo().search_count([]),
            'audit_events': self.env['mezze.audit.log'].sudo().search_count([]),
        }
        return out

    @api.model
    def _log_tail(self, lines=200):
        """Last N lines of the Odoo logfile (if configured), redacted. Returns a
        note when no logfile path is available (e.g. stdout logging)."""
        try:
            from odoo.tools import config as _cfg
            path = _cfg.get('logfile')
            if not path or not os.path.isfile(path):
                return ['(no logfile configured — logs go to stdout/journal; '
                        'use the host support-bundle.sh for journald logs)']
            with open(path, 'r', errors='replace') as fh:
                tail = fh.readlines()[-lines:]
            return redaction.redact_lines([ln.rstrip('\n') for ln in tail])
        except Exception as e:  # noqa: BLE001
            return ['(log tail unavailable: %s)' % redaction.redact(str(e))]
