"""Centralized machine-secret access (P6.2 Phase 14).

The ONE server-side abstraction that encrypts/decrypts machine secrets. No
controller reads a ciphertext field directly; no generic ORM/RPC/serialization
returns a secret. The master key is loaded from the environment only (never DB /
source). Missing key or any crypto failure => fail closed (deny), and every
decryption records a metadata-only access audit (never the plaintext).
"""
import logging

from odoo import api, models

from ..domain import crypto

_logger = logging.getLogger(__name__)


class MezzeSecretStore(models.AbstractModel):
    _name = 'mezze.secret.store'
    _description = 'Mezze machine-secret access (envelope encryption)'

    @api.model
    def _master_key(self):
        return crypto.load_master_key_from_env()

    @api.model
    def available(self):
        """True when a valid master key is configured (used by the config guard)."""
        return self._master_key() is not None

    @api.model
    def encrypt(self, plaintext, kid='mk1', aad=b''):
        """Encrypt a secret for at-rest storage. Fails closed if no master key."""
        mk = self._master_key()
        if mk is None:
            raise crypto.SecretError('master_key_unavailable')
        return crypto.encrypt(plaintext, mk, kid=kid, aad=aad)

    @api.model
    def decrypt(self, envelope, aad=b'', purpose='verify'):
        """Retrieve a secret's plaintext for the SIGNATURE-VERIFICATION path only.
        Metadata-only audit; the value is never logged. Fails closed."""
        mk = self._master_key()
        if mk is None:
            raise crypto.SecretError('master_key_unavailable')
        pt = crypto.decrypt(envelope, mk, aad=aad)
        try:
            self.env['mezze.audit.log'].sudo().log(
                'secret.accessed', severity='info',
                detail='{"purpose": "%s", "aad_present": %s}'
                       % (purpose, 'true' if aad else 'false'))
        except Exception:  # noqa: BLE001
            pass
        return pt

    @api.model
    def token_hash(self, token):
        """Keyed hash of a bearer token for indexed lookup without plaintext storage.
        Derives a lookup subkey from the master key. Returns None if no master key
        (bearer lookup then falls back to the legacy plaintext column)."""
        mk = self._master_key()
        if mk is None:
            return None
        # domain-separated subkey so the lookup hash key != the encryption key
        return crypto.keyed_hash(token, crypto.keyed_hash('mezze.token.lookup', mk).encode()[:32])
