# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Short-lived, HMAC-signed approval tokens.

A high-risk action (refund, void, big discount) must prove a supervisor actually
authorized it — PIN-verified server-side at ``/w1/approve``, which mints a token
here. The action endpoint then VERIFIES the token instead of trusting a
client-supplied cashier id (which could be forged). See ``docs/REVIEW_SCOPE.md``
W2-1.
"""
import base64
import hashlib
import hmac
import json
import time

_TTL = 120  # seconds — long enough to approve then complete the action


def _secret(env):
    return (env['ir.config_parameter'].sudo().get_param('database.secret') or 'mezze').encode()


def mint(env, action, approver_id, config_id=0, ttl=_TTL):
    """Return a signed token binding (action, approver, branch) with an expiry."""
    payload = {'a': action, 'by': int(approver_id), 'cfg': int(config_id or 0),
               'exp': int(time.time()) + int(ttl)}
    raw = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).decode()
    sig = hmac.new(_secret(env), raw.encode(), hashlib.sha256).hexdigest()
    return '%s.%s' % (raw, sig)


def verify(env, token, action):
    """Return the approver id (int) iff the token is authentic, matches ``action``
    and hasn't expired; otherwise None."""
    try:
        raw, sig = (token or '').rsplit('.', 1)
        good = hmac.new(_secret(env), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good):
            return None
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
        if payload.get('a') != action or int(payload.get('exp', 0)) < int(time.time()):
            return None
        return int(payload.get('by'))
    except Exception:  # noqa: BLE001
        return None
