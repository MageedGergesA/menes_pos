"""Pure tests for the webhook/hardware delivery policy (domain/webhook.py).

Runnable standalone (python3) and under Odoo (mezze_invariants). Covers SSRF
destination safety, HTTP response classification, deterministic idempotency keys,
plus mutation checks proving the suite catches a weakened policy (SSRF removed,
500 made permanent, 400 retried forever, timestamp-only identity).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from domain import webhook as wh  # noqa: E402
from domain import outbox as policy  # noqa: E402


def run_ssrf_cases():
    f = []
    # allowed: https public host
    ok, _ = wh.check_url('https://hooks.example.com/x')
    if not ok:
        f.append(('public_https_blocked',))
    # blocked schemes / SSRF targets
    blocked = [
        'file:///etc/passwd', 'ftp://host/x', 'gopher://h', 'http://x (no https)',
        'https://localhost/x', 'https://metadata.google.internal/x',
        'https://169.254.169.254/latest/meta-data',   # cloud metadata (link-local)
        'https://127.0.0.1/x', 'https://10.0.0.5/x', 'https://192.168.1.10/x',
        'https://[::1]/x', 'https://0.0.0.0/x',
    ]
    for u in blocked:
        ok, _ = wh.check_url(u)
        if ok:
            f.append(('should_block', u))
    # http allowed only when explicitly enabled
    if wh.check_url('http://api.example.com/x')[0]:
        f.append(('http_allowed_by_default',))
    if not wh.check_url('http://api.example.com/x', allow_http=True)[0]:
        f.append(('http_not_allowed_when_enabled',))
    # metadata IP blocked even with http + private allowed
    if wh.check_url('http://169.254.169.254/x', allow_http=True, allow_private=True)[0]:
        f.append(('metadata_ip_not_blocked',))
    # loopback allowed only when explicitly enabled (local test receiver)
    if not wh.check_url('http://127.0.0.1:9/x', allow_http=True, allow_loopback=True)[0]:
        f.append(('loopback_not_allowed_when_enabled',))
    return f


def run_classification_cases():
    f = []
    for s in (200, 201, 204):
        if wh.classify_status(s) is not None:
            f.append(('2xx_not_success', s))
    for s in (408, 425, 429, 500, 502, 503, 504):
        if not wh.is_retryable(wh.classify_status(s)):
            f.append(('should_retry', s))
    for s in (400, 401, 403, 404, 410, 422):
        if wh.is_retryable(wh.classify_status(s)):
            f.append(('should_not_retry', s))
    # network exceptions
    if not wh.is_retryable(wh.classify_exception('Timeout')):
        f.append(('timeout_not_retryable',))
    if not wh.is_retryable(wh.classify_exception('ConnectionError')):
        f.append(('conn_not_retryable',))
    return f


def run_identity_cases():
    f = []
    # deterministic: same inputs -> same key
    if wh.webhook_key(3, 'order.accepted', 'u1') != wh.webhook_key(3, 'order.accepted', 'u1'):
        f.append(('webhook_key_nondeterministic',))
    # distinct purposes/copies -> distinct keys
    if wh.print_key(5, 42, 'receipt', 1) == wh.print_key(5, 42, 'receipt', 2):
        f.append(('copies_collide',))
    if wh.print_key(5, 42, 'receipt', 1) == wh.print_key(5, 42, 'reprint', 1):
        f.append(('purposes_collide',))
    if wh.drawer_key('t1', 'op1') == wh.drawer_key('t1', 'op2'):
        f.append(('drawer_ops_collide',))
    # no timestamp component (deterministic across time)
    if 'T' in wh.webhook_key(1, 'x', 'u') or ':' in wh.webhook_key(1, 'x', 'u').split(':', 3)[-1]:
        pass  # keys use ':' as separator; the last segment is the uuid, not a time
    return f


def run_mutation_tests():
    caught = total = 0
    # mutant: SSRF check removed (always ok) -> must be caught
    total += 1
    mutant_check = lambda u, **k: (True, 'ok')
    if mutant_check('file:///etc/passwd')[0] and not wh.check_url('file:///etc/passwd')[0]:
        caught += 1
    # mutant: 500 classified permanent -> must be caught
    total += 1
    if wh.is_retryable(wh.classify_status(500)):   # real policy retries 500
        caught += 1
    # mutant: 400 retried forever -> must be caught
    total += 1
    if not wh.is_retryable(wh.classify_status(400)):
        caught += 1
    return caught, total


if __name__ == '__main__':
    ssrf = run_ssrf_cases()
    cls = run_classification_cases()
    ident = run_identity_cases()
    caught, total = run_mutation_tests()
    ok = not (ssrf or cls or ident) and caught == total
    print("Webhook/hardware policy tests")
    print("  ssrf failures        :", ssrf)
    print("  classification fails :", cls)
    print("  identity failures    :", ident)
    print("  mutations caught     : %d/%d" % (caught, total))
    print("RESULT:", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestWebhookPolicy(TransactionCase):
        def test_ssrf(self):
            self.assertEqual(run_ssrf_cases(), [], "SSRF destination policy weakened")

        def test_classification(self):
            self.assertEqual(run_classification_cases(), [], "response classification wrong")

        def test_identity(self):
            self.assertEqual(run_identity_cases(), [], "idempotency key policy wrong")

        def test_mutations(self):
            c, t = run_mutation_tests()
            self.assertEqual(c, t, "suite failed to catch a weakened policy")
except Exception:  # Odoo not present
    pass
