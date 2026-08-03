"""S5 — one authoritative secret / PII redactor for support bundles & diagnostics.

Everything that leaves the product as a diagnostic export (config summary, log
tail, environment facts) passes through :func:`redact` FIRST. The contract is
*leakage = 0*: no password, secret, token, API key, ``Authorization``/bearer
header, PEM private key, HMAC secret, Paymob/terminal credential, and no PAN /
CVV / PIN / customer email ever survives redaction. Over-redaction is acceptable
and deliberate — a diagnostic value we blank by accident is a non-event; a secret
we leak is a breach. This is the Python sibling of ``deploy/edge/lib/common.sh``'s
``redact()`` (support bundle parity) with PII added.
"""
import re

REDACTED = '***REDACTED***'

# (compiled pattern, replacement). Order matters: structural key=value / "k":"v"
# secrets first, then bearer/PEM, then value-shaped PII (PAN/CVV/email).
_PATTERNS = [
    # odoo.conf specifics
    (re.compile(r'(?i)(admin_passwd\s*=\s*).*'), r'\1' + REDACTED),
    (re.compile(r'(?i)(db_password\s*=\s*).*'), r'\1' + REDACTED),
    (re.compile(r'(?i)(MEZZE_MASTER_KEY\s*[=:]\s*)\S+'), r'\1' + REDACTED),
    # generic key=value / "key": "value" secrets (password/secret/token/apikey/hmac/private_key)
    (re.compile(r'(?i)("?\b(?:password|passwd|pwd)"?\s*[=:]\s*"?)[^"\s,}\]]+'), r'\1' + REDACTED),
    (re.compile(r'(?i)("?\b[\w.]*secret[\w.]*"?\s*[=:]\s*"?)[^"\s,}\]]+'), r'\1' + REDACTED),
    (re.compile(r'(?i)("?\b[\w.]*token[\w.]*"?\s*[=:]\s*"?)[^"\s,}\]]+'), r'\1' + REDACTED),
    (re.compile(r'(?i)("?\bapi[_-]?key"?\s*[=:]\s*"?)[^"\s,}\]]+'), r'\1' + REDACTED),
    (re.compile(r'(?i)("?\b[\w.]*hmac[\w.]*"?\s*[=:]\s*"?)[^"\s,}\]]+'), r'\1' + REDACTED),
    (re.compile(r'(?i)("?\bprivate[_-]?key"?\s*[=:]\s*"?)[^"\s,}\]]+'), r'\1' + REDACTED),
    (re.compile(r'(?i)("?\bpaymob[\w.-]*"?\s*[=:]\s*"?)[^"\s,}\]]+'), r'\1' + REDACTED),
    # HTTP Authorization header + bearer tokens
    (re.compile(r'(?i)(authorization\s*[=:]\s*).*'), r'\1' + REDACTED),
    (re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._\-+/=]{6,}'), r'\1' + REDACTED),
    # PEM private key blocks
    (re.compile(r'(?s)(-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----).*?(-----END [A-Z0-9 ]*PRIVATE KEY-----)'),
     r'\1 ' + REDACTED + r' \2'),
    # PAN (13-19 digits, space/dash grouped) + CVV/PIN near a label
    (re.compile(r'\b(?:\d[ -]?){12,18}\d\b'), REDACTED),
    (re.compile(r'(?i)(\b(?:cvv|cvc|cvv2|pin)\b\s*[=:]\s*)\d{3,6}'), r'\1' + REDACTED),
    # customer email PII
    (re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b'), REDACTED),
]


def redact(text):
    """Return ``text`` with every secret / PII pattern replaced by ``REDACTED``.

    Idempotent (``redact(redact(x)) == redact(x)``) and never raises — a
    diagnostic pipeline must not blow up on odd input.
    """
    if text is None:
        return text
    s = text if isinstance(text, str) else str(text)
    for pat, repl in _PATTERNS:
        s = pat.sub(repl, s)
    return s


def redact_lines(lines):
    """Redact an iterable of log lines, preserving order."""
    return [redact(ln) for ln in (lines or [])]


# A dict KEY that names a secret -> its whole value is redacted regardless of the
# value's shape (a bare token value carries no inline "key=" context for the
# value-level patterns to catch, so structured data must key off the field name).
_SECRET_KEY = re.compile(
    r'(?i)(password|passwd|pwd|secret|token|api[_-]?key|apikey|hmac|'
    r'private[_-]?key|paymob|authorization|bearer|master[_-]?key|credential)')


def redact_json(obj):
    """Recursively redact a JSON-like structure (dict/list/str). Dict keys are
    preserved (they name fields), but when a KEY names a secret the entire value is
    replaced by ``REDACTED``; otherwise string values are still scrubbed for inline
    secrets/PII (emails, PANs, ``key=value`` fragments). Non-string scalars pass
    through unchanged. Defence-in-depth for whole diagnostic bundles."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and _SECRET_KEY.search(k):
                out[k] = REDACTED
            else:
                out[k] = redact_json(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact_json(v) for v in obj]
    if isinstance(obj, str):
        return redact(obj)
    return obj
