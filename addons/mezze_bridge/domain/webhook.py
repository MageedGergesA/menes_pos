"""Pure webhook/hardware delivery policy — SSRF safety, response classification,
deterministic idempotency keys. No Odoo, no I/O: unit/property/mutation-testable.

The outbox consumers (models/outbox_consumers.py) delegate every *decision* here so
"is this URL safe", "is this response retryable", and "what is this operation's
identity" live in ONE tested place. DNS resolution + the actual socket/HTTP call
stay in the consumer, but they re-use ``ip_is_blocked`` on every resolved address.
"""

import ipaddress
from urllib.parse import urlsplit

from . import outbox as _policy   # reuse RETRYABLE/PERMANENT vocabulary

ALLOWED_SCHEMES = ('https',)          # http only when explicitly allowed per-call
BLOCKED_HOSTNAMES = frozenset({
    'localhost', 'ip6-localhost', 'ip6-loopback',
    'metadata', 'metadata.google.internal',
})
# common cloud metadata endpoints (IMDS) — always blocked
METADATA_IPS = frozenset({'169.254.169.254', 'fd00:ec2::254', '100.100.200.200'})


def ip_is_blocked(ip_str, allow_loopback=False, allow_private=False):
    """True if an IP literal must not be an SSRF target. Blocks loopback,
    link-local (incl. cloud metadata 169.254.169.254), private, multicast,
    reserved and unspecified ranges unless explicitly allowed."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # not a parseable IP -> refuse (fail closed)
    if str(ip) in METADATA_IPS:
        return True
    if ip.is_loopback:
        return not allow_loopback
    if ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    if ip.is_private:
        return not allow_private
    return False


def check_url(url, allow_http=False, allow_loopback=False, allow_private=False):
    """Validate a destination URL BEFORE any network call. Returns (ok, reason).
    Hostname targets pass the syntactic check here; the consumer must still resolve
    the host and re-run ``ip_is_blocked`` on every resolved address (DNS-rebind /
    SSRF defence). A literal-IP host is fully checked here."""
    if not url or not isinstance(url, str):
        return (False, 'invalid_url')
    try:
        parts = urlsplit(url)
    except ValueError:
        return (False, 'invalid_url')
    scheme = (parts.scheme or '').lower()
    allowed = set(ALLOWED_SCHEMES) | ({'http'} if allow_http else set())
    if scheme not in allowed:
        return (False, 'unsupported_scheme')
    host = (parts.hostname or '').lower()
    if not host:
        return (False, 'invalid_url')
    if host in BLOCKED_HOSTNAMES:
        return (False, 'blocked_host')
    # literal IP? fully validate now
    try:
        ipaddress.ip_address(parts.hostname)
        if ip_is_blocked(parts.hostname, allow_loopback, allow_private):
            return (False, 'blocked_ip')
    except ValueError:
        pass  # hostname — consumer resolves + re-checks each address
    return (True, 'ok')


# --- response classification --------------------------------------------------
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
# 4xx that cannot become valid by retrying (config/permanent)
_PERMANENT_STATUS = frozenset({400, 401, 403, 404, 405, 406, 410, 415, 422})


def classify_status(status):
    """Classify an HTTP status into an outbox failure class (or None on success)."""
    s = int(status)
    if 200 <= s < 300:
        return None
    if s == 408:
        return _policy.TIMEOUT
    if s in _RETRYABLE_STATUS:          # 425/429/500/502/503/504
        return _policy.TRANSPORT
    if s in _PERMANENT_STATUS:
        return _policy.CONFIGURATION if s in (401, 403) else _policy.PERMANENT
    # unknown 5xx -> retry; unknown 3xx/4xx -> permanent (don't spin)
    if 500 <= s < 600:
        return _policy.TRANSPORT
    return _policy.PERMANENT


def classify_exception(exc_name):
    """Network/exception name -> failure class (delegates to the outbox policy)."""
    return _policy.classify(exc_name)


def is_retryable(failure_class):
    return _policy.is_retryable(failure_class)


# --- deterministic idempotency keys ------------------------------------------
def webhook_key(integration_id, topic, op_uuid):
    return 'webhook:%s:%s:%s' % (integration_id, topic, op_uuid)


def print_key(printer_config_id, receipt_id, purpose, copy_seq=1):
    return 'print:%s:%s:%s:%s' % (printer_config_id, receipt_id, purpose, copy_seq)


def drawer_key(terminal_id, op_uuid):
    return 'drawer:%s:%s' % (terminal_id, op_uuid)
