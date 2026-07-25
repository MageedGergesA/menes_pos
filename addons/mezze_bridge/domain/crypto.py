"""Authenticated envelope encryption for machine secrets (P6.2 Phases 13-15).

Uses AES-256-GCM from the vetted ``cryptography`` library (no home-grown crypto,
no reversible encoding, no deterministic encryption). The ciphertext is a versioned
envelope so the algorithm + key id are explicit and the format can be upgraded:

    v1:AESGCM:<kid>:<base64 nonce>:<base64 ciphertext+tag>

The 256-bit master key lives OUTSIDE PostgreSQL and source (env ``MEZZE_MASTER_KEY``,
base64). This module is pure (key passed in); loading + fail-closed policy live in
models/secret_store.py.
"""
import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = 'v1'
ALGO = 'AESGCM'


class SecretError(Exception):
    """Encryption/decryption failure — callers MUST fail closed (deny)."""


def _b64e(b):
    return base64.b64encode(b).decode()


def _b64d(s):
    return base64.b64decode(s)


def encrypt(plaintext, master_key, kid='mk1', aad=b''):
    """Encrypt a str/bytes secret into a versioned envelope. Random 96-bit nonce
    per call (never reused). ``aad`` (e.g. principal id) is authenticated but not
    encrypted, binding the ciphertext to its context."""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode()
    if not master_key or len(master_key) != 32:
        raise SecretError('master_key_invalid')
    nonce = os.urandom(12)
    ct = AESGCM(master_key).encrypt(nonce, plaintext, aad or None)
    return ':'.join((VERSION, ALGO, str(kid), _b64e(nonce), _b64e(ct)))


def decrypt(envelope, master_key, aad=b''):
    """Decrypt + authenticate an envelope. Raises SecretError on any tamper /
    wrong key / bad format (the GCM tag fails authentication)."""
    if not envelope or not isinstance(envelope, str):
        raise SecretError('empty_envelope')
    parts = envelope.split(':')
    if len(parts) != 5 or parts[0] != VERSION or parts[1] != ALGO:
        raise SecretError('bad_envelope_format')
    if not master_key or len(master_key) != 32:
        raise SecretError('master_key_invalid')
    try:
        nonce, ct = _b64d(parts[3]), _b64d(parts[4])
        return AESGCM(master_key).decrypt(nonce, ct, aad or None).decode()
    except Exception as exc:  # noqa: BLE001 — cryptography raises InvalidTag etc.
        raise SecretError('decrypt_failed:%s' % type(exc).__name__)


def is_envelope(value):
    return isinstance(value, str) and value.startswith('%s:%s:' % (VERSION, ALGO))


def keyed_hash(value, key):
    """Deterministic keyed HMAC-SHA256 for INDEXED lookup of a bearer token without
    storing it in plaintext (one-way; the token itself is presented in the request
    and used directly for signature verification)."""
    return hmac.new(key, str(value).encode(), hashlib.sha256).hexdigest()


def load_master_key_from_env(env_var='MEZZE_MASTER_KEY'):
    """Return the 32-byte master key from a base64 env var, or None if unset/invalid
    (caller fails closed). The key is never read from the database or source."""
    raw = os.environ.get(env_var)
    if not raw:
        return None
    try:
        key = base64.b64decode(raw)
        return key if len(key) == 32 else None
    except Exception:  # noqa: BLE001
        return None
