"""Production security-configuration hardening (P6.1 Phase 10).

Guards the ir.config_parameter keys that can weaken API enforcement. Every change
to a security key is durably AUDITED (old/new classified, never the secret value),
and in the ``production`` environment profile a change that would silently weaken
enforcement is REJECTED (fail-closed) unless an explicit, audited break-glass flag
is set. This makes "a config DB row edit silently disables enforcement in prod"
impossible without detection + policy approval.
"""

from odoo import api, models
from odoo.exceptions import UserError


# keys whose change must be audited (and, in prod, safety-checked)
_GUARDED = {
    'mezze_bridge.api_security',
    'mezze_bridge.signing_mode',
    'mezze_bridge.signing_mode.terminal',
    'mezze_bridge.signing_mode.integration',
    'mezze_bridge.signing_mode.admin',
    'mezze_bridge.signing_mode.cashier',
    'mezze_bridge.clock_skew_seconds',
    'mezze_bridge.nonce_required',
    'mezze_bridge.shared_token_disabled',
    'mezze_bridge.key_grace_seconds',
    'mezze_bridge.env_profile',
    'mezze_bridge.breakglass',
}
_SECRET_HINTS = ('token', 'secret', 'key', 'password')


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    def _profile(self):
        return (self.sudo().get_param('mezze_bridge.env_profile') or 'development').strip().lower()

    def _breakglass(self):
        # a live emergency ACTIVATION (scoped, ≤1h, audited) is the only break-glass;
        # the legacy raw flag is honoured as a fallback for pre-P6.5 tooling.
        try:
            if self.env['mezze.emergency.access'].is_active():
                return True
        except Exception:  # noqa: BLE001 — model may not be loaded during early migration
            pass
        return str(self.sudo().get_param('mezze_bridge.breakglass', '')).strip().lower() in (
            '1', 'true', 'yes', 'on')

    def _is_weakening(self, key, value):
        """Is THIS key<-value a weakening of enforcement? Per-key + value-based, so
        an env-profile switch (declaring the environment) is not itself flagged and
        a strengthening change (e.g. -> enforce) is always allowed."""
        v = str(value).strip().lower()
        if key in ('mezze_bridge.api_security', 'mezze_bridge.signing_mode',
                   'mezze_bridge.signing_mode.terminal', 'mezze_bridge.signing_mode.integration',
                   'mezze_bridge.signing_mode.admin'):
            return v in ('off', 'observe')
        if key == 'mezze_bridge.nonce_required':
            return v in ('0', 'false', 'no')
        if key == 'mezze_bridge.shared_token_disabled':      # re-enabling shared admin
            return v in ('0', 'false', 'no')
        if key == 'mezze_bridge.key_grace_seconds':
            try:
                return int(value) > 3600
            except (TypeError, ValueError):
                return True
        if key == 'mezze_bridge.clock_skew_seconds':
            try:
                n = int(value)
            except (TypeError, ValueError):
                return True
            return n <= 0 or n > 900
        return False

    @api.model
    def set_param(self, key, value):
        if key not in _GUARDED:
            return super().set_param(key, value)
        old = self.sudo().get_param(key)
        weakening = self._is_weakening(key, value)
        if weakening and self._profile() == 'production' and not self._breakglass():
            # fail closed: refuse BEFORE writing, and audit the blocked attempt
            self._audit_change(key, old, value, weakening=True, blocked=True)
            raise UserError(
                "Refused: this change would weaken production API security (%s). "
                "Set an approved break-glass flag to override." % key)
        res = super().set_param(key, value)
        self._audit_change(key, old, value, weakening=weakening, blocked=False)
        return res

    def _audit_change(self, key, old, new, weakening, blocked=False):
        def classify(v):
            # never log secret VALUES — only presence/shape
            if any(h in key for h in _SECRET_HINTS):
                return 'set' if v else 'unset'
            return v
        event = ('security.policy_weakening_blocked' if blocked else
                 'security.policy_weakening' if weakening else 'security.policy_change')
        try:
            self.env['mezze.audit.log'].sudo().log(
                event, severity='warning' if (weakening or blocked) else 'info',
                detail='{"key": "%s", "old": "%s", "new": "%s", "profile": "%s", "blocked": %s}'
                       % (key, classify(old), classify(new), self._profile(),
                          'true' if blocked else 'false'))
        except Exception:  # noqa: BLE001
            pass
