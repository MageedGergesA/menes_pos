"""Pure verification helpers for Mezze Station device identity (WS-0).

The Windows station holds an ECDSA P-256 private key that never leaves the machine
— in a TPM through the Windows Platform Crypto Provider where the hardware allows
it, otherwise a DPAPI-protected software key. The server only ever sees the PUBLIC
key and a signature, so nothing here can mint a station credential.

Wire formats, chosen to match what Windows CNG produces natively so the client does
no format gymnastics with key material:

* public key  — SubjectPublicKeyInfo (DER), base64
* signature   — RAW ``r || s``, 64 bytes for P-256, base64
                (``NCryptSignHash`` returns exactly this; OpenSSL/``cryptography``
                speak DER, so the conversion lives here, on the server)

This module is pure: no ORM, no request, no key storage. It is the only place that
touches asymmetric primitives for station auth.
"""
import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils

CURVE_NAME = 'P-256'
ALGORITHM = 'ES256'          # ECDSA over P-256 with SHA-256 (RFC 7518 name)
_COORD_BYTES = 32            # P-256 => r and s are 32 bytes each


class StationKeyError(Exception):
    """The supplied key material is unusable. Callers MUST fail closed."""


def b64d(value):
    """Decode standard or URL-safe base64, tolerant of missing padding."""
    if isinstance(value, bytes):
        value = value.decode()
    value = (value or '').strip()
    pad = '=' * (-len(value) % 4)
    try:
        if '-' in value or '_' in value:
            return base64.urlsafe_b64decode(value + pad)
        return base64.b64decode(value + pad)
    except Exception as exc:  # noqa: BLE001
        raise StationKeyError('malformed base64') from exc


def load_public_key(spki_b64):
    """Load a base64 SubjectPublicKeyInfo and prove it is a P-256 public key.

    Anything else — RSA, another curve, a private key, garbage — raises, so an
    enrolment can never register a key the auth path cannot verify, and a client
    cannot smuggle in a weaker curve.
    """
    der = b64d(spki_b64)
    try:
        key = serialization.load_der_public_key(der)
    except Exception as exc:  # noqa: BLE001
        raise StationKeyError('not a DER SubjectPublicKeyInfo public key') from exc
    if not isinstance(key, ec.EllipticCurvePublicKey):
        raise StationKeyError('not an elliptic-curve public key')
    if not isinstance(key.curve, ec.SECP256R1):
        raise StationKeyError('unsupported curve: %s' % key.curve.name)
    return key


def public_key_fingerprint(spki_b64):
    """Stable, non-secret id for a public key (SHA-256 of the SPKI, base64url).

    Used for logging and for spotting the same key being presented by a second
    device — never as a credential.
    """
    from hashlib import sha256
    der = b64d(spki_b64)
    return base64.urlsafe_b64encode(sha256(der).digest()).decode().rstrip('=')


def _raw_to_der(signature):
    """Convert CNG's raw ``r || s`` into the DER encoding OpenSSL expects."""
    if len(signature) != 2 * _COORD_BYTES:
        raise StationKeyError('signature must be %d raw bytes for %s'
                              % (2 * _COORD_BYTES, CURVE_NAME))
    r = int.from_bytes(signature[:_COORD_BYTES], 'big')
    s = int.from_bytes(signature[_COORD_BYTES:], 'big')
    return asym_utils.encode_dss_signature(r, s)


def verify(spki_b64, message, signature_b64):
    """True only if ``signature_b64`` is this key's signature over ``message``.

    Accepts the raw CNG form and, for tolerance, a DER signature. Never raises on
    a bad signature — it returns False, so a caller cannot accidentally treat an
    exception path as success.
    """
    if isinstance(message, str):
        message = message.encode()
    try:
        key = load_public_key(spki_b64)
        sig = b64d(signature_b64)
    except StationKeyError:
        return False
    if not sig:
        return False
    candidates = []
    if len(sig) == 2 * _COORD_BYTES:
        try:
            candidates.append(_raw_to_der(sig))
        except StationKeyError:
            return False
    else:
        candidates.append(sig)          # already DER
    for der in candidates:
        try:
            key.verify(der, message, ec.ECDSA(hashes.SHA256()))
            return True
        except InvalidSignature:
            continue
        except Exception:  # noqa: BLE001 — malformed DER etc.
            continue
    return False


def auth_message(protocol, device_uuid, nonce):
    """The exact bytes a station signs to authenticate.

    Domain-separated and bound to the device, so a signature captured from one
    device/protocol can never be replayed as another. The nonce is server-issued
    and single-use, which is what makes a captured response worthless.
    """
    return ('%s|%s|%s' % (protocol, device_uuid or '', nonce or '')).encode()
